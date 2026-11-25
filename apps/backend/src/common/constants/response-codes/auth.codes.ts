// ============================================================
// Auth (01) - 인증/인가
// ============================================================
export const AuthResponseCode = {
  // 01-01: Login
  AUTH_LOGIN_SUCCESS: 'BKN010100',
  AUTH_LOGIN_FAILED: 'BKN010120',
  // 01-02: Token
  AUTH_TOKEN_REFRESH_SUCCESS: 'BKN010200',
  AUTH_TOKEN_EXPIRED: 'BKN010220',
  AUTH_REFRESH_TOKEN_MISSING: 'BKN010221',
  // 01-03: Logout
  AUTH_LOGOUT_SUCCESS: 'BKN010300',
  // 01-04: Profile
  AUTH_PROFILE_SUCCESS: 'BKN010400',
} as const;

export const AuthHttpStatus: Record<string, number> = {
  [AuthResponseCode.AUTH_LOGIN_SUCCESS]: 200,
  [AuthResponseCode.AUTH_LOGIN_FAILED]: 401,
  [AuthResponseCode.AUTH_TOKEN_REFRESH_SUCCESS]: 200,
  [AuthResponseCode.AUTH_TOKEN_EXPIRED]: 401,
  [AuthResponseCode.AUTH_REFRESH_TOKEN_MISSING]: 401,
  [AuthResponseCode.AUTH_LOGOUT_SUCCESS]: 200,
  [AuthResponseCode.AUTH_PROFILE_SUCCESS]: 200,
};

export const AuthMessages: Record<string, string> = {
  [AuthResponseCode.AUTH_LOGIN_SUCCESS]: '로그인 성공',
  [AuthResponseCode.AUTH_LOGIN_FAILED]: '로그인 실패',
  [AuthResponseCode.AUTH_TOKEN_REFRESH_SUCCESS]: '토큰 갱신 성공',
  [AuthResponseCode.AUTH_TOKEN_EXPIRED]: '토큰이 만료되었습니다',
  [AuthResponseCode.AUTH_REFRESH_TOKEN_MISSING]: '리프레시 토큰이 없습니다',
  [AuthResponseCode.AUTH_LOGOUT_SUCCESS]: '로그아웃 성공',
  [AuthResponseCode.AUTH_PROFILE_SUCCESS]: '사용자 정보 조회 성공',
};
