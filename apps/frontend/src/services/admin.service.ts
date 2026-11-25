// created by ARES team [2026-01-12]
import apiClient from '../lib/apiClient';

// 사용자 권한 정보 인터페이스
interface Permission {
  permissionId: string;
  authorityId: string;
  authorityName: string;
}

// 부서 권한 정보
export interface DeptPermission {
  id: string;
  deptId: string;
  deptName: string;
  createdAt: string;
}

// 사용자 정보 인터페이스
export interface AdminUser {
  id: string;
  email: string;
  name: string;
  jobTitle: string | null;
  authorities: string[];
  permissions: Permission[];
  deptPermissions?: DeptPermission[];
  createdAt: string;
  department?: string;
}

// 시스템 권한
export interface Authority {
  id: string;
  authorityName: string;
  description: string;
  createdAt: string;
}

// 스토리지 문서 (레거시)
export interface StorageDocument {
  name: string;
  size: number;
  lastModified: string;
}

// 관리자용 전체 문서
export interface AdminDocument {
  id: string;
  title: string;
  createdBy: {
    id: string;
    name: string;
    email: string;
  };
  latestContent: {
    id: string;
    originalFilename: string;
    fileSize: number;
    status: string;
    createdAt: string;
  } | null;
  createdAt: string;
}

export interface PaginationMeta {
  page: number;
  limit: number;
  total: number;
}

// 부서 정보
export interface Department {
  id: string;
  deptName: string;
}

// API 응답
interface AdminUsersResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    items: AdminUser[];
    meta: PaginationMeta;
  };
}

interface AuthoritiesResponse {
  success: boolean;
  code: string;
  message: string;
  data: Authority[] | { items: Authority[]; meta: PaginationMeta };
}

interface StorageDocumentsResponse {
  success: boolean;
  code: string;
  message: string;
  data: StorageDocument[];
}

interface AdminDocumentsResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    items: AdminDocument[];
    meta: PaginationMeta;
  };
}

interface DepartmentsResponse {
  success: boolean;
  code: string;
  message: string;
  data: Department[];
}

interface ApiResponse {
  success: boolean;
  code: string;
  message: string;
}

// 사용자 활동 모니터링
export type ActivityType = 'chat' | 'upload' | 'feedback' | 'survey';
export type ActivityPeriod = 'intro' | 'expansion' | 'default';

export interface ActivityRankItem {
  rank: number;
  userId: string;
  name: string;
  department: string | null;
  jobTitle: string | null;
  totalScore: number;
  eligible: boolean;
  questionCount: number;
  uploadCount: number;
  otherCitationCount: number;
  lastActivityAt: string | null;
  lastActivityType: ActivityType | null;
}

export interface ActivityRankingMeta {
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export interface ActivityPersona {
  score: number;
  missedDays: number;
  threeDayStreakCount: number;
  fiveDayStreakCount: number;
  questionCount: number;
}

export interface ActivityHeritage {
  score: number;
  uploadCount: number;
  otherCitationCount: number;
  selfCitationCount: number;
}

export interface ActivityExpert {
  score: number;
  feedbackCount: number;
  answerSuggestionCount: number;
  adoptionScore: number;
}

export interface ActivityDetail {
  rank: number;
  userId: string;
  name: string;
  department: string | null;
  jobTitle: string | null;
  totalScore: number;
  eligible: boolean;
  period: ActivityPeriod;
  deptMultiplier: number;
  deptEligibleRatio: number;
  persona: ActivityPersona;
  heritage: ActivityHeritage;
  expert: ActivityExpert;
  lastActivityAt: string | null;
  lastActivityType: ActivityType | null;
  updatedAt: string;
}

interface ActivityRankingResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    items: ActivityRankItem[];
    meta: ActivityRankingMeta;
  };
}

interface ActivityDetailResponse {
  success: boolean;
  code: string;
  message: string;
  data: ActivityDetail;
}

interface ActivityRefreshResponse {
  success: boolean;
  code: string;
  message: string;
  data: { refreshedAt: string };
}

/**
 * 사용자 목록 조회 (관리자 전용)
 * @param page 페이지 번호
 * @param limit 페이지당 항목 수
 * @returns 사용자 목록 및 메타 정보
 */
export async function getAdminUsers(page = 1, limit = 10, search?: string): Promise<{ items: AdminUser[]; meta: PaginationMeta }> {
  const params: Record<string, string | number | undefined> = { page, limit };
  if (search) params.search = search;
  const response = await apiClient.get<AdminUsersResponse>('/admin/users', {
    params
  });

  if (response.data.success) {
    return response.data.data;
  } else {
    throw new Error(response.data.message || '사용자 목록 조회 실패');
  }
}

/**
 * 시스템 권한 목록 조회 (관리자 전용)
 * @returns 권한 목록
 */
export async function getAdminAuthorities(): Promise<Authority[]> {
  const response = await apiClient.get<AuthoritiesResponse>('/admin/authorities');

  if (response.data.success) {
    const resData = response.data.data;
    // 배열로 직접 오는 경우와 { items } 구조 모두 처리
    return Array.isArray(resData) ? resData : resData.items;
  } else {
    throw new Error(response.data.message || '권한 목록 조회 실패');
  }
}

/**
 * 사용자에게 권한 일괄 부여 (관리자 전용)
 * @param usersId 사용자 ID
 * @param authorityTypes 부여할 권한 타입 배열
 */
export async function grantAuthorities(usersId: string, authorityTypes: string[]): Promise<void> {
  const response = await apiClient.post<ApiResponse>('/admin/users/authorities', {
    usersId,
    authorityTypes
  });

  if (!response.data.success) {
    throw new Error(response.data.message || '권한 부여 실패');
  }
}

/**
 * 사용자 권한 일괄 회수 (관리자 전용)
 * @param usersId 사용자 ID
 * @param authorityTypes 회수할 권한 타입 배열
 */
export async function revokeAuthorities(usersId: string, authorityTypes: string[]): Promise<void> {
  const response = await apiClient.delete<ApiResponse>('/admin/users/authorities', {
    data: {
      usersId,
      authorityTypes
    }
  });

  if (!response.data.success) {
    throw new Error(response.data.message || '권한 회수 실패');
  }
}

/**
 * MinIO 스토리지 문서 목록 조회 (레거시, 사용 안 함)
 * @returns 스토리지 문서 목록
 */
export async function getStorageDocuments(): Promise<StorageDocument[]> {
  const response = await apiClient.get<StorageDocumentsResponse>('/documents/storage/list');

  if (response.data.success) {
    return response.data.data;
  } else {
    throw new Error(response.data.message || '스토리지 문서 목록 조회 실패');
  }
}

/**
 * 관리자용 전체 문서 목록 조회 (시스템 권한 필요)
 * @param page 페이지 번호
 * @param limit 페이지당 항목 수
 * @returns 전체 문서 목록 및 메타 정보
 */
export async function getAdminDocuments(page = 1, limit = 9, sort: 'latest' | 'oldest' = 'latest'): Promise<{ items: AdminDocument[]; meta: PaginationMeta }> {
  const response = await apiClient.get<AdminDocumentsResponse>('/admin/documents', {
    params: { page, limit, sort }
  });

  if (response.data.success) {
    return response.data.data;
  } else {
    throw new Error(response.data.message || '관리자 문서 목록 조회 실패');
  }
}

/**
 * 관리자용 문서 삭제 (Soft Delete)
 * @param documentId 문서 ID
 */
export async function softDeleteDocument(documentId: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse>(`/admin/documents/${documentId}/soft`);

  if (!response.data.success) {
    throw new Error(response.data.message || '문서 삭제 실패');
  }
}

/**
 * 관리자용 문서 삭제 (Hard Delete)
 * @param documentId 문서 ID
 */
export async function hardDeleteDocument(documentId: string): Promise<void> {
  const response = await apiClient.delete<ApiResponse>(`/admin/documents/${documentId}/hard`);

  if (!response.data.success) {
    throw new Error(response.data.message || '문서 영구 삭제 실패');
  }
}

/**
 * 전체 부서 목록 조회 (관리자 전용)
 * @returns 부서 목록
 */
export async function getAdminDepartments(): Promise<Department[]> {
  const response = await apiClient.get<DepartmentsResponse>('/admin/departments');

  if (response.data.success) {
    return response.data.data;
  } else {
    throw new Error(response.data.message || '부서 목록 조회 실패');
  }
}

/**
 * 사용자에게 부서 권한 추가 (관리자 전용)
 * @param userId 사용자 ID
 * @param deptIds 부서 ID 배열
 */
export async function updateDeptPermissions(userId: string, deptIds: string[]): Promise<void> {
  const response = await apiClient.put<ApiResponse>(`/admin/users/${userId}/dept-permissions`, {
    deptIds
  });

  if (!response.data.success) {
    throw new Error(response.data.message || '부서 권한 처리 실패');
  }
}

/**
 * 사용자 활동 랭킹 조회 (관리자 전용)
 */
export async function getActivityRanking(page = 1, limit = 20): Promise<{ items: ActivityRankItem[]; meta: ActivityRankingMeta }> {
  const response = await apiClient.get<ActivityRankingResponse>('/admin/activity', {
    params: { page, limit }
  });

  if (response.data.success) {
    return response.data.data;
  } else {
    throw new Error(response.data.message || '사용자 활동 랭킹 조회 실패');
  }
}

/**
 * 사용자 활동 상세 조회 (관리자 전용)
 */
export async function getActivityDetail(userId: string): Promise<ActivityDetail> {
  const response = await apiClient.get<ActivityDetailResponse>(`/admin/activity/${userId}`);

  if (response.data.success) {
    return response.data.data;
  } else {
    throw new Error(response.data.message || '사용자 활동 상세 조회 실패');
  }
}

/**
 * 사용자 활동 모니터링 수동 새로고침 (관리자 전용)
 */
export async function refreshActivity(): Promise<{ refreshedAt: string }> {
  const response = await apiClient.post<ActivityRefreshResponse>('/admin/activity/refresh');

  if (response.data.success) {
    return response.data.data;
  } else {
    throw new Error(response.data.message || '사용자 활동 새로고침 실패');
  }
}
