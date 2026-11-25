// ============================================================
// Admin (03) - 관리자
// ============================================================
export const AdminResponseCode = {
  // 03-01: User Management
  ADMIN_USER_LIST_SUCCESS: 'BKN030100',
  ADMIN_USER_NOT_FOUND: 'BKN030120',
  // 03-02: Authority Management
  ADMIN_AUTHORITY_GRANTED: 'BKN030200',
  ADMIN_AUTHORITY_REVOKED: 'BKN030200',
  ADMIN_AUTHORITY_LIST_SUCCESS: 'BKN030200',
  ADMIN_AUTHORITY_DUPLICATE: 'BKN030220',
  ADMIN_AUTHORITY_NOT_FOUND: 'BKN030221',
  ADMIN_AUTHORITY_USER_NOT_FOUND: 'BKN030222',
  // 03-05: Department Permission
  ADMIN_DEPT_LIST_SUCCESS: 'BKN030600',
  ADMIN_DEPT_PERMISSION_LIST_SUCCESS: 'BKN030500',
  ADMIN_DEPT_PERMISSION_SET: 'BKN030500',
  ADMIN_DEPT_PERMISSION_USER_NOT_FOUND: 'BKN030520',
  ADMIN_DEPT_PERMISSION_DEPT_NOT_FOUND: 'BKN030521',
  // 03-03: Analytics
  ADMIN_ANALYTICS_SUCCESS: 'BKN030300',
  // 03-04: Document Management (Admin)
  ADMIN_DOC_LIST_SUCCESS: 'BKN030400',
  ADMIN_DOC_SOFT_DELETE_SUCCESS: 'BKN030400',
  ADMIN_DOC_HARD_DELETE_SUCCESS: 'BKN030400',
  // 03-07: Activity Monitoring
  ADMIN_ACTIVITY_SUCCESS: 'BKN030700',
  ADMIN_ACTIVITY_REFRESH_SUCCESS: 'BKN030700',
  ADMIN_ACTIVITY_NOT_FOUND: 'BKN030720',
  // 03-08: Board Post Adoption
  ADMIN_BOARD_ADOPTION_SUCCESS: 'BKN030800',
  ADMIN_BOARD_ADOPTION_POST_NOT_FOUND: 'BKN030820',
  ADMIN_BOARD_ADOPTION_INVALID_TYPE: 'BKN030821',
} as const;

export const AdminHttpStatus: Record<string, number> = {
  [AdminResponseCode.ADMIN_USER_LIST_SUCCESS]: 200,
  [AdminResponseCode.ADMIN_USER_NOT_FOUND]: 404,
  [AdminResponseCode.ADMIN_AUTHORITY_GRANTED]: 200,
  [AdminResponseCode.ADMIN_AUTHORITY_DUPLICATE]: 409,
  [AdminResponseCode.ADMIN_AUTHORITY_NOT_FOUND]: 404,
  [AdminResponseCode.ADMIN_AUTHORITY_USER_NOT_FOUND]: 404,
  [AdminResponseCode.ADMIN_DEPT_LIST_SUCCESS]: 200,
  [AdminResponseCode.ADMIN_DEPT_PERMISSION_LIST_SUCCESS]: 200,
  [AdminResponseCode.ADMIN_DEPT_PERMISSION_USER_NOT_FOUND]: 404,
  [AdminResponseCode.ADMIN_DEPT_PERMISSION_DEPT_NOT_FOUND]: 404,
  [AdminResponseCode.ADMIN_ANALYTICS_SUCCESS]: 200,
  [AdminResponseCode.ADMIN_DOC_LIST_SUCCESS]: 200,
  [AdminResponseCode.ADMIN_ACTIVITY_SUCCESS]: 200,
  [AdminResponseCode.ADMIN_ACTIVITY_NOT_FOUND]: 404,
  [AdminResponseCode.ADMIN_BOARD_ADOPTION_SUCCESS]: 200,
  [AdminResponseCode.ADMIN_BOARD_ADOPTION_POST_NOT_FOUND]: 404,
  [AdminResponseCode.ADMIN_BOARD_ADOPTION_INVALID_TYPE]: 400,
};

export const AdminMessages: Record<string, string> = {
  [AdminResponseCode.ADMIN_USER_LIST_SUCCESS]: '사용자 목록 조회 성공',
  [AdminResponseCode.ADMIN_USER_NOT_FOUND]: '사용자를 찾을 수 없습니다',
  [AdminResponseCode.ADMIN_AUTHORITY_GRANTED]: '권한 처리 성공',
  [AdminResponseCode.ADMIN_AUTHORITY_DUPLICATE]: '이미 부여된 권한입니다',
  [AdminResponseCode.ADMIN_AUTHORITY_NOT_FOUND]: '권한을 찾을 수 없습니다',
  [AdminResponseCode.ADMIN_AUTHORITY_USER_NOT_FOUND]:
    '권한 부여 대상을 찾을 수 없습니다',
  [AdminResponseCode.ADMIN_DEPT_LIST_SUCCESS]: '부서 목록 조회 성공',
  [AdminResponseCode.ADMIN_DEPT_PERMISSION_LIST_SUCCESS]: '부서 권한 처리 성공',
  [AdminResponseCode.ADMIN_DEPT_PERMISSION_USER_NOT_FOUND]:
    '사용자를 찾을 수 없습니다',
  [AdminResponseCode.ADMIN_DEPT_PERMISSION_DEPT_NOT_FOUND]:
    '유효한 부서를 찾을 수 없습니다',
  [AdminResponseCode.ADMIN_ANALYTICS_SUCCESS]: '통계 조회 성공',
  [AdminResponseCode.ADMIN_DOC_LIST_SUCCESS]: '관리자 문서 처리 성공',
  [AdminResponseCode.ADMIN_ACTIVITY_SUCCESS]: '사용자 활동 모니터링 처리 성공',
  [AdminResponseCode.ADMIN_ACTIVITY_NOT_FOUND]:
    '사용자 활동 데이터를 찾을 수 없습니다',
  [AdminResponseCode.ADMIN_BOARD_ADOPTION_SUCCESS]: '서비스 제안 채택 처리 성공',
  [AdminResponseCode.ADMIN_BOARD_ADOPTION_POST_NOT_FOUND]:
    '게시글을 찾을 수 없습니다',
  [AdminResponseCode.ADMIN_BOARD_ADOPTION_INVALID_TYPE]:
    'suggestion 게시판 글만 채택할 수 있습니다',
};
