// ============================================================
// Event / Alarm (06) - SSE / 알림
// ============================================================
export const EventAlarmResponseCode = {
  // 06-01: Subscribe
  EVENT_SUBSCRIBE_SUCCESS: 'BKN060100',
  EVENT_CONNECTION_CLOSED: 'BKN060100',
  // 06-02: Notification
  EVENT_NOTIFICATION_SUCCESS: 'BKN060200',
  // 06-03: Alarm
  ALARM_LIST_SUCCESS: 'BKN060300',
  ALARM_READ_SUCCESS: 'BKN060300',
  ALARM_DELETE_SUCCESS: 'BKN060301',
  ALARM_NOT_FOUND: 'BKN060320',
} as const;

export const EventAlarmHttpStatus: Record<string, number> = {
  [EventAlarmResponseCode.EVENT_SUBSCRIBE_SUCCESS]: 200,
  [EventAlarmResponseCode.EVENT_NOTIFICATION_SUCCESS]: 200,
  [EventAlarmResponseCode.ALARM_LIST_SUCCESS]: 200,
  [EventAlarmResponseCode.ALARM_DELETE_SUCCESS]: 200,
  [EventAlarmResponseCode.ALARM_NOT_FOUND]: 404,
};

export const EventAlarmMessages: Record<string, string> = {
  [EventAlarmResponseCode.EVENT_SUBSCRIBE_SUCCESS]: 'SSE 처리 성공',
  [EventAlarmResponseCode.EVENT_NOTIFICATION_SUCCESS]: '알림 전송 성공',
  [EventAlarmResponseCode.ALARM_LIST_SUCCESS]: '알림 처리 성공',
  [EventAlarmResponseCode.ALARM_DELETE_SUCCESS]: '알림 삭제 성공',
  [EventAlarmResponseCode.ALARM_NOT_FOUND]: '알림을 찾을 수 없습니다',
};
