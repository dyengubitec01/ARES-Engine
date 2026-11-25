import {
  Injectable,
  Logger,
  ServiceUnavailableException,
  BadRequestException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

interface ChatMessage {
  role: string;
  content: string;
}

interface ChatRequestParams {
  query: string;
  history: ChatMessage[];
  sessionId: string;
  userId: string;
  userPosition?: string;
  authDeptIds?: string[];
  excludedDocs?: string[];
  summary?: string;
  accessToken?: string;
}

/**
 * SSE 이벤트 타입 (챗봇 서버에서 전송)
 * - thought: AI 사고 과정
 * - message: AI 응답 내용
 * - done: 스트리밍 완료 (sources 포함)
 */
export interface ChatbotSseEvent {
  event: 'thought' | 'message' | 'done';
  content?: string;
  sources?: Array<{
    doc_id: string;
    doc_title: string;
    doc_content: string;
    location?: string;
  }>;
  usage?: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
}

@Injectable()
export class ChatbotService {
  private readonly logger = new Logger(ChatbotService.name);
  private readonly chatbotUrl: string;

  // Retry configuration
  private readonly MAX_RETRIES = 3;
  private readonly INITIAL_DELAY_MS = 1000;

  constructor(private configService: ConfigService) {
    this.chatbotUrl =
      this.configService.get<string>('external.chatbot.url') ||
      'http://localhost:8000';
  }

  /**
   * Retry wrapper with exponential backoff
   * Retries: 1s → 2s → 4s
   */
  private async withRetry<T>(
    operation: () => Promise<T>,
    context: string,
  ): Promise<T> {
    let lastError: Error = new Error('Unknown error');

    for (let attempt = 1; attempt <= this.MAX_RETRIES; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));

        // Don't retry client errors (4xx) - AC5
        if (this.isNonRetryableError(error)) {
          throw error;
        }

        if (attempt < this.MAX_RETRIES) {
          const delay = this.INITIAL_DELAY_MS * Math.pow(2, attempt - 1);
          this.logger.warn(
            `${context} failed (attempt ${attempt}/${this.MAX_RETRIES}), retrying in ${delay}ms...`,
          );
          await this.sleep(delay);
        }
      }
    }

    this.logger.error(
      `${context} failed after ${this.MAX_RETRIES} attempts: ${lastError.message}`,
    );
    throw new ServiceUnavailableException(
      'Chatbot service unavailable after retries',
    );
  }

  /**
   * Check if error should not be retried (client errors)
   */
  private isNonRetryableError(error: unknown): boolean {
    if (error instanceof BadRequestException) {
      return true;
    }
    // HTTP 4xx errors should not be retried
    if (
      error instanceof Error &&
      (error.message.includes('400') ||
        error.message.includes('401') ||
        error.message.includes('403') ||
        error.message.includes('404'))
    ) {
      return true;
    }
    return false;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * 챗봇 서버에 메시지를 전송하고 SSE 이벤트를 그대로 yield (패스스루)
   * 프론트엔드에서 thought, message, done 이벤트를 직접 처리
   */
  async *sendMessage(
    params: ChatRequestParams,
    signal?: AbortSignal,
  ): AsyncGenerator<ChatbotSseEvent> {
    const {
      query,
      history,
      sessionId,
      userId,
      userPosition,
      authDeptIds,
      excludedDocs,
      summary,
      accessToken,
    } = params;

    // Use retry logic for initial connection - AC1, AC2, AC3, AC4
    const response = await this.withRetry(async () => {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (accessToken) {
        headers['Authorization'] = `Bearer ${accessToken}`;
      }

      const res = await fetch(`${this.chatbotUrl}/v1/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          query,
          history,
          session_id: sessionId,
          user_id: userId,
          user_position: userPosition,
          user_depts: authDeptIds || [],
          excluded_docs: excludedDocs || [],
          summary: summary || null,
        }),
        signal,
      });

      if (!res.ok) {
        throw new ServiceUnavailableException(
          `Chatbot service returned ${res.status}`,
        );
      }

      return res;
    }, 'sendMessage');

    const reader = response.body?.getReader();
    if (!reader) {
      throw new ServiceUnavailableException('Failed to read stream');
    }

    const decoder = new TextDecoder();

    let currentEvent: string | null = null;
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          // 정상적인 SSE 스트림은 마지막 메시지가 \n\n 으로 끝나므로 buffer 비어있어야 정상
          if (buffer.trim().length > 0) {
            this.logger.warn(
              `SSE stream ended with non-empty buffer (${buffer.length} bytes): "${buffer.slice(0, 200)}"`,
            );
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        // 마지막 element 는 다음 read 의 시작과 합쳐야 하므로 buffer 로 보관
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          // event: 라인 파싱
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
            continue;
          }

          // data: 라인 파싱
          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            if (data === '[DONE]') continue;

            try {
              const parsed = JSON.parse(data);

              // event 타입 결정: 별도 라인의 event 또는 JSON 내부의 event
              const eventType = currentEvent || parsed.event;

              if (eventType === 'message' || eventType === 'thought') {
                yield {
                  event: eventType as 'message' | 'thought',
                  content: parsed.content,
                } as ChatbotSseEvent;
              } else if (eventType === 'done') {
                yield {
                  event: 'done',
                  sources: parsed.sources,
                  usage: parsed.usage,
                } as ChatbotSseEvent;
              }

              // 이벤트 처리 후 리셋
              currentEvent = null;
            } catch {
              // JSON 파싱 실패 시 무시
              this.logger.warn(`Failed to parse SSE data: ${data}`);
            }
          }
        }
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Stream processing error: ${message}`);
      throw new ServiceUnavailableException('Chatbot stream interrupted');
    }
  }

  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.chatbotUrl}/health`);
      return response.ok;
    } catch {
      return false;
    }
  }
}
