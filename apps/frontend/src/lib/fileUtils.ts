// created by ARES team [2026-02-10]
import { createCustomError } from './customError';
import { DOCUMENT_CODES } from '../constants/customCodes';

/**
 * 파일의 SHA-256 해시값을 계산하는 유틸리티 함수
 * @param file - 해시를 계산할 File 객체
 * @returns 64자리 소문자 16진수 문자열로 변환된 SHA-256 해시값
 */
export async function calculateFileHash(file: File): Promise<string> {
  try {
    // File을 ArrayBuffer로 읽기
    const arrayBuffer = await file.arrayBuffer();
    
    // Web Crypto API를 사용하여 SHA-256 해시 계산
    const hashBuffer = await crypto.subtle.digest('SHA-256', arrayBuffer);
    
    // ArrayBuffer를 Hex 문자열로 변환
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    const hashHex = hashArray
      .map(byte => byte.toString(16).padStart(2, '0'))
      .join('');
    
    return hashHex;
  } catch (error) {
    console.error('[fileUtils] SHA-256 해시 계산 중 오류 발생:', error);
    throw createCustomError(DOCUMENT_CODES.DOC_FILE_HASH_FAILED, undefined, undefined, error);
  }
}

/**
 * 파일 크기를 사람이 읽기 쉬운 형태로 변환
 * @param bytes - 바이트 수
 * @param fallback - 값이 없을 때 반환할 문자열 (기본: '-')
 */
export function formatFileSize(bytes: number | undefined | null, fallback = '-'): string {
  if (bytes === undefined || bytes === null || isNaN(bytes)) {
    return fallback;
  }
  const numBytes = Number(bytes);
  if (numBytes < 1024) return numBytes + ' B';
  if (numBytes < 1024 * 1024) return (numBytes / 1024).toFixed(2) + ' KB';
  return (numBytes / (1024 * 1024)).toFixed(2) + ' MB';
}

/**
 * 날짜 문자열을 포맷팅 (YYYY{sep}MM{sep}DD HH:mm)
 * @param dateString - ISO 날짜 문자열
 * @param separator - 날짜 구분자 (기본: '-')
 */
export function formatDate(dateString: string | undefined | null, separator = '-'): string {
  if (!dateString) return '-';
  const date = new Date(dateString);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  return `${year}${separator}${month}${separator}${day} ${hours}:${minutes}`;
}

/**
 * 파일명에서 확장자 추출 (.포함)
 */
export function getFileExtension(filename: string | undefined): string {
  if (!filename) return '';
  const lastDotIndex = filename.lastIndexOf('.');
  if (lastDotIndex === -1) return '';
  return filename.substring(lastDotIndex);
}

/**
 * 파일명에서 확장자만 대문자로 반환 (.제외)
 */
export function getFileExtensionUpperCase(filename: string | undefined): string {
  const ext = getFileExtension(filename);
  return ext ? ext.substring(1).toUpperCase() : '';
}
