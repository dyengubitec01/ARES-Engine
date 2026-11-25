// created by ARES team [2025-12-15]
import axios, { InternalAxiosRequestConfig } from 'axios';
import { reportApiError } from './faro';

// axios 타입 확장: apiClient가 동적으로 추가하는 비표준 필드 정식 등록
// - _retry: 토큰 갱신 후 재시도된 요청인지 표시 (무한 루프 방지)
// - userMessage: 사용자에게 보여줄 친화적 에러 메시지
declare module 'axios' {
  interface InternalAxiosRequestConfig {
    _retry?: boolean;
  }
  interface AxiosError {
    userMessage?: string;
  }
}

// 환경 변수에서 API URL 가져오기 (fallback: '/api')
const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true
});

// Refresh 토큰 재시도 플래그
let isRefreshing = false;
let isLoggingOut = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
  config: InternalAxiosRequestConfig;
}> = [];

// 토큰 갱신 시도를 하지 않을 엔드포인트 (무한 루프 방지)
const REFRESH_EXCLUDED_ENDPOINTS = [
  '/auth/refresh',   // 리프레시 자체의 401은 재시도 불가
  '/auth/logout',    // 로그아웃은 재시도 불필요
  '/auth/callback',  // OAuth 콜백은 재시도 불필요
  '/auth/login-url'  // 로그인 URL 조회는 재시도 불필요
];

// 실패한 요청 큐에 추가 및 처리하는 함수
const processQueue = (error: unknown = null) => {
  console.log(`[apiClient] Processing queue with ${failedQueue.length} requests`, error ? 'with error' : 'successfully');
  failedQueue.forEach((promise) => {
    if (error) {
      promise.reject(error);
    } else {
      // _retry 플래그 설정 후 요청 재시도
      promise.config._retry = true;
      apiClient(promise.config)
        .then(response => promise.resolve(response))
        .catch(err => promise.reject(err));
    }
  });
  failedQueue = [];
};


// 전역 상태 초기화 함수 (로그아웃 시 호출)
export const clearAuthState = () => {
  isLoggingOut = true;
  isRefreshing = false;
  processQueue(new Error('User logged out'));
};

// URL이 리프레시 제외 대상인지 확인
const isRefreshExcluded = (url: string | undefined): boolean => {
  if (!url) return false;
  return REFRESH_EXCLUDED_ENDPOINTS.some(endpoint => url.includes(endpoint));
};

// 응답 인터셉터: 401 에러 시 자동 토큰 갱신 시도
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const requestUrl = originalRequest?.url || 'unknown';
    const status = error.response?.status;
    const backendCode = error.response?.data?.code;
    const backendMessage = error.response?.data?.message;

    // 모든 에러의 상세 정보를 콘솔에 출력 (개발자용)
    const code = backendCode || status;
    console.error('[에러]', { code, message: backendMessage || error.message });

    reportApiError({
      url: requestUrl,
      method: originalRequest?.method || 'unknown',
      status,
      backendCode,
      backendMessage,
    });

    // 401 에러 감지
    if (error.response?.status === 401) {

      // 로그아웃 진행 중이면 토큰 갱신 차단
      if (isLoggingOut) {
        return Promise.reject(error);
      }

      // 리프레시 제외 대상이거나 이미 재시도한 요청인 경우 스킵
      if (isRefreshExcluded(requestUrl)) {
        
        // 사용자 친화적인 에러 메시지로 변환
        error.userMessage = '세션이 만료되었습니다. 다시 로그인해 주세요.';
        return Promise.reject(error);
      }

      if (originalRequest._retry) {
        
        // 사용자 친화적인 에러 메시지로 변환
        error.userMessage = '세션이 만료되었습니다. 다시 로그인해 주세요.';
        return Promise.reject(error);
      }

      // 이미 refresh 중이면 큐에 추가
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject, config: originalRequest });
        });
      }

      // 토큰 갱신 시작
      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // Access Token 갱신 시도
        const refreshResponse = await apiClient.post('/auth/refresh');
        console.log('[apiClient] Refresh response status:', refreshResponse.status);
        
        // 성공 시 큐에 있는 요청들 재시도
        processQueue();
        isRefreshing = false;

        // 원래 요청 재시도
        return apiClient(originalRequest);
      } catch (refreshError: unknown) {
        // axios 에러일 때만 응답 상세 추출 (그 외에는 undefined 처리)
        let status: number | undefined;
        let backendCode: string | undefined;
        let backendMessage: string | undefined;

        if (axios.isAxiosError(refreshError)) {
          status = refreshError.response?.status;
          backendCode = refreshError.response?.data?.code;
          backendMessage = refreshError.response?.data?.message;
        }

        console.error('[에러]', {
          code: backendCode || status,
          message: '토큰 갱신 실패 - 로그아웃 처리 및 페이지 이동'
        });

        reportApiError({
          url: '/auth/refresh',
          method: 'POST',
          status,
          backendCode,
          backendMessage,
          isRefreshFailure: true,
        });

        // Refresh 실패 시 큐 비우기 및 상태 초기화
        processQueue(refreshError);
        isRefreshing = false;

        // 사용자 친화적인 에러 메시지 추가 (AxiosError에만 적용)
        if (axios.isAxiosError(refreshError)) {
          refreshError.userMessage = '세션이 만료되었습니다. 다시 로그인해 주세요.';
        }

        // 로그인 페이지로 리다이렉트 (한 번만)
        // AuthContext에서 이미 리다이렉트하는 경우를 대비해 중복 방지
        if (window.location.pathname !== '/' && window.location.pathname !== '/auth/callback') {
          window.location.href = '/';
        }

        return Promise.reject(refreshError);
      }
    }

    // 401이 아닌 경우: 사용자 친화적인 에러 메시지 추가
    if (!error.userMessage) {
      // 상태 코드별 사용자 친화적 메시지
      if (status >= 500) {
        error.userMessage = '서비스에 일시적인 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.';
      } else if (status === 403) {
        error.userMessage = '접근 권한이 없습니다.';
      } else if (status === 404) {
        error.userMessage = '요청하신 정보를 찾을 수 없습니다.';
      } else if (status === 400) {
        // 400 에러의 경우 백엔드 메시지가 있으면 사용, 없으면 일반 메시지
        error.userMessage = backendMessage || '잘못된 요청입니다.';
      } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        error.userMessage = '서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.';
      } else if (error.code === 'ERR_NETWORK' || !status) {
        error.userMessage = '서버에 연결할 수 없습니다. 인터넷 연결을 확인해 주세요.';
      } else {
        // 기타 모든 에러
        error.userMessage = '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;

