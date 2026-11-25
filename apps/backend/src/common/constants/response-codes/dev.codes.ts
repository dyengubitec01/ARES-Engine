// ============================================================
// Dev (99) - 개발용 ⚠️ 프로덕션 배포 시 제거 고려
// ============================================================
export const DevResponseCode = {
  // 99-01: Redis Debug
  DEV_REDIS_HEALTH_SUCCESS: 'BKN990100',
  DEV_REDIS_KEYS_SUCCESS: 'BKN990100',
  DEV_REDIS_SESSION_SUCCESS: 'BKN990100',
  DEV_REDIS_SESSION_DELETED: 'BKN990100',
  DEV_REDIS_SESSION_RAW_SUCCESS: 'BKN990100',
} as const;

export const DevHttpStatus: Record<string, number> = {
  [DevResponseCode.DEV_REDIS_HEALTH_SUCCESS]: 200,
};

export const DevMessages: Record<string, string> = {
  [DevResponseCode.DEV_REDIS_HEALTH_SUCCESS]: '[DEV] Redis 처리 성공',
};
