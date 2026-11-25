// ============================================================
// Embedding (05) - 임베딩/RAG
// ============================================================
export const EmbeddingResponseCode = {
  // 05-01: Request
  EMBED_REQUEST_ACCEPTED: 'BKN050100',
  EMBED_ALREADY_IN_PROGRESS: 'BKN050120',
  EMBED_INVALID_STATUS: 'BKN050121',
  EMBED_DOC_DELETED: 'BKN050122',
  EMBED_DOC_NOT_FOUND: 'BKN050123',
  // 05-02: Status
  EMBED_STATUS_SUCCESS: 'BKN050200',
  // 05-03: Approval List
  EMBED_APPROVAL_LIST_SUCCESS: 'BKN050300',
  // 05-04: Approve
  EMBED_APPROVE_SUCCESS: 'BKN050400',
  // 05-05: Reject
  EMBED_REJECT_SUCCESS: 'BKN050500',
  // 05-06: Re-embedding
  RE_EMBED_REQUEST_ACCEPTED: 'BKN050600',
} as const;

export const EmbeddingHttpStatus: Record<string, number> = {
  [EmbeddingResponseCode.EMBED_REQUEST_ACCEPTED]: 202,
  [EmbeddingResponseCode.EMBED_ALREADY_IN_PROGRESS]: 409,
  [EmbeddingResponseCode.EMBED_INVALID_STATUS]: 400,
  [EmbeddingResponseCode.EMBED_DOC_DELETED]: 410,
  [EmbeddingResponseCode.EMBED_DOC_NOT_FOUND]: 404,
  [EmbeddingResponseCode.EMBED_STATUS_SUCCESS]: 200,
  [EmbeddingResponseCode.EMBED_APPROVAL_LIST_SUCCESS]: 200,
  [EmbeddingResponseCode.EMBED_APPROVE_SUCCESS]: 200,
  [EmbeddingResponseCode.EMBED_REJECT_SUCCESS]: 200,
  [EmbeddingResponseCode.RE_EMBED_REQUEST_ACCEPTED]: 200,
};

export const EmbeddingMessages: Record<string, string> = {
  [EmbeddingResponseCode.EMBED_REQUEST_ACCEPTED]: '임베딩 요청이 접수되었습니다',
  [EmbeddingResponseCode.EMBED_ALREADY_IN_PROGRESS]:
    '이미 임베딩이 진행 중입니다',
  [EmbeddingResponseCode.EMBED_INVALID_STATUS]:
    '임베딩을 요청할 수 없는 상태입니다',
  [EmbeddingResponseCode.EMBED_DOC_DELETED]:
    '삭제된 문서는 임베딩을 요청할 수 없습니다',
  [EmbeddingResponseCode.EMBED_DOC_NOT_FOUND]:
    '임베딩 요청할 문서를 찾을 수 없습니다',
  [EmbeddingResponseCode.EMBED_STATUS_SUCCESS]: '임베딩 상태 조회 성공',
  [EmbeddingResponseCode.EMBED_APPROVAL_LIST_SUCCESS]:
    '임베딩 승인 대기 목록 조회 성공',
  [EmbeddingResponseCode.EMBED_APPROVE_SUCCESS]: '임베딩 요청이 승인되었습니다',
  [EmbeddingResponseCode.EMBED_REJECT_SUCCESS]: '임베딩 요청이 거절되었습니다',
  [EmbeddingResponseCode.RE_EMBED_REQUEST_ACCEPTED]:
    '재임베딩 요청이 접수되었습니다',
};
