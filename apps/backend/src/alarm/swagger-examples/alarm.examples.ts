/**
 * Swagger response/body example payloads for AlarmController.
 *
 * Extracted from inline `@ApiResponse({ schema: { example: ... } })` blocks
 * to keep the controller focused on routing and authorization logic.
 * Editing these constants only affects generated OpenAPI/Swagger UI output —
 * no runtime behavior change.
 */

export const GetAlarmsSuccessExample = {
  success: true,
  code: 'BKN060300',
  message: '알림 조회 성공',
  data: {
    items: [
      {
        id: 'n1b2c3d4-e5f6-7890-abcd-ef1234567890',
        type: 'EMBED_COMPLETE',
        title: '임베딩 완료',
        body: '"2026 1분기 업무 보고서" 문서의 임베딩이 완료되었습니다.',
        isRead: false,
        createdAt: '2026-03-20T09:01:30.000Z',
      },
    ],
    meta: { total: 5, page: 1, limit: 20, totalPages: 1 },
  },
};

export const GetUnreadCountSuccessExample = {
  success: true,
  code: 'BKN060300',
  message: '알림 조회 성공',
  data: { count: 3 },
};

export const MarkAsReadSuccessExample = {
  success: true,
  code: 'BKN060300',
  message: '알림 조회 성공',
  data: {
    id: 'n1b2c3d4-e5f6-7890-abcd-ef1234567890',
    isRead: true,
    updatedAt: '2026-03-20T10:00:00.000Z',
  },
};

export const MarkAllAsReadSuccessExample = {
  success: true,
  code: 'BKN060300',
  message: '알림 조회 성공',
  data: { affected: 3 },
};

export const DeleteAlarmSuccessExample = {
  success: true,
  code: 'BKN060301',
  message: '알림 삭제 성공',
  data: { message: '알림이 삭제되었습니다' },
};
