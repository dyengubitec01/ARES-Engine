// ============================================================
// Document (04) - 문서 관리
// ============================================================
export const DocumentResponseCode = {
  // 04-01: Upload
  DOC_UPLOAD_SESSION_CREATED: 'BKN040100',
  DOC_UPLOAD_COMPLETE: 'BKN040101',
  DOC_UPLOAD_SIZE_EXCEEDED: 'BKN040120',
  DOC_UPLOAD_UNSUPPORTED_TYPE: 'BKN040121',
  DOC_UPLOAD_FAILED: 'BKN040122',
  DOC_UPLOAD_DUPLICATE: 'BKN040123',
  DOC_UPLOAD_NOT_FOUND_IN_STORAGE: 'BKN040124',
  // 04-02: List/Detail
  DOC_LIST_SUCCESS: 'BKN040200',
  DOC_DETAIL_SUCCESS: 'BKN040201',
  DOC_NOT_FOUND: 'BKN040220',
  DOC_FORBIDDEN: 'BKN040221',
  // 04-03: Delete
  DOC_DELETE_SUCCESS: 'BKN040300',
  DOC_DELETE_FORBIDDEN: 'BKN040320',
  // 04-04: Favorite
  DOC_FAVORITE_ADDED: 'BKN040400',
  DOC_FAVORITE_REMOVED: 'BKN040400',
  DOC_FAVORITE_DUPLICATE: 'BKN040420',
  DOC_FAVORITE_NOT_FOUND: 'BKN040421',
  // 04-05: Storage
  DOC_STORAGE_LIST_SUCCESS: 'BKN040500',
  // 04-06: Download
  DOC_DOWNLOAD_URL_SUCCESS: 'BKN040600',
  DOC_DOWNLOAD_FORBIDDEN: 'BKN040620',
  // 04-07: Reference Toggle
  DOC_REFERENCE_TOGGLED: 'BKN040700',
  DOC_REFERENCE_NOT_FOUND: 'BKN040720',
  // 04-08: Summary
  DOC_SUMMARY_SUCCESS: 'BKN040800',
  // 04-09: User Tags
  DOC_TAG_SUCCESS: 'BKN040900',
  DOC_TAG_DUPLICATE: 'BKN040920',
  DOC_TAG_NOT_FOUND: 'BKN040921',
  DOC_TAG_FORBIDDEN: 'BKN040922',
  DOC_TAG_DOCUMENT_FORBIDDEN: 'BKN040923',
} as const;

export const DocumentHttpStatus: Record<string, number> = {
  [DocumentResponseCode.DOC_UPLOAD_SESSION_CREATED]: 201,
  [DocumentResponseCode.DOC_UPLOAD_COMPLETE]: 200,
  [DocumentResponseCode.DOC_UPLOAD_SIZE_EXCEEDED]: 413,
  [DocumentResponseCode.DOC_UPLOAD_UNSUPPORTED_TYPE]: 415,
  [DocumentResponseCode.DOC_UPLOAD_FAILED]: 500,
  [DocumentResponseCode.DOC_UPLOAD_DUPLICATE]: 409,
  [DocumentResponseCode.DOC_UPLOAD_NOT_FOUND_IN_STORAGE]: 400,
  [DocumentResponseCode.DOC_LIST_SUCCESS]: 200,
  [DocumentResponseCode.DOC_DETAIL_SUCCESS]: 200,
  [DocumentResponseCode.DOC_NOT_FOUND]: 404,
  [DocumentResponseCode.DOC_FORBIDDEN]: 403,
  [DocumentResponseCode.DOC_DELETE_SUCCESS]: 200,
  [DocumentResponseCode.DOC_DELETE_FORBIDDEN]: 403,
  [DocumentResponseCode.DOC_FAVORITE_ADDED]: 201,
  [DocumentResponseCode.DOC_FAVORITE_DUPLICATE]: 409,
  [DocumentResponseCode.DOC_FAVORITE_NOT_FOUND]: 404,
  [DocumentResponseCode.DOC_STORAGE_LIST_SUCCESS]: 200,
  [DocumentResponseCode.DOC_DOWNLOAD_URL_SUCCESS]: 200,
  [DocumentResponseCode.DOC_DOWNLOAD_FORBIDDEN]: 403,
  [DocumentResponseCode.DOC_REFERENCE_TOGGLED]: 200,
  [DocumentResponseCode.DOC_REFERENCE_NOT_FOUND]: 404,
  [DocumentResponseCode.DOC_SUMMARY_SUCCESS]: 200,
  [DocumentResponseCode.DOC_TAG_SUCCESS]: 200,
  [DocumentResponseCode.DOC_TAG_DUPLICATE]: 409,
  [DocumentResponseCode.DOC_TAG_NOT_FOUND]: 404,
  [DocumentResponseCode.DOC_TAG_FORBIDDEN]: 403,
  [DocumentResponseCode.DOC_TAG_DOCUMENT_FORBIDDEN]: 403,
};

export const DocumentMessages: Record<string, string> = {
  [DocumentResponseCode.DOC_UPLOAD_SESSION_CREATED]: '업로드 세션 생성 성공',
  [DocumentResponseCode.DOC_UPLOAD_COMPLETE]: '업로드 완료 처리 성공',
  [DocumentResponseCode.DOC_UPLOAD_SIZE_EXCEEDED]:
    '파일 크기가 제한을 초과했습니다',
  [DocumentResponseCode.DOC_UPLOAD_UNSUPPORTED_TYPE]:
    '지원하지 않는 파일 형식입니다',
  [DocumentResponseCode.DOC_UPLOAD_FAILED]: '업로드에 실패했습니다',
  [DocumentResponseCode.DOC_UPLOAD_DUPLICATE]: '이미 동일한 파일이 존재합니다',
  [DocumentResponseCode.DOC_UPLOAD_NOT_FOUND_IN_STORAGE]:
    '파일이 스토리지에 업로드되지 않았습니다',
  [DocumentResponseCode.DOC_LIST_SUCCESS]: '문서 목록 조회 성공',
  [DocumentResponseCode.DOC_DETAIL_SUCCESS]: '문서 상세 조회 성공',
  [DocumentResponseCode.DOC_NOT_FOUND]: '문서를 찾을 수 없습니다',
  [DocumentResponseCode.DOC_FORBIDDEN]: '문서에 대한 권한이 없습니다',
  [DocumentResponseCode.DOC_DELETE_SUCCESS]: '문서 삭제 성공',
  [DocumentResponseCode.DOC_DELETE_FORBIDDEN]: '문서 삭제 권한이 없습니다',
  [DocumentResponseCode.DOC_FAVORITE_ADDED]: '즐겨찾기 처리 성공',
  [DocumentResponseCode.DOC_FAVORITE_DUPLICATE]: '이미 즐겨찾기된 문서입니다',
  [DocumentResponseCode.DOC_FAVORITE_NOT_FOUND]:
    '즐겨찾기 목록에 없는 문서입니다',
  [DocumentResponseCode.DOC_STORAGE_LIST_SUCCESS]:
    '스토리지 파일 목록 조회 성공',
  [DocumentResponseCode.DOC_DOWNLOAD_URL_SUCCESS]: '다운로드 URL 생성 성공',
  [DocumentResponseCode.DOC_DOWNLOAD_FORBIDDEN]: '문서 다운로드 권한이 없습니다',
  [DocumentResponseCode.DOC_REFERENCE_TOGGLED]: '문서 참조 설정 변경 성공',
  [DocumentResponseCode.DOC_REFERENCE_NOT_FOUND]:
    '해당 문서 버전을 찾을 수 없습니다',
  [DocumentResponseCode.DOC_SUMMARY_SUCCESS]:
    '내가 접근 가능한 모든 부서의 문서 요약 통계 조회 성공',
  [DocumentResponseCode.DOC_TAG_SUCCESS]: '문서 태그 작업 성공',
  [DocumentResponseCode.DOC_TAG_DUPLICATE]: '같은 이름의 태그가 이미 존재합니다',
  [DocumentResponseCode.DOC_TAG_NOT_FOUND]: '태그를 찾을 수 없습니다',
  [DocumentResponseCode.DOC_TAG_FORBIDDEN]: '본인의 태그만 사용할 수 있습니다',
  [DocumentResponseCode.DOC_TAG_DOCUMENT_FORBIDDEN]:
    '해당 문서에 태그를 부여할 권한이 없습니다',
};
