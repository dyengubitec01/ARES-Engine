/**
 * Swagger response/body example payloads for AuthController.
 *
 * Extracted from inline `@ApiResponse({ schema: { example: ... } })` blocks
 * to keep the controller focused on routing and authorization logic.
 * Editing these constants only affects generated OpenAPI/Swagger UI output —
 * no runtime behavior change.
 */

export const GetLoginUrlSuccessExample = {
  success: true,
  code: 'BKN010100',
  message: '로그인 성공',
  data: {
    url: 'https://login.microsoftonline.com/tenant-id/oauth2/v2.0/authorize?...',
  },
};

export const RefreshSuccessExample = {
  success: true,
  code: 'BKN010200',
  message: '토큰 갱신 성공',
  data: { expiresIn: 3600 },
};

export const LogoutSuccessExample = {
  success: true,
  code: 'BKN010300',
  message: '로그아웃 성공',
  data: null,
};

export const GetProfileSuccessExample = {
  success: true,
  code: 'BKN010400',
  message: '사용자 정보 조회 성공',
  data: {
    userId: 'u1b2c3d4-e5f6-7890-abcd-ef1234567890',
    email: 'user@company.com',
    name: '홍길동',
    authorities: ['UPLOADER'],
    jobTitle: '선임연구원',
    department: '연구개발팀',
    authDeptId: 'd1a2b3c4-e5f6-7890-abcd-ef1234567890',
    deptPermissions: [
      { id: 'd2a2b3c4-e5f6-7890-abcd-ef1234567891', name: '기획팀' },
      { id: 'd3a2b3c4-e5f6-7890-abcd-ef1234567892', name: '마케팅팀' },
    ],
  },
};
