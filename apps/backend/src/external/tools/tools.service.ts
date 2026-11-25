import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

// Tools API v1 request/response interfaces
interface SummaryHistoryItem {
  content: string;
  role: 'user' | 'assistant';
}

interface SummaryRequest {
  history: SummaryHistoryItem[];
  summary: string | null;
}

interface SummaryResponse {
  code: string;
  msg: string;
  data: {
    summary: string;
  };
}

// Legacy interfaces for backward compatibility
interface ConversationPair {
  question: string;
  answer: string;
}

@Injectable()
export class ToolsService {
  private readonly logger = new Logger(ToolsService.name);
  private readonly toolsUrl: string;

  constructor(private configService: ConfigService) {
    this.toolsUrl =
      this.configService.get<string>('external.tools.url') ||
      'http://localhost:8002';
  }

  /**
   * Story 2.13: Compress conversation summary with sliding window
   * Calls Tools API /v1/summary endpoint
   *
   * @param sessionId - Chat session ID (for logging)
   * @param existingSummary - Existing summary text (null if none)
   * @param conversations - Old conversation pairs to compress
   * @returns New compressed summary string
   */
  async compressSummary(
    sessionId: string,
    existingSummary: string | null,
    conversations: ConversationPair[],
  ): Promise<string | null> {
    try {
      // Convert conversation pairs to history format
      const history: SummaryHistoryItem[] = [];
      for (const pair of conversations) {
        history.push({ content: pair.question, role: 'user' });
        history.push({ content: pair.answer, role: 'assistant' });
      }

      const requestBody: SummaryRequest = {
        history,
        summary: existingSummary,
      };

      this.logger.debug(
        `Calling Tools API /v1/summary with ${conversations.length} pairs for session ${sessionId}`,
      );

      const response = await fetch(`${this.toolsUrl}/v1/summary`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-TOL-Scope': 'backend',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        this.logger.error(`Tools API /v1/summary returned ${response.status}`);
        return null;
      }

      const result = (await response.json()) as SummaryResponse;

      if (!result.data?.summary) {
        this.logger.warn(
          `Tools API /v1/summary returned empty summary for session ${sessionId}`,
        );
        return null;
      }

      this.logger.debug(
        `Tools API returned summary (${result.data.summary.length} chars)`,
      );

      return result.data.summary;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to call Tools API /v1/summary: ${message}`);
      return null;
    }
  }

  /**
   * Check Tools API health
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.toolsUrl}/health`);
      return response.ok;
    } catch {
      return false;
    }
  }
}
