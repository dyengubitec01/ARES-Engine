/**
 * Swagger response/body example payloads for ChatController.
 *
 * Extracted from inline `@ApiResponse({ schema: { example: ... } })` blocks
 * to keep the controller focused on routing and authorization logic.
 * Editing these constants only affects generated OpenAPI/Swagger UI output —
 * no runtime behavior change.
 */

export const HealthCheckSuccessExample = {
  success: true,
  code: 'BKN020500',
  message: '헬스체크 완료',
  data: { chatbot: true },
};

export const GetSessionsSuccessExample = {
  success: true,
  code: 'BKN020100',
  message: '채팅 세션 처리 성공',
  data: {
    items: [
      {
        id: 's1b2c3d4-e5f6-7890-abcd-ef1234567890',
        title: '문서 검색 방법 문의',
        favorites: 'N',
        createdAt: '2026-03-20T09:00:00.000Z',
        updatedAt: '2026-03-20T09:30:00.000Z',
      },
    ],
    nextCursor: null,
    hasMore: false,
  },
};

export const GetSessionSuccessExample = {
  success: true,
  code: 'BKN020100',
  message: '채팅 세션 처리 성공',
  data: {
    id: 's1b2c3d4-e5f6-7890-abcd-ef1234567890',
    title: '문서 검색 방법 문의',
    favorites: 'N',
    createdAt: '2026-03-20T09:00:00.000Z',
    updatedAt: '2026-03-20T09:30:00.000Z',
  },
};

export const UpdateSessionSuccessExample = {
  success: true,
  code: 'BKN020100',
  message: '채팅 세션 처리 성공',
  data: {
    id: 's1b2c3d4-e5f6-7890-abcd-ef1234567890',
    title: '새 채팅방 제목',
  },
};

export const ToggleFavoriteSuccessExample = {
  success: true,
  code: 'BKN020100',
  message: '채팅 세션 처리 성공',
  data: {
    id: 's1b2c3d4-e5f6-7890-abcd-ef1234567890',
    title: '문서 검색 방법 문의',
    favorites: 'Y',
  },
};

export const DeleteSessionSuccessExample = {
  success: true,
  code: 'BKN020100',
  message: '채팅 세션 처리 성공',
  data: { message: '채팅방이 삭제되었습니다' },
};

export const GetMessagesSuccessExample = {
  success: true,
  code: 'BKN020200',
  message: '대화 내역 처리 성공',
  data: {
    items: [
      {
        id: 'i1b2c3d4-e5f6-7890-abcd-ef1234567890',
        type: 'Q',
        content: '문서 검색은 어떻게 하나요?',
        chatTurn: 1,
        feedback: null,
        createdAt: '2026-03-20T09:05:00.000Z',
      },
      {
        id: 'i2b2c3d4-e5f6-7890-abcd-ef1234567890',
        type: 'A',
        content: '문서 검색은 상단 검색창에서...',
        chatTurn: 1,
        feedback: 'Y',
        createdAt: '2026-03-20T09:05:03.000Z',
      },
    ],
    nextCursor: null,
    hasMore: false,
  },
};

export const SendPromptSseExample = {
  type: 'message',
  data: '{"event":"message","content":"안녕하세요"}',
};

export const ToggleFeedbackSuccessExample = {
  success: true,
  code: 'BKN020300',
  message: '피드백 처리 성공',
  data: {
    interactionId: 'i2b2c3d4-e5f6-7890-abcd-ef1234567890',
    feedback: 'Y',
  },
};

export const GetDocumentReferencesSuccessExample = {
  success: true,
  code: 'BKN020400',
  message: '문서 참조 처리 성공',
  data: [
    {
      id: 'r1b2c3d4-e5f6-7890-abcd-ef1234567890',
      documentContentId: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
      documentTitle: '2026 1분기 업무 보고서',
      relevance: 0.95,
      location: '3페이지',
    },
  ],
};

export const AddDocumentReferenceSuccessExample = {
  success: true,
  code: 'BKN020400',
  message: '문서 참조 처리 성공',
  data: {
    id: 'r1b2c3d4-e5f6-7890-abcd-ef1234567890',
    documentContentId: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
    documentTitle: '2026 1분기 업무 보고서',
    relevance: 0,
    location: null,
  },
};

export const DeleteDocumentReferenceSuccessExample = {
  success: true,
  code: 'BKN020400',
  message: '문서 참조 처리 성공',
  data: { deleted: true },
};
