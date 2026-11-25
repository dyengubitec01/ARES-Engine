/**
 * Swagger response/body example payloads for DocumentTagsController.
 *
 * Extracted from inline `@ApiResponse({ schema: { example: ... } })` blocks
 * to keep the controller focused on routing and authorization logic.
 * Editing these constants only affects generated OpenAPI/Swagger UI output —
 * no runtime behavior change.
 */

export const ListTagsSuccessExample = {
  success: true,
  code: 'BKN040900',
  message: '문서 태그 작업 성공',
  data: {
    items: [
      {
        id: '8c2f6e44-0a3b-4f3a-bf61-9c11d5e6a4b1',
        name: '재무',
        color: '#4caf50',
        createdAt: '2026-06-15T08:31:22.412Z',
        updatedAt: '2026-06-15T08:31:22.412Z',
      },
      {
        id: 'a91b9d23-7c5e-4d1f-9b2a-0e8f1234abcd',
        name: '중요',
        color: '#f44336',
        createdAt: '2026-06-15T08:32:01.005Z',
        updatedAt: '2026-06-15T08:32:01.005Z',
      },
    ],
  },
};

export const CreateTagSuccessExample = {
  success: true,
  code: 'BKN040900',
  message: '문서 태그 작업 성공',
  data: {
    id: '8c2f6e44-0a3b-4f3a-bf61-9c11d5e6a4b1',
    name: '재무',
    color: '#4caf50',
    createdAt: '2026-06-15T08:31:22.412Z',
    updatedAt: '2026-06-15T08:31:22.412Z',
  },
};

export const CreateTagDuplicateExample = {
  success: false,
  code: 'BKN040920',
  message: '같은 이름의 태그가 이미 존재합니다',
};

export const UpdateTagSuccessExample = {
  success: true,
  code: 'BKN040900',
  message: '문서 태그 작업 성공',
  data: {
    id: '8c2f6e44-0a3b-4f3a-bf61-9c11d5e6a4b1',
    name: '재무/회계',
    color: '#ff9800',
    createdAt: '2026-06-15T08:31:22.412Z',
    updatedAt: '2026-06-15T09:10:55.778Z',
  },
};

export const UpdateTagForbiddenExample = {
  success: false,
  code: 'BKN040922',
  message: '본인의 태그만 사용할 수 있습니다',
};

export const UpdateTagNotFoundExample = {
  success: false,
  code: 'BKN040921',
  message: '태그를 찾을 수 없습니다',
};

export const UpdateTagDuplicateExample = {
  success: false,
  code: 'BKN040920',
  message: '같은 이름의 태그가 이미 존재합니다',
};

export const DeleteTagSuccessExample = {
  success: true,
  code: 'BKN040900',
  message: '문서 태그 작업 성공',
  data: {
    tagId: '8c2f6e44-0a3b-4f3a-bf61-9c11d5e6a4b1',
  },
};

export const DeleteTagForbiddenExample = {
  success: false,
  code: 'BKN040922',
  message: '본인의 태그만 사용할 수 있습니다',
};

export const DeleteTagNotFoundExample = {
  success: false,
  code: 'BKN040921',
  message: '태그를 찾을 수 없습니다',
};
