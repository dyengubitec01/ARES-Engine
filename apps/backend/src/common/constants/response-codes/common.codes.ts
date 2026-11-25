// ============================================================
// Common (00) - 공통 코드
// ============================================================
export const CommonResponseCode = {
  // 00-00: Unknown/Internal
  UNKNOWN: 'BKN000020',
  INTERNAL_ERROR: 'BKN000021',
  // 00-09: Health
  HEALTH_CHECK_SUCCESS: 'BKN000900',
  // 00-01: Validation
  VALIDATION_FAILED: 'BKN000120',
  // 00-02: Auth Common
  UNAUTHORIZED: 'BKN000220',
  FORBIDDEN: 'BKN000221',
} as const;

export const CommonHttpStatus: Record<string, number> = {
  [CommonResponseCode.UNKNOWN]: 500,
  [CommonResponseCode.INTERNAL_ERROR]: 500,
  [CommonResponseCode.VALIDATION_FAILED]: 400,
  [CommonResponseCode.UNAUTHORIZED]: 401,
  [CommonResponseCode.FORBIDDEN]: 403,
  [CommonResponseCode.HEALTH_CHECK_SUCCESS]: 200,
};

export const CommonMessages: Record<string, string> = {
  [CommonResponseCode.UNKNOWN]: '알 수 없는 오류가 발생했습니다',
  [CommonResponseCode.INTERNAL_ERROR]: '내부 서버 오류가 발생했습니다',
  [CommonResponseCode.VALIDATION_FAILED]: '유효성 검증에 실패했습니다',
  [CommonResponseCode.UNAUTHORIZED]: '인증이 필요합니다',
  [CommonResponseCode.FORBIDDEN]: '접근 권한이 없습니다',
  [CommonResponseCode.HEALTH_CHECK_SUCCESS]: '헬스체크 성공',
};
