// created by ARES team [2026-03-19]
import apiClient from '../lib/apiClient';

interface DownloadUrlResponse {
  success: boolean;
  data: {
    downloadUrl: string;
  };
}

/**
 * 문서 파일 다운로드
 * @param versionId 문서 버전 ID
 * @param fileName 다운로드할 파일명
 */
export const downloadFile = async (versionId: string, fileName: string): Promise<void> => {
  const response = await apiClient.get<DownloadUrlResponse>(`/documents/versions/${versionId}/download`);

  const downloadUrl = response.data.data.downloadUrl;

  if (!downloadUrl) {
    throw new Error('다운로드 URL을 받지 못했습니다.');
  }

  const link = document.createElement('a');
  link.href = downloadUrl;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};

/**
 * 문서 RAG 참조 ON/OFF 토글
 * @param contentId 문서 버전(latestContent) ID
 */
export const toggleDocumentReference = async (contentId: string): Promise<void> => {
  await apiClient.patch(`/documents/versions/${contentId}/reference`);
};

interface EmbedRequestResult {
  versionId: string;
  status: string;
  error?: string;
}

interface ApproveEmbedRequestsResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    results: EmbedRequestResult[];
  };
}

interface RejectEmbedRequestItem {
  versionId: string;
  reason: string;
}

interface RejectEmbedRequestsResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    results: EmbedRequestResult[];
  };
}

/**
 * 임베딩 요청 반려 (단일/일괄)
 * @param items 반려할 문서 버전 ID와 사유 배열
 */
export const rejectEmbedRequests = async (items: RejectEmbedRequestItem[]): Promise<RejectEmbedRequestsResponse> => {
  const response = await apiClient.patch<RejectEmbedRequestsResponse>('/documents/embed-requests/reject', {
    items,
  });
  return response.data;
};

/**
 * 임베딩 요청 승인 (단일/일괄)
 * @param versionIds 승인할 문서 버전 ID 배열
 */
export const approveEmbedRequests = async (versionIds: string[]): Promise<ApproveEmbedRequestsResponse> => {
  const response = await apiClient.patch<ApproveEmbedRequestsResponse>('/documents/embed-requests', {
    versionIds,
  });
  return response.data;
};
