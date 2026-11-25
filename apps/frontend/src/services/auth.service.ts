// created by ARES team [2026-01-07]
import apiClient from '../lib/apiClient';
import { createCustomError } from '../lib/customError';
import { AUTH_CODES } from '../constants/customCodes';

interface LoginUrlResponse {
  url: string;
  state: string;
}

interface LoginUrlApiResponse {
  data?: LoginUrlResponse;
  url?: string;
  state?: string;
  message?: string;
}

interface UserProfile {
  userId: string;
  email: string;
  name: string;
  authorities: string[];
  jobTitle?: string;
  department?: string;
  authDeptId: string;
  deptPermissions: { id: string; name: string }[];
}

/**
 * Azure AD 로그인 URL 요청
 * 
 * 백엔드 응답 형식: { data: { url, state }, message } 또는 { url, state }
 */
export const getLoginUrl = async (): Promise<LoginUrlResponse> => {
  // 프론트엔드 콜백 URL 생성
  // 개발 환경: 동적 URL 사용
  // 프로덕션 환경: 고정 URL 사용 가능
  const frontendCallbackUrl = `${window.location.origin}/auth/callback`;
  
  // 백엔드에 프론트엔드 콜백 URL 전달
  const response = await apiClient.get<LoginUrlApiResponse>('/auth/login-url', {
    params: {
      redirectUri: frontendCallbackUrl
    }
  });

  // 백엔드 응답 형식 확인
  // Case 1: { data: { url, state }, message } - 중첩된 data
  if (response.data.data && response.data.data.url) {
    return response.data.data;
  }

  // Case 2: { url, state } - 직접 반환
  if (response.data.url && response.data.state) {
    return { url: response.data.url, state: response.data.state };
  }

  throw createCustomError(AUTH_CODES.AUTH_INVALID_LOGIN_RESPONSE);
};

/**
 * 사용자 프로필 조회
 */
export const getUserProfile = async (): Promise<UserProfile> => {
  const response = await apiClient.get<{ data: UserProfile }>('/auth/me');
  return response.data.data;
};

/**
 * 로그아웃
 */
export const logout = async (): Promise<void> => {
  await apiClient.post('/auth/logout');
};
