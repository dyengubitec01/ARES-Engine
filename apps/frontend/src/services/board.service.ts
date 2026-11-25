// created by ARES team [2026-03-20]
import axios from 'axios';
import apiClient from '../lib/apiClient';

// ─── 타입 정의 ───

export interface BoardPost {
  id: string;
  title: string;
  createdAt: string;
  isReplied: boolean;
}

export interface BoardPostDetailImage extends BoardImage {
  id: string;
  sortOrder: number;
}

export interface BoardPostReply {
  id: string;
  userId: string;
  userName: string;
  content: string;
  createdAt: string;
}

export interface BoardPostDetail extends BoardPost {
  boardTypeId: string;
  userId: string;
  userName: string;
  content: string;
  hasImage: boolean;
  images: BoardPostDetailImage[];
  reply: BoardPostReply | null;
}

export interface BoardImage {
  objectKey: string;
  originalFilename: string;
  fileSize: number;
  mimeType: string;
  viewUrl: string;
}

export interface CreatePostData {
  boardTypeId: string;
  title: string;
  content: string;
  images: BoardImage[];
}

export interface BoardType {
  id: string;
  name: string;
  description: string;
}

interface BoardTypesResponse {
  success: boolean;
  code: string;
  message: string;
  data: BoardType[];
}

interface BoardPostsResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    items: BoardPost[];
    meta: {
      page: number;
      limit: number;
      total: number;
    };
  };
}

interface PresignedUrlResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    uploadUrl: string;
    objectKey: string;
  };
}

interface CreatePostResponse {
  success: boolean;
  code: string;
  message: string;
  data: BoardPost;
}

interface BoardPostDetailResponse {
  success: boolean;
  code: string;
  message: string;
  data: BoardPostDetail;
}

// ─── 사용성 평가 타입 정의 ───

export interface SurveyStatusResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    submitted: boolean;
  };
}

export interface SurveyData {
  // 로그인
  loginUnderstand: number;
  loginSimple: number;
  // 홈
  homeIntuitive: number;
  homeInputPosition: number;
  homeNaturalStart: number;
  // 채팅
  chatSpeed: number;
  chatEasy: number;
  chatLength: number;
  chatProcessHelpful: number;
  // 출처
  sourceVisible: number;
  sourceUiEasy: number;
  sourceTrust: number;
  // 문서함
  docUploadEasy: number;
  docStatusClear: number;
  docAiKnowledge: number;
  // 활용도
  workHelpful: number;
  workBetterThanLlm: number;
  // 주관식
  bestFeature: string;
  worstFeature: string;
  freeComment: string;
}

interface SurveySubmitResponse {
  success: boolean;
  code: string;
  message: string;
  data: unknown;
}

// ─── API 함수 ───

/**
 * 게시판 타입 목록 조회
 */
export async function getBoardTypes(): Promise<BoardType[]> {
  const response = await apiClient.get<BoardTypesResponse>('/board/types');

  if (response.data.success) {
    return response.data.data;
  } else {
    throw new Error(response.data.message || '게시판 타입 조회 실패');
  }
}

/**
 * 게시판 게시글 목록 조회
 */
export async function getBoardPosts(
  page: number,
  limit: number,
  boardTypeId: string
): Promise<{ posts: BoardPost[]; total: number }> {
  const response = await apiClient.get<BoardPostsResponse>('/board/posts', {
    params: { page, limit, boardTypeId }
  });

  if (response.data.success) {
    return {
      posts: response.data.data.items,
      total: response.data.data.meta.total
    };
  } else {
    throw new Error(response.data.message || '게시글 목록 조회 실패');
  }
}

/**
 * 게시판 게시글 상세 조회
 */
export async function getBoardPostDetail(id: string): Promise<BoardPostDetail> {
  const response = await apiClient.get<BoardPostDetailResponse>(`/board/posts/${id}`);

  if (response.data.success) {
    return response.data.data;
  }
  throw new Error(response.data.message || '게시글 상세 조회 실패');
}

interface CreatePostCommentResponse {
  success: boolean;
  code: string;
  message: string;
  data: BoardPostReply;
}

/**
 * 게시글 댓글(답변) 작성 — ADMIN 권한 필요, 게시글당 1개
 */
export async function createPostComment(postId: string, content: string): Promise<BoardPostReply> {
  const response = await apiClient.post<CreatePostCommentResponse>(
    `/board/posts/${postId}/comments`,
    { content }
  );
  if (response.data.success) {
    return response.data.data;
  }
  throw new Error(response.data.message || '답변 작성 실패');
}

/**
 * 게시판 이미지 업로드 (Presigned URL 방식)
 * 1. 서버에서 Presigned URL + objectKey 발급
 * 2. 해당 URL로 S3(MinIO)에 직접 PUT 업로드
 * 3. 업로드 메타데이터 반환
 */
export async function uploadBoardImage(file: File, boardTypeName: string): Promise<BoardImage> {
  // 1) Presigned URL 발급
  const presignedResponse = await apiClient.post<PresignedUrlResponse>('/board/presigned-url', {
    filename: file.name,
    boardTypeName,
    mimeType: file.type
  });

  if (!presignedResponse.data.success) {
    throw new Error(presignedResponse.data.message || 'Presigned URL 발급 실패');
  }

  const { uploadUrl, objectKey } = presignedResponse.data.data;

  // 2) S3(MinIO)에 직접 업로드
  // Presigned URL의 SignedHeaders에 content-type이 포함되지 않으므로 헤더를 보내지 않음
  await axios.put(uploadUrl, file);

  // viewUrl: 로컬 Blob URL을 생성하여 에디터 미리보기에 사용
  // (PUT presigned URL은 업로드 전용이므로 이미지 표시에 사용할 수 없음)
  const viewUrl = URL.createObjectURL(file);

  // 3) 업로드 메타데이터 반환
  return {
    objectKey,
    originalFilename: file.name,
    fileSize: file.size,
    mimeType: file.type,
    viewUrl
  };
}

/**
 * 게시글 생성
 */
// ─── 사용성 평가 API 함수 ───

/**
 * 사용성 평가 제출 여부 확인
 */
export async function getMySurveyStatus(): Promise<boolean> {
  const response = await apiClient.get<SurveyStatusResponse>('/board/surveys/me');
  if (response.data.success) {
    return response.data.data.submitted;
  } else {
    throw new Error(response.data.message || '설문 상태 조회 실패');
  }
}

/**
 * 사용성 평가 제출
 */
export async function submitSurvey(data: SurveyData): Promise<void> {
  const response = await apiClient.post<SurveySubmitResponse>('/board/surveys', data);
  if (!response.data.success) {
    throw new Error(response.data.message || '설문 제출 실패');
  }
}

/**
 * 게시글 생성
 */
export async function createPost(data: CreatePostData): Promise<BoardPost> {
  // viewUrl은 프론트엔드 전용 필드이므로 서버 전송 시 제거
  const payload = {
    ...data,
    images: data.images.map(({ viewUrl: _viewUrl, ...rest }) => rest)
  };
  const response = await apiClient.post<CreatePostResponse>('/board/posts', payload);

  if (response.data.success) {
    return response.data.data;
  } else {
    throw new Error(response.data.message || '게시글 등록 실패');
  }
}
