/**
 * Swagger response/body example payloads for DocumentController.
 *
 * Extracted from inline `@ApiResponse({ schema: { example: ... } })` /
 * `@ApiBody({ examples: ... })` blocks to keep the controller focused on
 * routing and authorization logic. Editing these constants only affects
 * generated OpenAPI/Swagger UI output — no runtime behavior change.
 */

export const DocumentListSuccessExample = {
  success: true,
  code: 'BKN040200',
  message: '문서 조회 성공',
  data: {
    items: [
      {
        id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        title: '2026 1분기 업무 보고서',
        latestContent: {
          id: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
          versionNo: 1,
          originalFilename: '2026_Q1_report.pdf',
          fileSize: 1024000,
          mimeType: 'application/pdf',
          status: 'completed',
          statusReason: null,
          isEnabled: true,
          createdAt: '2026-03-20T09:00:00.000Z',
        },
        isFavorite: false,
        uploaderDepartment: '연구개발팀',
        failedCount: 0,
        myTags: [
          {
            id: '8c2f6e44-0a3b-4f3a-bf61-9c11d5e6a4b1',
            name: '재무',
            color: '#4caf50',
          },
        ],
        createdAt: '2026-03-20T09:00:00.000Z',
      },
    ],
    meta: { total: 50, page: 1, limit: 20, totalPages: 3 },
  },
};

export const DocumentSummarySuccessExample = {
  success: true,
  code: 'BKN040800',
  message: '내가 접근 가능한 모든 부서의 문서 요약 통계 조회 성공',
  data: {
    uploaded: 5,
    completed: 12,
    enabled: 8,
    pendingApproval: 0,
  },
};

export const StorageFileListSuccessExample = {
  success: true,
  code: 'BKN040500',
  message: '스토리지 파일 목록 조회 성공',
  data: {
    data: [
      {
        name: 'raw/2026/03/uuid/document.pdf',
        size: 1024000,
        lastModified: '2026-03-20T09:00:00.000Z',
      },
    ],
    bucket: 'rag-prod',
    prefix: 'raw/',
    count: 1,
  },
};

export const CreateUploadSessionBodyExamples = {
  singleFile: {
    summary: 'Single PDF file',
    value: {
      files: [
        {
          filename: 'document.pdf',
          mimeType: 'application/pdf',
          size: 1024000,
          fileModifiedAt: '2026-03-20T09:00:00.000Z',
          sha256:
            'a3f1c2e4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2',
        },
      ],
    },
  },
  multipleFiles: {
    summary: 'Multiple files',
    value: {
      files: [
        {
          filename: 'report.pdf',
          mimeType: 'application/pdf',
          size: 2048000,
          fileModifiedAt: '2026-03-20T09:00:00.000Z',
          sha256:
            'a3f1c2e4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2',
        },
        {
          filename: 'data.xlsx',
          mimeType:
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          size: 512000,
          fileModifiedAt: '2026-03-20T09:00:00.000Z',
          sha256:
            'b4e2d3f5c6a7b8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3',
        },
      ],
    },
  },
};

export const CreateUploadSessionSuccessExample = {
  success: true,
  code: 'BKN040100',
  message: '업로드 처리 성공',
  data: {
    documentId: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    uploads: [
      {
        filename: 'document.pdf',
        versionId: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
        uploadUrl:
          'https://minio.example.com/rag-prod/raw/2026/03/uuid/document.pdf?X-Amz-Signature=...',
        objectKey: 'raw/2026/03/uuid/document.pdf',
        expiresIn: 3600,
      },
    ],
  },
};

export const CompleteUploadSuccessExample = {
  success: true,
  code: 'BKN040100',
  message: '업로드 처리 성공',
  data: {
    documentId: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    versionId: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
    status: 'uploaded',
  },
};

export const BulkRequestEmbeddingApprovalSuccessExample = {
  success: true,
  code: 'BKN050100',
  message: '임베딩 승인 요청이 처리되었습니다',
  data: {
    results: [
      {
        versionId: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
        documentId: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        status: 'pending_approval',
      },
      {
        versionId: 'v2b2c3d4-e5f6-7890-abcd-ef1234567890',
        status: 'error',
        error: '이미 임베딩이 진행 중이거나 완료된 문서입니다',
      },
    ],
  },
};

export const BulkRequestReEmbeddingSuccessExample = {
  success: true,
  code: 'BKN050600',
  message: '재임베딩 요청이 접수되었습니다',
  data: {
    results: [
      {
        versionId: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
        documentId: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        status: 'failed',
      },
      {
        versionId: 'v2b2c3d4-e5f6-7890-abcd-ef1234567890',
        status: 'error',
        error: '재임베딩은 failed/completed 상태에서만 가능합니다',
      },
    ],
  },
};

export const GetEmbedRequestsSuccessExample = {
  success: true,
  code: 'BKN050300',
  message: '임베딩 승인 대기 목록 조회 성공',
  data: {
    items: [
      {
        versionId: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
        documentId: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
        title: '2026 1분기 업무 보고서',
        versionNo: 1,
        filename: '2026_1분기_업무보고서.pdf',
        fileSize: 1024000,
        mimeType: 'application/pdf',
        status: 'pending_approval',
        statusReason: null,
        uploaderName: '홍길동',
        uploaderDepartment: '연구개발팀',
        reviewerName: null,
        requestedAt: '2026-04-08T09:00:00.000Z',
        createdAt: '2026-04-08T08:00:00.000Z',
        reviewHistory: [
          {
            reviewerName: '홍길동',
            action: 'reject',
            reason: '내용 보완 필요',
            reviewedAt: '2026-04-07T15:00:00.000Z',
          },
        ],
      },
    ],
    meta: { total: 5, page: 1, limit: 20, totalPages: 1 },
  },
};

export const BulkApproveEmbeddingSuccessExample = {
  success: true,
  code: 'BKN050400',
  message: '임베딩 요청이 승인되었습니다',
  data: {
    results: [
      {
        versionId: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
        status: 'queued',
      },
      {
        versionId: 'v2b2c3d4-e5f6-7890-abcd-ef1234567890',
        status: 'error',
        error: '대기 중인 임베딩 요청이 아닙니다',
      },
    ],
  },
};

export const BulkRejectEmbeddingSuccessExample = {
  success: true,
  code: 'BKN050500',
  message: '임베딩 요청이 거절되었습니다',
  data: {
    results: [
      {
        versionId: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
        status: 'rejected',
      },
      {
        versionId: 'v2b2c3d4-e5f6-7890-abcd-ef1234567890',
        status: 'error',
        error: '대기 중인 임베딩 요청이 아닙니다',
      },
    ],
  },
};

export const DocumentDetailSuccessExample = {
  success: true,
  code: 'BKN040200',
  message: '문서 조회 성공',
  data: {
    id: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
    title: '2026 1분기 업무 보고서',
    createdBy: 'u1b2c3d4-e5f6-7890-abcd-ef1234567890',
    createdAt: '2026-03-20T09:00:00.000Z',
    versions: [
      {
        id: 'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
        versionNo: 1,
        originalFilename: '2026_Q1_report.pdf',
        fileSize: 1024000,
        mimeType: 'application/pdf',
        status: 'completed',
        statusReason: null,
        queuedAt: '2026-03-20T09:01:00.000Z',
        startedAt: '2026-03-20T09:01:05.000Z',
        finishedAt: '2026-03-20T09:01:30.000Z',
        createdAt: '2026-03-20T09:00:00.000Z',
      },
    ],
    isFavorite: false,
  },
};

export const ToggleReferenceSuccessExample = {
  success: true,
  code: 'BKN040700',
  message: '문서 참조 설정 변경 성공',
  data: {
    isEnabled: true,
  },
};

export const DownloadUrlSuccessExample = {
  success: true,
  code: 'BKN040600',
  message: '다운로드 URL 생성 성공',
  data: {
    downloadUrl:
      'https://minio.example.com/rag-prod/raw/2026/03/uuid/document.pdf?X-Amz-Signature=...',
    expiresIn: 3600,
  },
};

export const AddFavoriteSuccessExample = {
  success: true,
  code: 'BKN040400',
  message: '즐겨찾기 처리 성공',
  data: {
    message: '즐겨찾기에 추가되었습니다',
  },
};

export const RemoveFavoriteSuccessExample = {
  success: true,
  code: 'BKN040400',
  message: '즐겨찾기 처리 성공',
  data: {
    message: '즐겨찾기가 해제되었습니다',
  },
};

export const SetDocumentTagsSuccessExample = {
  success: true,
  code: 'BKN040900',
  message: '문서 태그 작업 성공',
  data: {
    documentId: 'd3a1c8e0-1234-4abc-9def-9f12abcd5678',
    myTags: [
      {
        id: '8c2f6e44-0a3b-4f3a-bf61-9c11d5e6a4b1',
        name: '재무',
        color: '#4caf50',
      },
      {
        id: 'a91b9d23-7c5e-4d1f-9b2a-0e8f1234abcd',
        name: '중요',
        color: '#f44336',
      },
    ],
  },
};

export const SetDocumentTagsForbiddenExample = {
  success: false,
  code: 'BKN040923',
  message: '해당 문서에 태그를 부여할 권한이 없습니다',
};

export const SetDocumentTagsNotFoundExample = {
  success: false,
  code: 'BKN040921',
  message: '태그를 찾을 수 없습니다',
};
