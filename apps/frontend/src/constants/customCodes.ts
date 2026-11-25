// created by ARES team [2026-02-24]
// ============================================
// 01. 인증 관련 (FRN01XXXX)
// ============================================

export const AUTH_CODES = {
  // 유효성 검사 (FRN0101XX)
  AUTH_USER_NOT_FOUND: 'FRN010120',
  AUTH_INVALID_OAUTH_PARAMS: 'FRN010121',
  
  // API/상태 전환 (FRN0102XX)
  AUTH_FAILED: 'FRN010220',
  AUTH_ACCESS_DENIED: 'FRN010221',
  AUTH_OAUTH_CALLBACK_FAILED: 'FRN010222',
  AUTH_TOKEN_REFRESH_FAILED: 'FRN010223',
  AUTH_PROFILE_FETCH_FAILED: 'FRN010224',
  AUTH_LOGIN_URL_FETCH_FAILED: 'FRN010225',
  AUTH_INVALID_LOGIN_RESPONSE: 'FRN010226',
  
  // 로컬 로직 (FRN0103XX)
  AUTH_LOGOUT_FAILED: 'FRN010320',
  AUTH_SESSION_REFRESH_FAILED: 'FRN010321',
} as const;

// ============================================
// 02. 문서 관련 (FRN02XXXX)
// ============================================

export const DOCUMENT_CODES = {
  // 유효성 검사 (FRN0201XX)
  DOC_INVALID_FILE_TYPE: 'FRN020120',
  DOC_FILE_SIZE_EXCEEDED: 'FRN020121',
  DOC_INVALID_FILE_EXTENSION: 'FRN020122',
  DOC_FILE_VALIDATION_FAILED: 'FRN020123',

  // API/상태 전환 (FRN0202XX)
  DOC_UPLOAD_SESSION_FAILED: 'FRN020220',
  DOC_DUPLICATE_FILE: 'FRN020221',
  DOC_MINIO_UPLOAD_FAILED: 'FRN020222',
  DOC_UPLOAD_COMPLETE_FAILED: 'FRN020223',
  DOC_DOCUMENT_FETCH_FAILED: 'FRN020224',
  DOC_EMBEDDING_REQUEST_FAILED: 'FRN020225',
  DOC_FAVORITE_TOGGLE_FAILED: 'FRN020226',
  DOC_DOCUMENT_DELETE_FAILED: 'FRN020227',

  // 로컬 로직 (FRN0203XX)
  DOC_NO_DOCUMENT_SELECTED: 'FRN020320',
  DOC_FILE_HASH_FAILED: 'FRN020321',
  DOC_UPLOAD_SESSION_INVALID_RESPONSE: 'FRN020322',
  DOC_UPLOAD_SESSION_MISSING_DATA: 'FRN020323',
  DOC_UPLOAD_SESSION_MISSING_VERSION: 'FRN020324',
  DOC_UPLOAD_COMPLETE_INVALID_RESPONSE: 'FRN020325',

  // 태그 관련 (FRN0204XX)
  DOC_TAG_DUPLICATE: 'FRN020420',
  DOC_TAG_NOT_FOUND: 'FRN020421',
  DOC_TAG_FORBIDDEN: 'FRN020422',
  DOC_TAG_DOCUMENT_FORBIDDEN: 'FRN020423',
  DOC_TAG_CREATE_FAILED: 'FRN020424',
} as const;

// ============================================
// 03. 채팅 관련 (FRN03XXXX)
// ============================================

export const CHAT_CODES = {
  // 유효성 검사 (FRN0301XX)
  CHAT_EMPTY_MESSAGE: 'FRN030120',
  CHAT_NO_ROOM_SELECTED: 'FRN030121',
  CHAT_INVALID_ROOM_UUID: 'FRN030122',
  CHAT_EMPTY_ROOM_NAME: 'FRN030123',
  
  // API/상태 전환 (FRN0302XX)
  CHAT_ROOM_CREATE_FAILED: 'FRN030220',
  CHAT_ROOM_NOT_FOUND: 'FRN030221',
  CHAT_MESSAGE_SEND_FAILED: 'FRN030222',
  CHAT_SSE_STREAM_ERROR: 'FRN030223',
  CHAT_HISTORY_LOAD_FAILED: 'FRN030224',
  CHAT_ROOM_LIST_LOAD_FAILED: 'FRN030225',
  
  // 로컬 로직 (FRN0303XX)
  CHAT_FAVORITE_TOGGLE_FAILED: 'FRN030320',
  CHAT_ROOM_RENAME_FAILED: 'FRN030321',
  CHAT_ROOM_DELETE_FAILED: 'FRN030322',
} as const;

// ============================================
// 04. 공통/네트워크 (FRN04XXXX)
// ============================================

export const COMMON_CODES = {
  // API/상태 전환 (FRN0402XX)
  COMMON_NETWORK_ERROR: 'FRN040220',
  COMMON_TIMEOUT_ERROR: 'FRN040221',
  COMMON_HTTP_ERROR: 'FRN040222',
  COMMON_RESPONSE_BODY_NULL: 'FRN040223',
  COMMON_INVALID_RESPONSE_FORMAT: 'FRN040224',
  COMMON_SERVER_ERROR: 'FRN040225',
  
  // 로컬 로직 (FRN0403XX)
  COMMON_UNKNOWN_ERROR: 'FRN040320',
} as const;

// ============================================
// 전체 코드 통합
// ============================================

export const FRN_CODES = {
  ...AUTH_CODES,
  ...DOCUMENT_CODES,
  ...CHAT_CODES,
  ...COMMON_CODES,
} as const;

// 타입 정의
export type FRNCodeValue = typeof FRN_CODES[keyof typeof FRN_CODES];

// ============================================
// 에러 메시지 매핑
// ============================================

export const ERROR_MESSAGES: Record<FRNCodeValue, string> = {
  // 인증 관련
  [AUTH_CODES.AUTH_USER_NOT_FOUND]: '사용자 정보를 불러올 수 없습니다.',
  [AUTH_CODES.AUTH_INVALID_OAUTH_PARAMS]: '인증 정보가 올바르지 않습니다.',
  [AUTH_CODES.AUTH_FAILED]: '인증에 실패했습니다. 다시 로그인해주세요.',
  [AUTH_CODES.AUTH_ACCESS_DENIED]: '접근 권한이 없습니다.',
  [AUTH_CODES.AUTH_OAUTH_CALLBACK_FAILED]: '로그인 처리 중 오류가 발생했습니다.',
  [AUTH_CODES.AUTH_TOKEN_REFRESH_FAILED]: '토큰 갱신에 실패했습니다.',
  [AUTH_CODES.AUTH_PROFILE_FETCH_FAILED]: '사용자 프로필 조회에 실패했습니다.',
  [AUTH_CODES.AUTH_LOGIN_URL_FETCH_FAILED]: '로그인 URL 조회에 실패했습니다.',
  [AUTH_CODES.AUTH_INVALID_LOGIN_RESPONSE]: '잘못된 로그인 응답 형식입니다.',
  [AUTH_CODES.AUTH_LOGOUT_FAILED]: '로그아웃 처리 중 오류가 발생했습니다.',
  [AUTH_CODES.AUTH_SESSION_REFRESH_FAILED]: '세션 갱신에 실패했습니다.',
  
  // 문서 관련
  [DOCUMENT_CODES.DOC_INVALID_FILE_TYPE]: '지원하지 않는 파일 형식입니다.',
  [DOCUMENT_CODES.DOC_FILE_SIZE_EXCEEDED]: '파일 크기가 제한을 초과했습니다.',
  [DOCUMENT_CODES.DOC_INVALID_FILE_EXTENSION]: '지원하지 않는 파일 확장자입니다.',
  [DOCUMENT_CODES.DOC_FILE_VALIDATION_FAILED]: '파일 정보 유효성 검증에 실패했습니다.',
  [DOCUMENT_CODES.DOC_UPLOAD_SESSION_FAILED]: '업로드 세션 생성 중 오류가 발생했습니다.',
  [DOCUMENT_CODES.DOC_DUPLICATE_FILE]: '이미 동일한 파일이 존재합니다.',
  [DOCUMENT_CODES.DOC_MINIO_UPLOAD_FAILED]: 'MinIO 파일 업로드에 실패했습니다.',
  [DOCUMENT_CODES.DOC_UPLOAD_COMPLETE_FAILED]: '업로드 완료 보고 중 오류가 발생했습니다.',
  [DOCUMENT_CODES.DOC_DOCUMENT_FETCH_FAILED]: '문서 목록 조회에 실패했습니다.',
  [DOCUMENT_CODES.DOC_EMBEDDING_REQUEST_FAILED]: '임베딩 요청 중 오류가 발생했습니다.',
  [DOCUMENT_CODES.DOC_FAVORITE_TOGGLE_FAILED]: '북마크 처리 중 오류가 발생했습니다.',
  [DOCUMENT_CODES.DOC_DOCUMENT_DELETE_FAILED]: '문서 삭제 중 오류가 발생했습니다.',
  [DOCUMENT_CODES.DOC_NO_DOCUMENT_SELECTED]: '임베딩할 문서를 선택해주세요.',
  [DOCUMENT_CODES.DOC_FILE_HASH_FAILED]: '파일 해시 계산에 실패했습니다.',
  [DOCUMENT_CODES.DOC_UPLOAD_SESSION_INVALID_RESPONSE]: '업로드 세션 생성 실패: 응답 데이터 없음',
  [DOCUMENT_CODES.DOC_UPLOAD_SESSION_MISSING_DATA]: '업로드 세션 생성 실패: uploads 배열이 비어있음',
  [DOCUMENT_CODES.DOC_UPLOAD_SESSION_MISSING_VERSION]: '업로드 세션 생성 실패: versionId가 없음',
  [DOCUMENT_CODES.DOC_UPLOAD_COMPLETE_INVALID_RESPONSE]: '업로드 완료 처리 실패: 응답 데이터 없음',
  [DOCUMENT_CODES.DOC_TAG_DUPLICATE]: '이미 사용 중인 태그 이름입니다.',
  [DOCUMENT_CODES.DOC_TAG_NOT_FOUND]: '태그를 찾을 수 없습니다.',
  [DOCUMENT_CODES.DOC_TAG_FORBIDDEN]: '태그에 대한 권한이 없습니다.',
  [DOCUMENT_CODES.DOC_TAG_DOCUMENT_FORBIDDEN]: '문서에 대한 권한이 없습니다.',
  [DOCUMENT_CODES.DOC_TAG_CREATE_FAILED]: '태그 생성 중 오류가 발생했습니다.',
  
  // 채팅 관련
  [CHAT_CODES.CHAT_EMPTY_MESSAGE]: '메시지를 입력해주세요.',
  [CHAT_CODES.CHAT_NO_ROOM_SELECTED]: '채팅방을 먼저 생성해주세요.',
  [CHAT_CODES.CHAT_INVALID_ROOM_UUID]: '유효하지 않은 채팅방 ID입니다.',
  [CHAT_CODES.CHAT_EMPTY_ROOM_NAME]: '채팅방 이름을 입력해주세요.',
  [CHAT_CODES.CHAT_ROOM_CREATE_FAILED]: '새 채팅방 생성에 실패했습니다.',
  [CHAT_CODES.CHAT_ROOM_NOT_FOUND]: '존재하지 않는 채팅방입니다.',
  [CHAT_CODES.CHAT_MESSAGE_SEND_FAILED]: '메시지 전송에 실패했습니다.',
  [CHAT_CODES.CHAT_SSE_STREAM_ERROR]: 'SSE 스트리밍 중 오류가 발생했습니다.',
  [CHAT_CODES.CHAT_HISTORY_LOAD_FAILED]: '대화 내역 로드에 실패했습니다.',
  [CHAT_CODES.CHAT_ROOM_LIST_LOAD_FAILED]: '채팅방 목록 로드에 실패했습니다.',
  [CHAT_CODES.CHAT_FAVORITE_TOGGLE_FAILED]: '즐겨찾기 변경에 실패했습니다.',
  [CHAT_CODES.CHAT_ROOM_RENAME_FAILED]: '채팅방 이름 변경에 실패했습니다.',
  [CHAT_CODES.CHAT_ROOM_DELETE_FAILED]: '채팅방 삭제에 실패했습니다.',
  
  // 공통/네트워크
  [COMMON_CODES.COMMON_NETWORK_ERROR]: '서버에 연결할 수 없습니다.',
  [COMMON_CODES.COMMON_TIMEOUT_ERROR]: '서버 응답 시간이 초과되었습니다.',
  [COMMON_CODES.COMMON_HTTP_ERROR]: 'HTTP 오류가 발생했습니다.',
  [COMMON_CODES.COMMON_RESPONSE_BODY_NULL]: '응답 본문이 없습니다.',
  [COMMON_CODES.COMMON_INVALID_RESPONSE_FORMAT]: '잘못된 응답 형식입니다.',
  [COMMON_CODES.COMMON_SERVER_ERROR]: '서버 오류가 발생했습니다.',
  [COMMON_CODES.COMMON_UNKNOWN_ERROR]: '알 수 없는 오류가 발생했습니다.',
};

// ============================================
// 백엔드 에러 코드 → 프론트엔드 코드 매핑
// ============================================

export const BACKEND_TO_FRONTEND_CODE_MAP: Record<string, FRNCodeValue> = {
  // 문서 관련 백엔드 코드
  'BKN040120': DOCUMENT_CODES.DOC_FILE_SIZE_EXCEEDED,
  'BKN040121': DOCUMENT_CODES.DOC_INVALID_FILE_TYPE,
  'BKN040123': DOCUMENT_CODES.DOC_DUPLICATE_FILE,
  'BKN000120': DOCUMENT_CODES.DOC_FILE_VALIDATION_FAILED,

  // 태그 관련 백엔드 코드
  'BKN040920': DOCUMENT_CODES.DOC_TAG_DUPLICATE,
  'BKN040921': DOCUMENT_CODES.DOC_TAG_NOT_FOUND,
  'BKN040922': DOCUMENT_CODES.DOC_TAG_FORBIDDEN,
  'BKN040923': DOCUMENT_CODES.DOC_TAG_DOCUMENT_FORBIDDEN,
};

/**
 * 백엔드 에러 코드를 프론트엔드 코드로 변환
 */
export function mapBackendCodeToFrontend(backendCode: string): FRNCodeValue | null {
  return BACKEND_TO_FRONTEND_CODE_MAP[backendCode] || null;
}
