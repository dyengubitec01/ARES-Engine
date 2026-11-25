// created by ARES team [2026-06-15]
import apiClient from '../lib/apiClient';

export interface DocumentTag {
  id: string;
  name: string;
  color: string;
  createdAt: string;
  updatedAt?: string;
}

export type DocumentTagSummary = Pick<DocumentTag, 'id' | 'name' | 'color'>;

interface CreateTagRequest {
  name: string;
  color: string;
}

interface TagResponse {
  success: boolean;
  code: string;
  message: string;
  data: DocumentTag;
}

export async function createDocumentTag(payload: CreateTagRequest): Promise<DocumentTag> {
  const response = await apiClient.post<TagResponse>('/document-tags', payload);
  return response.data.data;
}

interface GetTagsResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    items: DocumentTag[];
  };
}

export async function getDocumentTags(): Promise<DocumentTag[]> {
  const response = await apiClient.get<GetTagsResponse>('/document-tags');
  return response.data.data.items;
}

interface UpdateTagRequest {
  name?: string;
  color?: string;
}

export async function updateDocumentTag(tagId: string, payload: UpdateTagRequest): Promise<DocumentTag> {
  const response = await apiClient.patch<TagResponse>(`/document-tags/${tagId}`, payload);
  return response.data.data;
}

export async function deleteDocumentTag(tagId: string): Promise<void> {
  await apiClient.delete(`/document-tags/${tagId}`);
}

export async function assignTagsToDocument(documentId: string, tagIds: string[]): Promise<void> {
  await apiClient.put(`/documents/${documentId}/tags`, { tagIds });
}

interface CountResponse {
  data: {
    meta: { total: number };
  };
}

// 본인 권한 범위 내에서 해당 태그가 부여된 문서 개수를 조회.
// 본인 소유 태그는 본인 문서/접근 가능 부서 문서에만 부여되므로 view=all로 충분.
export async function countDocumentsByTag(tagId: string): Promise<number> {
  const params = new URLSearchParams();
  params.append('view', 'all');
  params.append('tagIds', tagId);
  params.append('limit', '1');
  params.append('page', '1');
  const response = await apiClient.get<CountResponse>('/documents', { params });
  return response.data?.data?.meta?.total ?? 0;
}
