// ============================================================
// DY-OOO AI 솔루션 - Business Response Codes (barrel)
// Format: BKN + XXXXXX (6자리)
// Structure: 대분류(00-99) + 중분류(00-99) + 소분류(00-99)
// 소분류: 정상(00), 예외(20-79), 기타(80-99)
//
// 도메인별 파일에 정의 후 여기서 합쳐 단일 ResponseCode/HttpStatusMap/ResponseMessage 로 노출.
// 신규 코드 추가는 해당 도메인 파일에서만.
// ============================================================

import {
  CommonResponseCode,
  CommonHttpStatus,
  CommonMessages,
} from './common.codes';
import {
  AuthResponseCode,
  AuthHttpStatus,
  AuthMessages,
} from './auth.codes';
import {
  ChatResponseCode,
  ChatHttpStatus,
  ChatMessages,
} from './chat.codes';
import {
  AdminResponseCode,
  AdminHttpStatus,
  AdminMessages,
} from './admin.codes';
import {
  DocumentResponseCode,
  DocumentHttpStatus,
  DocumentMessages,
} from './document.codes';
import {
  EmbeddingResponseCode,
  EmbeddingHttpStatus,
  EmbeddingMessages,
} from './embedding.codes';
import {
  EventAlarmResponseCode,
  EventAlarmHttpStatus,
  EventAlarmMessages,
} from './event-alarm.codes';
import {
  BoardResponseCode,
  BoardHttpStatus,
  BoardMessages,
} from './board.codes';
import { DevResponseCode, DevHttpStatus, DevMessages } from './dev.codes';

export const ResponseCode = {
  ...CommonResponseCode,
  ...AuthResponseCode,
  ...ChatResponseCode,
  ...AdminResponseCode,
  ...DocumentResponseCode,
  ...EmbeddingResponseCode,
  ...EventAlarmResponseCode,
  ...BoardResponseCode,
  ...DevResponseCode,
} as const;

export type ResponseCodeType = (typeof ResponseCode)[keyof typeof ResponseCode];

export const HttpStatusMap: Record<ResponseCodeType, number> = {
  ...CommonHttpStatus,
  ...AuthHttpStatus,
  ...ChatHttpStatus,
  ...AdminHttpStatus,
  ...DocumentHttpStatus,
  ...EmbeddingHttpStatus,
  ...EventAlarmHttpStatus,
  ...BoardHttpStatus,
  ...DevHttpStatus,
} as Record<ResponseCodeType, number>;

export const ResponseMessage: Record<ResponseCodeType, string> = {
  ...CommonMessages,
  ...AuthMessages,
  ...ChatMessages,
  ...AdminMessages,
  ...DocumentMessages,
  ...EmbeddingMessages,
  ...EventAlarmMessages,
  ...BoardMessages,
  ...DevMessages,
} as Record<ResponseCodeType, string>;

// ============================================================
// Helper Functions
// ============================================================

/**
 * Get message for a response code
 */
export function getResponseMessage(code: ResponseCodeType): string {
  return ResponseMessage[code] || ResponseMessage[ResponseCode.UNKNOWN];
}

/**
 * Get HTTP status code for a response code
 */
export function getHttpStatus(code: ResponseCodeType): number {
  return HttpStatusMap[code] || 500;
}

/**
 * Check if code represents success (소분류 00)
 */
export function isSuccessCode(code: string): boolean {
  if (!code.startsWith('BKN') || code.length !== 9) return false;
  const subCode = parseInt(code.slice(-2), 10);
  return subCode === 0;
}

/**
 * Check if code represents error (소분류 20-79)
 */
export function isErrorCode(code: string): boolean {
  if (!code.startsWith('BKN') || code.length !== 9) return false;
  const subCode = parseInt(code.slice(-2), 10);
  return subCode >= 20 && subCode <= 79;
}

/**
 * Extract category from code (대분류)
 */
export function getCodeCategory(code: string): string {
  if (!code.startsWith('BKN') || code.length !== 9) return '00';
  return code.slice(3, 5);
}

/**
 * Extract sub-category from code (중분류)
 */
export function getCodeSubCategory(code: string): string {
  if (!code.startsWith('BKN') || code.length !== 9) return '00';
  return code.slice(5, 7);
}
