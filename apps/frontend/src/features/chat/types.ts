// created by ARES team [2025-12-15]
// 채팅방 타입
export interface ChatRoom {
  id: string;
  title: string;
  lastMessage?: string;
  lastMessageTime?: string;
  createdAt?: string;
  unreadCount?: number;
  isFavorite: boolean; // 즐겨찾기 필터 기능을 위해 필수로 변경
}

// 참조 문서 아이템 타입 (실시간 스트리밍에서 사용)
export interface ReferenceSource {
  doc_title: string;
  doc_id: string;
  location?: string;
}

// 메시지 타입
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  feedback?: 'like' | 'dislike' | null;
  referenceTitles?: string[];
  referenceSources?: ReferenceSource[];
  error?: string;
}

// 참조 문서 타입
export interface SourceDocument {
  document_id: string;
  document_name: string;
  chunk_id: string;
  content: string;
  similarity_score: number;
}

// API 응답 타입 (백엔드 연동 대비)
export interface ChatRoomListResponse {
  success: boolean;
  data: ChatRoom[];
}

export interface ChatMessageListResponse {
  success: boolean;
  data: ChatMessage[];
}

// 피드백 요청 타입 (백엔드 연동 대비)
export interface FeedbackRequest {
  messageId: string;
  feedback: 'like' | 'dislike';
}
