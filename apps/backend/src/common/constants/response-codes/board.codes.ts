// ============================================================
// Board (07) - 게시판
// ============================================================
export const BoardResponseCode = {
  // 07-00: Type
  BOARD_TYPE_LIST_SUCCESS: 'BKN070000',
  // 07-01: Post
  BOARD_POST_CREATED: 'BKN070100',
  BOARD_POST_LIST_SUCCESS: 'BKN070100',
  BOARD_POST_DETAIL_SUCCESS: 'BKN070100',
  BOARD_POST_NOT_FOUND: 'BKN070120',
  BOARD_IMAGE_NOT_UPLOADED: 'BKN070130',
  // 07-02: Image / Presigned URL
  BOARD_PRESIGNED_URL_SUCCESS: 'BKN070200',
  // 07-03: Survey
  BOARD_SURVEY_SUBMITTED: 'BKN070300',
  BOARD_SURVEY_DUPLICATE: 'BKN070320',
  // 07-04: Reply (답변)
  BOARD_REPLY_CREATED: 'BKN070400',
  BOARD_REPLY_ALREADY_EXISTS: 'BKN070420',
} as const;

export const BoardHttpStatus: Record<string, number> = {
  [BoardResponseCode.BOARD_TYPE_LIST_SUCCESS]: 200,
  [BoardResponseCode.BOARD_POST_CREATED]: 200,
  [BoardResponseCode.BOARD_POST_NOT_FOUND]: 404,
  [BoardResponseCode.BOARD_IMAGE_NOT_UPLOADED]: 400,
  [BoardResponseCode.BOARD_PRESIGNED_URL_SUCCESS]: 200,
  [BoardResponseCode.BOARD_SURVEY_SUBMITTED]: 200,
  [BoardResponseCode.BOARD_SURVEY_DUPLICATE]: 409,
  [BoardResponseCode.BOARD_REPLY_CREATED]: 201,
  [BoardResponseCode.BOARD_REPLY_ALREADY_EXISTS]: 409,
};

export const BoardMessages: Record<string, string> = {
  [BoardResponseCode.BOARD_TYPE_LIST_SUCCESS]: '게시판 타입 조회 성공',
  [BoardResponseCode.BOARD_POST_CREATED]: '게시글 처리 성공',
  [BoardResponseCode.BOARD_POST_NOT_FOUND]: '게시글을 찾을 수 없습니다',
  [BoardResponseCode.BOARD_IMAGE_NOT_UPLOADED]:
    '업로드되지 않은 이미지가 있습니다',
  [BoardResponseCode.BOARD_PRESIGNED_URL_SUCCESS]: '업로드 URL 생성 성공',
  [BoardResponseCode.BOARD_SURVEY_SUBMITTED]: '설문 처리 성공',
  [BoardResponseCode.BOARD_SURVEY_DUPLICATE]: '이미 설문을 제출한 사용자입니다',
  [BoardResponseCode.BOARD_REPLY_CREATED]: '답변 등록 성공',
  [BoardResponseCode.BOARD_REPLY_ALREADY_EXISTS]: '이미 답변이 존재합니다',
};
