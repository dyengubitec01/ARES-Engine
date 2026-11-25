// created by ARES team [2026-02-24]
import axios from 'axios';
import { FRNCodeValue, ERROR_MESSAGES } from '../constants/customCodes';

/**
 * 프론트엔드 커스텀 에러 인터페이스
 */
export interface CustomError extends Error {
  code: FRNCodeValue;
  message: string;
  detail?: unknown;
  originalError?: unknown;
}

/**
 * 커스텀 에러 생성 함수
 * @param code FRN 코드
 * @param customMessage 커스텀 메시지 (선택, 없으면 기본 메시지 사용)
 * @param detail 상세 정보 (선택)
 * @param originalError 원본 에러 (선택)
 */
export function createCustomError(
  code: FRNCodeValue,
  customMessage?: string,
  detail?: unknown,
  originalError?: unknown
): CustomError {
  const message = customMessage || ERROR_MESSAGES[code] || '알 수 없는 오류가 발생했습니다.';

  const error = new Error(message) as CustomError;
  error.code = code;
  error.detail = detail;
  error.originalError = originalError;

  return error;
}

/**
 * 사용자에게 표시할 에러 메시지 포맷
 * 백엔드 에러 → 백엔드 코드/HTTP 상태 출력, 프론트엔드 에러 → FRN 코드 출력
 * @param error 커스텀 에러 또는 일반 에러
 */
export function formatErrorMessage(error: CustomError | Error): string {
  if ('code' in error && error.code) {
    return error.message;
  }

  return error.message || '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
}

/**
 * 에러가 CustomError인지 확인
 */
export function isCustomError(error: unknown): error is CustomError {
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    typeof (error as { code: unknown }).code === 'string'
  );
}

/**
 * 사용자에게 보여줄 에러 메시지 추출
 * apiClient에서 설정한 userMessage를 우선 사용하고, 없으면 formatErrorMessage 사용
 * @param error 모든 종류의 에러
 */
export function getUserFriendlyMessage(error: unknown): string {
  // apiClient 인터셉터에서 설정한 userMessage가 있으면 우선 사용
  if (
    typeof error === 'object' &&
    error !== null &&
    'userMessage' in error
  ) {
    const userMessage = (error as { userMessage?: unknown }).userMessage;
    if (typeof userMessage === 'string' && userMessage) {
      return userMessage;
    }
  }

  // CustomError 또는 일반 Error 처리
  if (error instanceof Error) {
    return formatErrorMessage(error);
  }

  return '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
}

/**
 * AxiosError를 CustomError로 변환
 * 백엔드 에러 코드 또는 HTTP 상태 코드를 콘솔에 출력
 */
export function convertAxiosError(
  axiosError: unknown,
  fallbackCode: FRNCodeValue
): CustomError {
  let status: number | undefined;
  let backendMessage: string | undefined;
  let backendCode: string | undefined;
  let url: string | undefined;
  let method: string | undefined;

  if (axios.isAxiosError(axiosError)) {
    status = axiosError.response?.status;
    backendMessage = axiosError.response?.data?.message;
    backendCode = axiosError.response?.data?.code;
    url = axiosError.config?.url;
    method = axiosError.config?.method;
  }

  const detail = {
    status,
    backendCode,
    url,
    method,
  };

  return createCustomError(
    fallbackCode,
    backendMessage,
    detail,
    axiosError
  );
}
