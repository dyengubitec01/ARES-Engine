// created by ARES team [2026-01-07]
// 문서 업로드 관련 타입 정의
export interface UploadInfo {
  uploadUrl: string;
  objectKey: string;
  versionId: string;
}

export interface UploadSession {
  documentId: string;
  uploads: UploadInfo[];
}

export interface UploadSessionResponse {
  data: UploadSession;
  message?: string;
}

export interface CompleteUploadResponse {
  data: {
    status: DocumentStatus;
  };
  message?: string;
}

// 문서 처리 상태
export type DocumentStatus =
  | 'uploading'          // 업로드 세션 생성됨, MinIO 업로드 대기 중
  | 'uploaded'           // MinIO 업로드 완료
  | 'pending_approval'   // 임베딩 승인 대기 중
  | 'queued'             // Embedding Request Server에 요청 전송됨
  | 'parsing'            // Worker가 파일 파싱 중
  | 'chunking'           // 문서 청킹 중
  | 'embedding'          // 임베딩 생성 중
  | 'upserting'          // Qdrant에 벡터 삽입 중
  | 'completed'          // 모든 처리 완료
  | 'rejected'           // 승인 반려
  | 'failed';            // 처리 실패

// 문서함 탭 타입
export type DocumentTab = 'my' | 'dept' | 'public' | 'favorite';

// UI 표시용 업로드 상태
export type UploadStatus = 'pending' | 'uploading' | 'uploaded' | 'failed';

export interface UploadProgress {
  fileName: string;
  fileSize: number;
  documentId: string;
  versionId: string;
  status: UploadStatus;
  progress: number;
  uploadedBytes: number;
  remainingTime?: number;
  error?: string;
  errorCode?: string;
}

export interface DocumentVersion {
  id: string;
  versionNo: number;
  originalFilename: string;
  fileSize: number;
  mimeType: string;
  status: DocumentStatus;
  statusReason?: string | null;
  isEnabled: boolean;
  createdAt: string;
}

export interface DocumentFile {
  id: string;
  title: string;
  latestContent: DocumentVersion;
  isFavorite: boolean;
  uploaderDepartment?: string;
  failedCount?: number;
  myTags?: { id: string; name: string; color: string }[];
  createdAt: string;
}

// 페이지네이션 메타
export interface PaginationMeta {
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

// 문서 목록 조회 응답
export interface GetDocumentsResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    items: DocumentFile[];
    meta: PaginationMeta;
  };
}

// 파일 검증 설정
export const FILE_VALIDATION = {
  MAX_SIZE: Infinity, // 용량 제한 없음
  ALLOWED_TYPES: [
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel.sheet.macroEnabled.12',
    'application/x-hwp',
    'text/plain',
    'text/csv',
    'application/csv'
  ],
  ALLOWED_EXTENSIONS: ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.xlsm', '.hwp', '.hwpx', '.txt', '.csv']
} as const;
