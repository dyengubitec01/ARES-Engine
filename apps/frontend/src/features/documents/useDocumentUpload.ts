// created by ARES team [2026-01-07]
import { useState, useCallback } from 'react';
import axios from 'axios';
import apiClient from '../../lib/apiClient';
import { calculateFileHash } from '../../lib/fileUtils';
import { createCustomError, convertAxiosError, formatErrorMessage } from '../../lib/customError';
import { DOCUMENT_CODES, mapBackendCodeToFrontend } from '../../constants/customCodes';
import {
  UploadProgress,
  UploadSession,
  UploadSessionResponse,
  CompleteUploadResponse,
  FILE_VALIDATION
} from './types';

interface UseDocumentUploadReturn {
  uploads: Map<string, UploadProgress>;
  uploadFile: (file: File) => Promise<void>;
  removeUpload: (fileName: string) => void;
  clearCompleted: () => void;
}

export function useDocumentUpload(): UseDocumentUploadReturn {
  const [uploads, setUploads] = useState<Map<string, UploadProgress>>(new Map());

  // 파일 유효성 검증
  const validateFile = (file: File): string | null => {
    // 파일 크기 검증 제거 - 용량 제한 없음

    // MIME 타입 검증
    const isValidType = (FILE_VALIDATION.ALLOWED_TYPES as readonly string[]).includes(file.type);
    const isValidExtension = (FILE_VALIDATION.ALLOWED_EXTENSIONS as readonly string[]).some(ext =>
      file.name.toLowerCase().endsWith(ext)
    );

    if (!isValidType && !isValidExtension) {
      return `${formatErrorMessage(createCustomError(DOCUMENT_CODES.DOC_INVALID_FILE_TYPE, '지원하지 않는 파일 형식입니다. (PDF, Word, PowerPoint, Excel, HWP, TXT, CSV만 가능)'))}`;
    }

    return null;
  };

  // Step 1: 업로드 세션 생성
  const createUploadSession = async (file: File, sha256: string): Promise<{ session: UploadSession; mimeType: string }> => {
    // MIME 타입 결정 (이 값이 MinIO PUT 요청 시 Content-Type과 정확히 일치해야 함)
    const mimeType = file.type || 'application/octet-stream';
    
    try {
      
      const response = await apiClient.post<UploadSessionResponse>(
        '/documents/upload-session',
        {
          files: [{
            filename: file.name,
            mimeType: mimeType,
            size: file.size,
            fileModifiedAt: new Date(file.lastModified).toISOString(),
            sha256: sha256
          }]
        }
      );

      if (!response.data.data) {
        throw createCustomError(DOCUMENT_CODES.DOC_UPLOAD_SESSION_INVALID_RESPONSE);
      }

      const sessionData = response.data.data;

      // uploads 배열 검증
      if (!sessionData.uploads || sessionData.uploads.length === 0) {
        throw createCustomError(DOCUMENT_CODES.DOC_UPLOAD_SESSION_MISSING_DATA);
      }

      // versionId가 uploads[0]에 있는지 확인
      if (!sessionData.uploads[0].versionId) {
        throw createCustomError(DOCUMENT_CODES.DOC_UPLOAD_SESSION_MISSING_VERSION);
      }

      return { session: sessionData, mimeType };
    } catch (error: unknown) {
      const statusCode = axios.isAxiosError(error) ? error.response?.status : undefined;
      const errorCode = axios.isAxiosError(error) ? error.response?.data?.code : undefined;

      // 백엔드 에러 코드를 프론트엔드 코드로 매핑
      const frontendCode = errorCode ? mapBackendCodeToFrontend(errorCode) : null;

      // API 명세서에 따른 에러 코드 처리
      if (statusCode === 413 || errorCode === 'BKN040120') {
        throw convertAxiosError(error, frontendCode || DOCUMENT_CODES.DOC_FILE_SIZE_EXCEEDED);
      }
      if (statusCode === 415 || errorCode === 'BKN040121') {
        throw convertAxiosError(error, frontendCode || DOCUMENT_CODES.DOC_INVALID_FILE_TYPE);
      }
      if (statusCode === 409 || errorCode === 'BKN040123') {
        throw convertAxiosError(error, frontendCode || DOCUMENT_CODES.DOC_DUPLICATE_FILE);
      }
      if (statusCode === 400 || errorCode === 'BKN000120') {
        throw convertAxiosError(error, frontendCode || DOCUMENT_CODES.DOC_FILE_VALIDATION_FAILED);
      }

      throw convertAxiosError(error, DOCUMENT_CODES.DOC_UPLOAD_SESSION_FAILED);
    }
  };

  // Step 2: Pre-signed URL로 파일 업로드 (axios 사용, 진행률 추적)
  const uploadToMinIO = async (
    file: File,
    uploadUrl: string,
    fileName: string,
    mimeType: string
  ): Promise<void> => {
    
    const startTime = Date.now();

    try {
      // axios를 사용하여 업로드 진행률 추적
      await axios.put(uploadUrl, file, {
        headers: {
          'Content-Type': mimeType // Presigned URL 서명에 포함된 Content-Type과 일치해야 함
        },
        timeout: 0, // 타임아웃 없음 (대용량 파일 업로드)
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
            const uploadedBytes = progressEvent.loaded;
            const elapsedTime = (Date.now() - startTime) / 1000; // 초 단위
            const uploadSpeed = uploadedBytes / elapsedTime; // bytes/sec
            const remainingBytes = progressEvent.total - uploadedBytes;
            const remainingTime = Math.ceil(remainingBytes / uploadSpeed); // 초

            setUploads((prev) => {
              const updated = new Map(prev);
              const current = updated.get(fileName);
              if (current) {
                updated.set(fileName, {
                  ...current,
                  progress,
                  uploadedBytes,
                  remainingTime: remainingTime > 0 ? remainingTime : undefined,
                  status: 'uploading'
                });
              }
              return updated;
            });
          }
        }
      });
    } catch (error: unknown) {
      const status = axios.isAxiosError(error) ? error.response?.status : undefined;
      const errorMessage = error instanceof Error ? error.message : '알 수 없는 오류';
      console.error('[에러]', { code: status, message: errorMessage });

      // HTTP 상태 코드별 에러 처리
      if (status === 403) {
        throw createCustomError(
          DOCUMENT_CODES.DOC_MINIO_UPLOAD_FAILED,
          'MinIO 업로드 권한이 없습니다. Presigned URL 서명이 유효하지 않습니다.',
          { status, fileName },
          error
        );
      }
      if (status === 405) {
        throw createCustomError(
          DOCUMENT_CODES.DOC_MINIO_UPLOAD_FAILED,
          'MinIO 업로드 실패: PUT 메서드가 허용되지 않습니다. 백엔드 Presigned URL 설정을 확인하세요.',
          { status, fileName },
          error
        );
      }
      if (status === 413) {
        throw createCustomError(
          DOCUMENT_CODES.DOC_FILE_SIZE_EXCEEDED,
          '파일 크기가 너무 큽니다. 게이트웨이 또는 MinIO 설정에서 업로드 크기 제한을 확인하세요.',
          { status, fileName },
          error
        );
      }
      if (status === 400) {
        throw createCustomError(
          DOCUMENT_CODES.DOC_MINIO_UPLOAD_FAILED,
          '잘못된 업로드 요청입니다.',
          { status, fileName },
          error
        );
      }
      if (status === 504 || status === 502) {
        throw createCustomError(
          DOCUMENT_CODES.DOC_MINIO_UPLOAD_FAILED,
          '업로드 타임아웃: 네트워크 연결을 확인하거나 파일을 나누어 업로드하세요.',
          { status, fileName },
          error
        );
      }

      throw createCustomError(
        DOCUMENT_CODES.DOC_MINIO_UPLOAD_FAILED,
        `MinIO 업로드 실패: ${errorMessage}`,
        { status, fileName },
        error
      );
    }
  };

  // Step 3: 업로드 완료 보고
  const completeUpload = async (
    documentId: string,
    versionId: string
  ): Promise<string> => {
    try {
      const response = await apiClient.post<CompleteUploadResponse>(
        `/documents/${documentId}/versions/${versionId}/complete`
      );

      if (!response.data.data) {
        throw createCustomError(DOCUMENT_CODES.DOC_UPLOAD_COMPLETE_INVALID_RESPONSE);
      }

      // 백엔드에서 반환한 상태 (uploaded, queued 등)
      return response.data.data.status;
    } catch (error: unknown) {
      throw convertAxiosError(error, DOCUMENT_CODES.DOC_UPLOAD_COMPLETE_FAILED);
    }
  };

  // 전체 업로드 프로세스
  const uploadFile = useCallback(async (file: File): Promise<void> => {
    // 파일 유효성 검증
    const validationError = validateFile(file);
    if (validationError) {
      // 에러 상태로 추가
      setUploads((prev) => {
        const updated = new Map(prev);
        updated.set(file.name, {
          fileName: file.name,
          fileSize: file.size,
          documentId: '',
          versionId: '',
          status: 'failed',
          progress: 0,
          uploadedBytes: 0,
          error: validationError
        });
        return updated;
      });
      return;
    }

    // 초기 상태 추가
    setUploads((prev) => {
      const updated = new Map(prev);
      updated.set(file.name, {
        fileName: file.name,
        fileSize: file.size,
        documentId: '',
        versionId: '',
        status: 'pending',
        progress: 0,
        uploadedBytes: 0
      });
      return updated;
    });

    // UI 렌더링 시간 확보: React가 pending 상태를 화면에 반영할 수 있도록 브라우저에게 제어권 양보
    await new Promise(resolve => setTimeout(resolve, 0));

    try {  
      // Step 0: 파일 해시 계산
      const sha256Hash = await calculateFileHash(file);
      
      // Step 1: 업로드 세션 생성
      const { session, mimeType } = await createUploadSession(file, sha256Hash);
      const uploadInfo = session.uploads[0]; // 첫 번째 파일 정보
      
      // versionId는 uploads[0]에 있음
      const documentId = session.documentId;
      const versionId = uploadInfo.versionId;

      // 세션 정보 업데이트
      setUploads((prev) => {
        const updated = new Map(prev);
        const current = updated.get(file.name);
        if (current) {
          updated.set(file.name, {
            ...current,
            documentId: documentId,
            versionId: versionId,
            status: 'uploading'
          });
        }
        return updated;
      });

      // Step 2: MinIO에 파일 직접 업로드
      await uploadToMinIO(file, uploadInfo.uploadUrl, file.name, mimeType);

      // Step 3: 업로드 완료 보고
      await completeUpload(documentId, versionId);

      // 성공 상태로 업데이트
      setUploads((prev) => {
        const updated = new Map(prev);
        const current = updated.get(file.name);
        if (current) {
          updated.set(file.name, {
            ...current,
            status: 'uploaded',
            progress: 100,
            uploadedBytes: file.size,
            remainingTime: undefined
          });
        }
        return updated;
      });

    } catch (error: unknown) {
      // 에러 메시지/코드 추출 (Error 인스턴스가 아닐 경우 fallback)
      const message = error instanceof Error
        ? formatErrorMessage(error)
        : '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.';
      const errorCode =
        error && typeof error === 'object' && 'code' in error &&
        typeof (error as { code: unknown }).code === 'string'
          ? (error as { code: string }).code
          : undefined;

      // 실패 상태로 업데이트
      setUploads((prev) => {
        const updated = new Map(prev);
        const current = updated.get(file.name);
        if (current) {
          updated.set(file.name, {
            ...current,
            status: 'failed',
            error: message,
            errorCode
          });
        }
        return updated;
      });
    }
  }, []);

  // 특정 업로드 제거
  const removeUpload = useCallback((fileName: string): void => {
    setUploads((prev) => {
      const updated = new Map(prev);
      updated.delete(fileName);
      return updated;
    });
  }, []);

  // 완료된 업로드 모두 제거
  const clearCompleted = useCallback((): void => {
    setUploads((prev) => {
      const updated = new Map(prev);
      Array.from(updated.entries()).forEach(([key, value]) => {
        if (value.status === 'uploaded') {
          updated.delete(key);
        }
      });
      return updated;
    });
  }, []);

  return {
    uploads,
    uploadFile,
    removeUpload,
    clearCompleted
  };
}
