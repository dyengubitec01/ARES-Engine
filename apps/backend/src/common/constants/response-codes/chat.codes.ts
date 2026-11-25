// ============================================================
// Chat (02) - 채팅/대화
// ============================================================
export const ChatResponseCode = {
  // 02-01: Session
  CHAT_SESSION_CREATED: 'BKN020100',
  CHAT_SESSION_FOUND: 'BKN020101',
  CHAT_SESSION_LIST_SUCCESS: 'BKN020102',
  CHAT_SESSION_UPDATED: 'BKN020103',
  CHAT_SESSION_DELETED: 'BKN020104',
  CHAT_SESSION_FAVORITE_TOGGLED: 'BKN020105',
  CHAT_SESSION_NOT_FOUND: 'BKN020120',
  CHAT_SESSION_FORBIDDEN: 'BKN020121',
  // 02-02: Interaction
  CHAT_INTERACTION_SUCCESS: 'BKN020200',
  CHAT_INTERACTION_NOT_FOUND: 'BKN020220',
  CHAT_INTERACTION_FORBIDDEN: 'BKN020221',
  // 02-03: Feedback
  CHAT_FEEDBACK_SUCCESS: 'BKN020300',
  CHAT_FEEDBACK_INVALID_TYPE: 'BKN020320',
  // 02-04: Document Reference (RAG)
  CHAT_DOC_REF_ADDED: 'BKN020400',
  CHAT_DOC_REF_DELETED: 'BKN020400',
  CHAT_DOC_REF_LIST_SUCCESS: 'BKN020400',
  CHAT_DOC_REF_NOT_FOUND: 'BKN020420',
  CHAT_DOC_REF_FORBIDDEN: 'BKN020421',
  // 02-05: Health
  CHAT_HEALTH_SUCCESS: 'BKN020500',
} as const;

export const ChatHttpStatus: Record<string, number> = {
  [ChatResponseCode.CHAT_SESSION_CREATED]: 201,
  [ChatResponseCode.CHAT_SESSION_FOUND]: 200,
  [ChatResponseCode.CHAT_SESSION_LIST_SUCCESS]: 200,
  [ChatResponseCode.CHAT_SESSION_UPDATED]: 200,
  [ChatResponseCode.CHAT_SESSION_DELETED]: 200,
  [ChatResponseCode.CHAT_SESSION_FAVORITE_TOGGLED]: 200,
  [ChatResponseCode.CHAT_SESSION_NOT_FOUND]: 404,
  [ChatResponseCode.CHAT_SESSION_FORBIDDEN]: 403,
  [ChatResponseCode.CHAT_INTERACTION_SUCCESS]: 200,
  [ChatResponseCode.CHAT_INTERACTION_NOT_FOUND]: 404,
  [ChatResponseCode.CHAT_INTERACTION_FORBIDDEN]: 403,
  [ChatResponseCode.CHAT_FEEDBACK_SUCCESS]: 200,
  [ChatResponseCode.CHAT_FEEDBACK_INVALID_TYPE]: 400,
  [ChatResponseCode.CHAT_DOC_REF_ADDED]: 201,
  [ChatResponseCode.CHAT_DOC_REF_NOT_FOUND]: 404,
  [ChatResponseCode.CHAT_DOC_REF_FORBIDDEN]: 403,
  [ChatResponseCode.CHAT_HEALTH_SUCCESS]: 200,
};

export const ChatMessages: Record<string, string> = {
  [ChatResponseCode.CHAT_SESSION_CREATED]: '채팅 세션 생성 성공',
  [ChatResponseCode.CHAT_SESSION_FOUND]: '채팅 세션 조회 성공',
  [ChatResponseCode.CHAT_SESSION_LIST_SUCCESS]: '채팅 세션 목록 조회 성공',
  [ChatResponseCode.CHAT_SESSION_UPDATED]: '채팅 세션 수정 성공',
  [ChatResponseCode.CHAT_SESSION_DELETED]: '채팅 세션 삭제 성공',
  [ChatResponseCode.CHAT_SESSION_FAVORITE_TOGGLED]:
    '채팅 세션 즐겨찾기 변경 성공',
  [ChatResponseCode.CHAT_SESSION_NOT_FOUND]: '채팅방을 찾을 수 없습니다',
  [ChatResponseCode.CHAT_SESSION_FORBIDDEN]: '채팅방의 소유자가 아닙니다',
  [ChatResponseCode.CHAT_INTERACTION_SUCCESS]: '대화 내역 처리 성공',
  [ChatResponseCode.CHAT_INTERACTION_NOT_FOUND]: '대화 내역을 찾을 수 없습니다',
  [ChatResponseCode.CHAT_INTERACTION_FORBIDDEN]: '채팅방의 소유자가 아닙니다',
  [ChatResponseCode.CHAT_FEEDBACK_SUCCESS]: '피드백 처리 성공',
  [ChatResponseCode.CHAT_FEEDBACK_INVALID_TYPE]:
    '답변에만 피드백을 남길 수 있습니다',
  [ChatResponseCode.CHAT_DOC_REF_ADDED]: '문서 참조 처리 성공',
  [ChatResponseCode.CHAT_DOC_REF_NOT_FOUND]: '문서 참조를 찾을 수 없습니다',
  [ChatResponseCode.CHAT_DOC_REF_FORBIDDEN]: '문서 참조에 대한 권한이 없습니다',
  [ChatResponseCode.CHAT_HEALTH_SUCCESS]: '헬스체크 완료',
};
