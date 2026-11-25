/**
 * Swagger response/body example payloads for BoardController.
 *
 * Extracted from inline `@ApiResponse({ schema: { example: ... } })` blocks
 * to keep the controller focused on routing and authorization logic.
 * Editing these constants only affects generated OpenAPI/Swagger UI output —
 * no runtime behavior change.
 */

export const GetBoardTypesSuccessExample = {
  success: true,
  code: 'BKN070000',
  message: '게시판 타입 조회 성공',
  data: [
    {
      id: 'd11f4479-e011-44d0-bc16-e3a602312fd5',
      name: 'feedback',
      description: '사내 테스트 피드백 게시판',
    },
  ],
};

export const CreatePostSuccessExample = {
  success: true,
  code: 'BKN070100',
  message: '게시글 처리 성공',
  data: {
    id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    boardTypeId: 'd11f4479-e011-44d0-bc16-e3a602312fd5',
    userId: 'u1b2c3d4-e5f6-7890-abcd-ef1234567890',
    userName: '홍길동',
    title: '서비스 사용 후기입니다',
    content: '전반적으로 만족스럽습니다.',
    hasImage: true,
    images: [
      {
        id: 'img-uuid',
        objectKey: 'board/feedback/2026/03/uuid/screenshot.png',
        originalFilename: 'screenshot.png',
        fileSize: 204800,
        mimeType: 'image/png',
        sortOrder: 0,
        viewUrl:
          'https://minio.example.com/rag-prod/board/feedback/2026/03/uuid/screenshot.png?X-Amz-Signature=...',
      },
    ],
    createdAt: '2026-03-20T10:00:00.000Z',
  },
};

export const GetPostListSuccessExample = {
  success: true,
  code: 'BKN070100',
  message: '게시글 처리 성공',
  data: {
    items: [
      {
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        boardTypeId: 'd11f4479-e011-44d0-bc16-e3a602312fd5',
        userId: 'u1b2c3d4-e5f6-7890-abcd-ef1234567890',
        userName: '홍길동',
        title: '서비스 사용 후기입니다',
        hasImage: false,
        isReplied: false,
        createdAt: '2026-03-20T10:00:00.000Z',
      },
    ],
    meta: {
      total: 42,
      page: 1,
      limit: 20,
      totalPages: 3,
    },
  },
};

export const GetPostDetailSuccessExample = {
  success: true,
  code: 'BKN070100',
  message: '게시글 처리 성공',
  data: {
    id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    boardTypeId: 'd11f4479-e011-44d0-bc16-e3a602312fd5',
    userId: 'u1b2c3d4-e5f6-7890-abcd-ef1234567890',
    userName: '홍길동',
    title: '서비스 사용 후기입니다',
    content:
      '전반적으로 만족스럽습니다. 특히 문서 검색 기능이 편리했습니다.',
    hasImage: true,
    isReplied: true,
    images: [
      {
        id: 'img-uuid',
        objectKey: 'board/feedback/2026/03/uuid/screenshot.png',
        originalFilename: 'screenshot.png',
        fileSize: 204800,
        mimeType: 'image/png',
        sortOrder: 0,
        viewUrl:
          'https://minio.example.com/rag-prod/board/feedback/2026/03/uuid/screenshot.png?X-Amz-Signature=...',
      },
    ],
    reply: {
      id: 'c1b2c3d4-e5f6-7890-abcd-ef1234567890',
      userId: 'admin-uuid',
      userName: '관리자',
      content: '피드백 감사합니다. 다음 업데이트에 반영하겠습니다.',
      createdAt: '2026-05-22T10:00:00.000Z',
    },
    createdAt: '2026-03-20T10:00:00.000Z',
  },
};

export const CreateReplySuccessExample = {
  success: true,
  code: 'BKN070400',
  message: '답변 등록 성공',
  data: {
    id: 'c1b2c3d4-e5f6-7890-abcd-ef1234567890',
    postId: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    userId: 'admin-uuid',
    userName: '관리자',
    content: '피드백 감사합니다. 다음 업데이트에 반영하겠습니다.',
    createdAt: '2026-05-22T10:00:00.000Z',
  },
};

export const GetPresignedUrlSuccessExample = {
  success: true,
  code: 'BKN070200',
  message: '업로드 URL 생성 성공',
  data: {
    uploadUrl:
      'https://minio.example.com/rag-prod/board/feedback/2026/03/uuid/screenshot.png?X-Amz-Signature=...',
    objectKey: 'board/feedback/2026/03/uuid/screenshot.png',
    expiresIn: 3600,
  },
};

export const SubmitSurveySuccessExample = {
  success: true,
  code: 'BKN070300',
  message: '설문 처리 성공',
  data: {
    id: 's1b2c3d4-e5f6-7890-abcd-ef1234567890',
    userId: 'u1b2c3d4-e5f6-7890-abcd-ef1234567890',
    loginUnderstand: 4,
    loginSimple: 5,
    homeIntuitive: 4,
    homeInputPosition: 3,
    homeNaturalStart: 4,
    chatSpeed: 5,
    chatEasy: 4,
    chatLength: 3,
    chatProcessHelpful: 5,
    sourceVisible: 4,
    sourceUiEasy: 4,
    sourceTrust: 3,
    docUploadEasy: 5,
    docStatusClear: 4,
    docAiKnowledge: 4,
    workHelpful: 5,
    workBetterThanLlm: 4,
    bestFeature: '문서 검색 기능이 가장 유용했습니다',
    worstFeature: '로딩 속도가 가끔 느렸습니다',
    freeComment: '전반적으로 만족합니다',
    createdAt: '2026-03-20T10:00:00.000Z',
  },
};
