/**
 * Swagger response/body example payloads for AdminController.
 *
 * Extracted from inline `@ApiResponse({ schema: { example: ... } })` blocks
 * to keep the controller focused on routing and authorization logic.
 * Editing these constants only affects generated OpenAPI/Swagger UI output —
 * no runtime behavior change.
 */

export const AdoptPostSuccessExample = {
  success: true,
  code: 'BKN030800',
  message: '서비스 제안 채택 처리 성공',
  data: {
    postId: 'p1b2c3d4-e5f6-7890-abcd-ef1234567890',
    grade: 150,
    reviewerId: 'u1b2c3d4-e5f6-7890-abcd-ef1234567890',
    reviewedAt: '2026-06-22T10:30:00.000Z',
  },
};

export const GetActivityListSuccessExample = {
  success: true,
  code: 'BKN030700',
  message: '사용자 활동 모니터링 처리 성공',
  data: {
    items: [
      {
        rank: 1,
        userId: 'u1b2c3d4-e5f6-7890-abcd-ef1234567890',
        name: '홍길동',
        department: '연구개발팀',
        jobTitle: '책임연구원',
        totalScore: 1850,
        eligible: true,
        questionCount: 84,
        uploadCount: 27,
        otherCitationCount: 32,
        lastActivityAt: '2026-06-22T10:00:00.000Z',
        lastActivityType: 'chat',
      },
    ],
    meta: { total: 50, page: 1, limit: 20, totalPages: 3 },
  },
};

export const GetActivityDetailSuccessExample = {
  success: true,
  code: 'BKN030700',
  message: '사용자 활동 모니터링 처리 성공',
  data: {
    rank: 1,
    userId: 'u1b2c3d4-e5f6-7890-abcd-ef1234567890',
    name: '홍길동',
    department: '연구개발팀',
    jobTitle: '책임연구원',
    totalScore: 1850,
    eligible: true,
    persona: {
      score: 1370,
      missedDays: 4,
      threeDayStreakCount: 2,
      fiveDayStreakCount: 1,
      questionCount: 84,
    },
    heritage: {
      score: 241,
      uploadCount: 27,
      otherCitationCount: 32,
      selfCitationCount: 8,
    },
    expert: {
      score: 239,
      feedbackCount: 3,
      answerSuggestionCount: 2,
      adoptionScore: 150,
    },
    lastActivityAt: '2026-06-22T10:00:00.000Z',
    lastActivityType: 'chat',
    updatedAt: '2026-06-22T10:30:00.000Z',
  },
};

export const RefreshActivitySuccessExample = {
  success: true,
  code: 'BKN030700',
  message: '사용자 활동 모니터링 처리 성공',
  data: { refreshedAt: '2026-04-22T10:30:00.000Z' },
};

export const GetUserListSuccessExample = {
  success: true,
  code: 'BKN030100',
  message: '사용자 목록 조회 성공',
  data: {
    items: [
      {
        id: 'u1b2c3d4-e5f6-7890-abcd-ef1234567890',
        email: 'user@company.com',
        name: '홍길동',
        jobTitle: '선임연구원',
        department: '연구개발팀',
        authorities: ['UPLOADER'],
        createdAt: '2026-01-01T00:00:00.000Z',
      },
    ],
    meta: { total: 50, page: 1, limit: 20, totalPages: 3 },
  },
};

export const GrantAuthoritiesSuccessExample = {
  success: true,
  code: 'BKN030200',
  message: '권한 처리 성공',
  data: {
    grantedCount: 1,
    grantedAuthorities: ['UPLOADER'],
    skippedAuthorities: [],
    message: '1개의 권한이 부여되었습니다',
  },
};

export const RevokeAuthoritiesSuccessExample = {
  success: true,
  code: 'BKN030200',
  message: '권한 처리 성공',
  data: {
    revokedCount: 1,
    revokedAuthorities: ['UPLOADER'],
    message: '1개의 권한이 회수되었습니다',
  },
};

export const GetAuthorityListSuccessExample = {
  success: true,
  code: 'BKN030200',
  message: '권한 처리 성공',
  data: [
    {
      id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
      authorityName: 'UPLOADER',
      createdAt: '2026-01-01T00:00:00.000Z',
    },
    {
      id: 'a2b2c3d4-e5f6-7890-abcd-ef1234567890',
      authorityName: 'ADMIN',
      createdAt: '2026-01-01T00:00:00.000Z',
    },
  ],
};

export const GetDeptListSuccessExample = {
  success: true,
  code: 'BKN030510',
  message: '부서 목록 조회 성공',
  data: [
    {
      id: 'd1b2c3d4-e5f6-7890-abcd-ef1234567890',
      deptName: '연구개발팀',
    },
    { id: 'd2b2c3d4-e5f6-7890-abcd-ef1234567890', deptName: '기획팀' },
  ],
};

export const SetDeptPermissionsSuccessExample = {
  success: true,
  code: 'BKN030500',
  message: '부서 권한이 설정되었습니다',
  data: {
    deptIds: ['uuid-1', 'uuid-2'],
    count: 2,
  },
};

export const GetUserDeptPermissionsSuccessExample = {
  success: true,
  code: 'BKN030500',
  message: '부서 권한 처리 성공',
  data: [
    {
      id: 'p1b2c3d4-e5f6-7890-abcd-ef1234567890',
      deptId: 'd1b2c3d4-e5f6-7890-abcd-ef1234567890',
      deptName: '연구개발팀',
      createdAt: '2026-01-01T00:00:00.000Z',
    },
    {
      id: 'p2b2c3d4-e5f6-7890-abcd-ef1234567890',
      deptId: 'd2b2c3d4-e5f6-7890-abcd-ef1234567890',
      deptName: '기획팀',
      createdAt: '2026-01-02T00:00:00.000Z',
    },
  ],
};

export const GetDocumentListSuccessExample = {
  success: true,
  code: 'BKN030400',
  message: '관리자 문서 처리 성공',
  data: {
    items: [
      {
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        title: '2026 1분기 업무 보고서',
        latestContent: {
          id: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
          versionNo: 1,
          originalFilename: '2026_Q1_report.pdf',
          fileSize: 1024000,
          mimeType: 'application/pdf',
          status: 'completed',
          statusReason: null,
          createdAt: '2026-03-20T09:00:00.000Z',
          deletedAt: null,
        },
        createdBy: {
          id: 'u1b2c3d4-e5f6-7890-abcd-ef1234567890',
          name: '홍길동',
          email: 'hong@company.com',
          department: '연구개발팀',
        },
        createdAt: '2026-03-20T09:00:00.000Z',
      },
    ],
    meta: { total: 50, page: 1, limit: 20, totalPages: 3 },
  },
};

export const SoftDeleteDocumentSuccessExample = {
  success: true,
  code: 'BKN030400',
  message: '관리자 문서 처리 성공',
  data: { message: '문서가 Soft Delete 되었습니다' },
};

export const HardDeleteDocumentSuccessExample = {
  success: true,
  code: 'BKN030400',
  message: '관리자 문서 처리 성공',
  data: { message: '문서가 영구 삭제되었습니다' },
};
