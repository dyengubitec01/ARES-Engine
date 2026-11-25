// created by ARES team [2026-01-27]
import apiClient from '../lib/apiClient';
import { createCustomError } from '../lib/customError';
import { COMMON_CODES } from '../constants/customCodes';

// ============================================
// 타입 정의
// ============================================

export interface CreateSessionResponse {
  success: boolean;
  message: string;
  data: {
    id: string;
    title: string;
    createdAt: string;
  };
}

export interface ChatSessionFromAPI {
  id: string;
  title: string | null;
  favorites: 'Y' | 'N';
  createdAt: string;
  messageCount: number;
}

export interface GetSessionsResponse {
  success: boolean;
  message: string;
  data: {
    items: ChatSessionFromAPI[];
    nextCursor: string | null;
    hasMore: boolean;
  };
}

export interface GetSessionResponse {
  success: boolean;
  message: string;
  data: ChatSessionFromAPI;
}

export interface ChatMessageFromAPI {
  id: string;
  type: 'Q' | 'A';
  content: string;
  chatTurn: number;
  feedback: 'Y' | 'N';
  createdAt: string;
}

export interface GetMessagesResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    items: ChatMessageFromAPI[];
    nextCursor: string | null;
    hasMore: boolean;
  };
}

export interface PromptRequest {
  prompt: string;
}

export interface SourceDocument {
  document_id: string;
  doc_title: string;
  doc_id: string;
  chunk_id: string;
  content: string;
  similarity_score: number;
  location?: string;
}

export interface SSEThoughtEvent {
  type: 'thought';
  data: string;
}

export interface SSEMessageEvent {
  type: 'message';
  data: {
    content: string;
  };
}

export interface SSEDoneEvent {
  type: 'done';
  data: {
    sources: SourceDocument[];
  };
}

export interface SSEErrorEvent {
  type: 'error';
  data: {
    message: string;
  };
}

export type SSEEvent = SSEThoughtEvent | SSEMessageEvent | SSEDoneEvent | SSEErrorEvent;

export interface SSECallbacks {
  onConnected?: (sessionId: string) => void;
  onThought?: (thought: string) => void;
  onMessage?: (content: string) => void;
  onDone?: (sources: SourceDocument[]) => void;
  onError?: (error: string) => void;
}

// ============================================
// 유틸리티 함수
// ============================================

/**
 * UUID 형식 유효성 검사
 */
export const isValidUUID = (uuid: string): boolean => {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(uuid);
};

// ============================================
// API 함수
// ============================================

/**
 * 새 채팅방 생성
 */
export const createChatSession = async (): Promise<CreateSessionResponse> => {
  const response = await apiClient.post<CreateSessionResponse>('/chat/sessions', {});
  return response.data;
};

/**
 * 채팅방 목록 조회
 */
export const getChatSessions = async (): Promise<GetSessionsResponse> => {
  const response = await apiClient.get<GetSessionsResponse>('/chat/sessions');
  return response.data;
};

/**
 * 채팅방 상세 조회
 */
export const getChatSession = async (sessionId: string): Promise<GetSessionResponse> => {
  const response = await apiClient.get<GetSessionResponse>(`/chat/sessions/${sessionId}`);
  return response.data;
};

/**
 * 채팅방 대화 내역 조회
 * @param sessionId 세션 ID
 * @param cursor 마지막으로 조회한 메시지의 chatTurn 값 (선택적, 초기 로딩 시에는 전달하지 않음)
 * @param signal AbortSignal (선택적, 요청 취소를 위한 시그널)
 */
export const getChatMessages = async (
  sessionId: string, 
  cursor?: number, 
  signal?: AbortSignal
): Promise<GetMessagesResponse> => {
  const params = cursor !== undefined ? { cursor } : {};
  const response = await apiClient.get<GetMessagesResponse>(
    `/chat/sessions/${sessionId}/messages`, 
    { params, signal }
  );
  return response.data;
};

/**
 * 채팅방 삭제
 */
export const deleteChatSession = async (sessionId: string): Promise<void> => {
  await apiClient.delete(`/chat/sessions/${sessionId}`);
};

/**
 * 채팅방 이름 변경
 */
export const updateChatSessionTitle = async (sessionId: string, title: string): Promise<void> => {
  await apiClient.patch(`/chat/sessions/${sessionId}`, { title });
};

/**
 * 즐겨찾기 토글 응답 타입
 */
export interface ToggleFavoriteResponse {
  success: boolean;
  message: string;
  data: {
    id: string;
    title: string;
    favorites: 'Y' | 'N';
  };
}

/**
 * 채팅방 즐겨찾기 토글
 * favorites 상태를 반전시킵니다 (Y <-> N)
 */
export const toggleChatSessionFavorite = async (sessionId: string): Promise<ToggleFavoriteResponse> => {
  const response = await apiClient.patch<ToggleFavoriteResponse>(`/chat/sessions/${sessionId}/favorite`);
  return response.data;
};

/**
 * 피드백 전송
 * @param interactionId 메시지(interaction) ID
 * @param feedback 'Y' (좋아요), 'N' (싫어요)
 */
export interface SendFeedbackResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    interactionId: string;
    feedback: 'Y' | 'N' | null;
  };
}

export const sendFeedback = async (interactionId: string, feedback: 'Y' | 'N'): Promise<SendFeedbackResponse> => {
  const response = await apiClient.patch<SendFeedbackResponse>(`/chat/interactions/${interactionId}/feedback`, { feedback });
  return response.data;
};

/**
 * 참조 문서 응답 타입 (과거 내역 API)
 */
export interface InteractionDocumentItem {
  docContent: {
    id: string;
    originalFilename: string;
  };
  location?: string;
}

export interface GetInteractionDocumentsResponse {
  success: boolean;
  message: string;
  data: InteractionDocumentItem[];
}

/**
 * 특정 interaction의 참조 문서 제목 목록 조회
 */
export const getInteractionDocuments = async (interactionId: string): Promise<GetInteractionDocumentsResponse> => {
  const response = await apiClient.get<GetInteractionDocumentsResponse>(`/chat/interactions/${interactionId}/documents`);
  return response.data;
};

/**
 * 다운로드 URL 응답 타입
 */
interface DownloadUrlResponse {
  success: boolean;
  data: {
    downloadUrl: string;
  };
}

/**
 * 문서 파일 다운로드 (2단계 방식)
 * @param docId 문서 버전 ID (doc_id)
 * @param fileName 다운로드할 파일명
 */
export const downloadDocument = async (docId: string, fileName: string): Promise<void> => {
  // 1단계: 다운로드 URL 가져오기 (JSON 응답)
  const response = await apiClient.get<DownloadUrlResponse>(`/documents/versions/${docId}/download`);

  // 2단계: downloadUrl 추출
  const downloadUrl = response.data.data.downloadUrl;

  if (!downloadUrl) {
    throw new Error('다운로드 URL을 받지 못했습니다.');
  }

  // 3단계: 외부 URL에서 실제 파일 데이터 가져오기 (fetch 사용)
  const fileResponse = await fetch(downloadUrl, {
    method: 'GET'
  });

  if (!fileResponse.ok) {
    throw new Error(`파일 다운로드 실패: ${fileResponse.status}`);
  }

  const blob = await fileResponse.blob();

  // 4단계: Blob URL 생성 및 다운로드 실행
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();

  // 메모리 정리
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};

/**
 * SSE 이벤트 처리 헬퍼 함수
 */
const processEvent = (eventType: string, dataStr: string, callbacks: SSECallbacks): void => {
  try {
    // JSON 파싱 시도 - 서버가 {"event": "...", "content": "..."} 형태로 보낼 경우
    let actualEventType = eventType;
    let actualContent = dataStr;
    
    try {
      const parsed = JSON.parse(dataStr);
      // JSON 내부에 event 필드가 있으면 우선 사용
      if (parsed.event) {
        actualEventType = parsed.event;
      }
      // content 또는 data 필드 추출 - 객체인 경우 content 필드 추출
      if (parsed.content) {
        actualContent = parsed.content;
      } else if (parsed.data) {
        // data가 문자열이면 그대로 사용, 객체이면 content 필드 추출
        if (typeof parsed.data === 'string') {
          actualContent = parsed.data;
        } else if (typeof parsed.data === 'object') {
          // 메타데이터 필터링: sessionId만 있거나 content가 없는 메타데이터는 무시
          const hasContent = parsed.data.content && typeof parsed.data.content === 'string';
          const hasSessionId = 'sessionId' in parsed.data;
          const keys = Object.keys(parsed.data);
          
          // sessionId만 있거나, 유의미한 content가 없는 메타데이터 객체는 빈 문자열 처리
          if (hasSessionId && !hasContent) {
            actualContent = '';
          } else if (hasContent) {
            actualContent = parsed.data.content;
          } else if (keys.length === 0) {
            // 빈 객체는 무시
            actualContent = '';
          } else {
            // 기타 객체는 JSON 문자열로 변환 (fallback)
            actualContent = JSON.stringify(parsed.data);
          }
        } else {
          actualContent = dataStr;
        }
      } else {
        actualContent = dataStr;
      }
    } catch {
      // JSON이 아니면 원본 그대로 사용
      actualContent = dataStr;
    }
    
    switch (actualEventType) {
      case 'connected':
        if (callbacks.onConnected) {
          try {
            const connectedData = JSON.parse(dataStr);
            const sessionId = connectedData.data?.sessionId;
            if (sessionId) {
              callbacks.onConnected(sessionId);
            }
          } catch (error) {
            console.error('[SSE] Failed to parse connected event:', error);
          }
        }
        break;

      case 'thought':
        if (callbacks.onThought) {
          callbacks.onThought(actualContent);
        }
        break;

      case 'message':
        if (callbacks.onMessage) {
          // 진짜 빈 문자열만 무시, 줄바꿈 문자는 유지
          if (actualContent !== '') {
            callbacks.onMessage(actualContent);
          }
        }
        break;

      case 'done':
        if (callbacks.onDone) {
          try {
            const doneData = JSON.parse(dataStr);
            const sources = doneData.sources || [];
            callbacks.onDone(sources);
          } catch {
            callbacks.onDone([]);
          }
        }
        break;

      case 'error':
        if (callbacks.onError) {
          let errorMessage = actualContent;
          try {
            const errorData = JSON.parse(dataStr);
            errorMessage = errorData.message || errorData.error || actualContent;
          } catch {
            errorMessage = actualContent;
          }
          callbacks.onError(errorMessage);
        }
        break;

      default:
        console.warn(`[SSE] Unknown event type: ${actualEventType}`);
    }
  } catch (error) {
    console.error('[SSE] Failed to process event:', error);
    console.error('[SSE] Event type:', eventType);
    console.error('[SSE] Data string:', dataStr);
  }
};

/**
 * SSE 스트리밍으로 프롬프트 전송
 * fetch API를 사용하여 POST 방식의 SSE 스트림 수신
 */
export const sendPromptWithSSE = async (
  sessionId: string | undefined,
  prompt: string,
  callbacks: SSECallbacks,
  abortSignal?: AbortSignal
): Promise<void> => {
  try {
    // 토큰 사전 검증: apiClient를 통해 가벼운 API 호출
    // 토큰이 만료되었다면 여기서 자동으로 리프레시됨
    try {
      await apiClient.get('/auth/me');
    } catch (error: unknown) {
      throw createCustomError(
        COMMON_CODES.COMMON_HTTP_ERROR,
        '인증에 실패했습니다. 다시 로그인해 주세요.',
        { originalError: error }
      );
    }
    
    // 토큰 검증 후 최신 토큰 가져오기
    const token = localStorage.getItem('accessToken');
    
    // 단일 엔드포인트 사용
    const url = `/api/chat/prompt`;
    
    // Request Body: sessionId가 있으면 포함, 없으면 제외
    const requestBody = sessionId 
      ? { prompt, sessionId }
      : { prompt };
    
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token && { Authorization: `Bearer ${token}` })
      },
      credentials: 'include',
      body: JSON.stringify(requestBody),
      signal: abortSignal
    });

    if (!response.ok) {
      throw createCustomError(
        COMMON_CODES.COMMON_HTTP_ERROR,
        `HTTP error! status: ${response.status}`,
        { status: response.status }
      );
    }

    if (!response.body) {
      throw createCustomError(COMMON_CODES.COMMON_RESPONSE_BODY_NULL);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let currentEvent = '';

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      let newlineIndex;
      while ((newlineIndex = buffer.indexOf('\n')) !== -1) {
        const line = buffer.substring(0, newlineIndex).trim();
        buffer = buffer.substring(newlineIndex + 1);

        if (line === '') {
          continue;
        }

        if (line.startsWith('event:')) {
          currentEvent = line.substring(6).trim();
          continue;
        }

        if (line.startsWith('data:')) {
          const dataLine = line.substring(5).trim();
          
          const eventToProcess = currentEvent || 'message';
          processEvent(eventToProcess, dataLine, callbacks);
          continue;
        }
      }
    }
  } catch (error: unknown) {
    if (error instanceof Error && error.name === 'AbortError') {
      return;
    }

    console.error('SSE streaming error:', error);
    if (callbacks.onError) {
      const errorMessage = error instanceof Error
        ? (error.message || '스트리밍 중 오류가 발생했습니다.')
        : '스트리밍 중 오류가 발생했습니다.';
      callbacks.onError(errorMessage);
    }
    throw error;
  }
};
