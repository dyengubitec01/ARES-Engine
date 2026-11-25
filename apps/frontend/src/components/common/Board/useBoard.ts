// created by ARES team [2026-04-28]
import { useState, useEffect, useCallback, useRef } from 'react';
import axios from 'axios';
import { getBoardPosts, createPost, getBoardPostDetail, createPostComment, BoardPost, BoardPostDetail, BoardImage } from '../../../services/board.service';
import { AnswerErrorType, LLM_SERVICE_NAME } from '../../../constants/answerSuggestion';

export const ITEMS_PER_PAGE = 5;
export const COMMENT_MAX_LENGTH = 5000;
export const ANSWER_TITLE_PREVIEW_LENGTH = 30;

export type BoardTab = 'error' | 'suggestion' | 'usability';
export type BoardViewMode = 'list' | 'write' | 'done' | 'detail';
export type ReportSubCategory = 'general' | 'answerData';

export interface BoardTypeIdMap {
  error: string;
  suggestion: string;
  answerSuggestion: string;
}

interface UseBoardArgs {
  isOpen: boolean;
  boardTypeIds: BoardTypeIdMap;
  initialViewMode: BoardViewMode;
  initialPostId?: string | null;
}

function buildAnswerTitle(errorType: AnswerErrorType, inputSentence: string): string {
  const trimmed = inputSentence.trim();
  const preview =
    trimmed.length > ANSWER_TITLE_PREVIEW_LENGTH
      ? `${trimmed.slice(0, ANSWER_TITLE_PREVIEW_LENGTH)}…`
      : trimmed;
  return `[${errorType}] ${preview}`;
}

export function useBoard({ isOpen, boardTypeIds, initialViewMode, initialPostId }: UseBoardArgs) {
  // 객체 참조 변동에 따른 useCallback 재생성 방지를 위해 string 값으로 분해
  const errorBoardTypeId = boardTypeIds.error;
  const suggestionBoardTypeId = boardTypeIds.suggestion;
  const answerSuggestionBoardTypeId = boardTypeIds.answerSuggestion;
  const [activeTab, setActiveTab] = useState<BoardTab>('error');
  const [reportSubCategory, setReportSubCategory] = useState<ReportSubCategory>('general');
  const [viewMode, setViewMode] = useState<BoardViewMode>('list');
  const [currentPage, setCurrentPage] = useState(1);
  const [posts, setPosts] = useState<BoardPost[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const [writeTitle, setWriteTitle] = useState('');
  const editorHtmlRef = useRef('');
  const [editorContent, setEditorContent] = useState('');
  const [uploadedImages, setUploadedImages] = useState<BoardImage[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // 정답 데이터 신고 단일 사례 입력 상태
  const [answerErrorType, setAnswerErrorType] = useState<AnswerErrorType | null>(null);
  const [answerInputSentence, setAnswerInputSentence] = useState('');
  const [answerCorrectContent, setAnswerCorrectContent] = useState('');
  const [answerImage, setAnswerImage] = useState<BoardImage | null>(null);

  const [postDetail, setPostDetail] = useState<BoardPostDetail | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [commentContent, setCommentContent] = useState('');
  const [isSubmittingComment, setIsSubmittingComment] = useState(false);
  const [commentError, setCommentError] = useState<string | null>(null);

  const resolveBoardTypeId = useCallback(
    (tab: BoardTab, subCategory: ReportSubCategory): string => {
      if (tab === 'suggestion') return suggestionBoardTypeId;
      if (tab === 'error' && subCategory === 'answerData') return answerSuggestionBoardTypeId;
      return errorBoardTypeId;
    },
    [errorBoardTypeId, suggestionBoardTypeId, answerSuggestionBoardTypeId]
  );

  const fetchPosts = useCallback(
    async (page: number, tab: BoardTab, subCategory: ReportSubCategory) => {
      const targetBoardTypeId = resolveBoardTypeId(tab, subCategory);
      setIsLoading(true);
      try {
        const result = await getBoardPosts(page, ITEMS_PER_PAGE, targetBoardTypeId);
        setPosts(result.posts);
        setTotalItems(result.total);
      } catch {
        setPosts([]);
        setTotalItems(0);
      } finally {
        setIsLoading(false);
      }
    },
    [resolveBoardTypeId]
  );

  const resetWriteState = () => {
    setWriteTitle('');
    editorHtmlRef.current = '';
    setEditorContent('');
    setUploadedImages([]);
    setAnswerErrorType(null);
    setAnswerInputSentence('');
    setAnswerCorrectContent('');
    setAnswerImage(null);
  };

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      setActiveTab('error');
      setReportSubCategory('general');
      if (initialPostId) {
        // 알림 등에서 특정 게시글 상세로 바로 진입
        setViewMode('detail');
        setIsLoadingDetail(true);
        setDetailError(null);
        setPostDetail(null);
        getBoardPostDetail(initialPostId)
          .then((detail) => {
            setPostDetail(detail);
            // 게시글 타입에 맞춰 탭/서브카테고리 동기화 — 목록으로 돌아갔을 때 같은 화면이 열리도록
            if (detail.boardTypeId === suggestionBoardTypeId) {
              setActiveTab('suggestion');
            } else if (detail.boardTypeId === answerSuggestionBoardTypeId) {
              setActiveTab('error');
              setReportSubCategory('answerData');
            }
          })
          .catch(() => setDetailError('게시글을 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.'))
          .finally(() => setIsLoadingDetail(false));
      } else {
        setViewMode(initialViewMode);
        if (initialViewMode === 'write') {
          resetWriteState();
        }
      }
      setCurrentPage(1);
      if (!initialPostId) {
        // 모달 오픈 시 항상 'error' 탭 + general 서브카테고리로 시작
        fetchPosts(1, 'error', 'general');
      }
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen, initialPostId, initialViewMode, fetchPosts, suggestionBoardTypeId, answerSuggestionBoardTypeId]);

  useEffect(() => {
    if (isOpen && activeTab !== 'usability' && viewMode === 'list') {
      fetchPosts(currentPage, activeTab, reportSubCategory);
    }
  }, [currentPage, isOpen, activeTab, reportSubCategory, viewMode, fetchPosts]);

  const handleGoToWrite = () => {
    resetWriteState();
    setSubmitError(null);
    setViewMode('write');
  };

  const handleBackToList = () => {
    setViewMode('list');
    setPostDetail(null);
    setDetailError(null);
    // currentPage 유지 — viewMode useEffect가 자동으로 재조회
  };

  const handleBackToListAfterSubmit = () => {
    setViewMode('list');
    setPostDetail(null);
    setDetailError(null);
    setCurrentPage(1);
    fetchPosts(1, activeTab, reportSubCategory);
  };

  const handleGoToDetail = async (postId: string) => {
    setViewMode('detail');
    setIsLoadingDetail(true);
    setDetailError(null);
    setPostDetail(null);
    setCommentContent('');
    setCommentError(null);
    try {
      const detail = await getBoardPostDetail(postId);
      setPostDetail(detail);
    } catch {
      setDetailError('게시글을 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.');
    } finally {
      setIsLoadingDetail(false);
    }
  };

  const handleSubmitComment = async () => {
    if (!postDetail) return;
    const trimmed = commentContent.trim();
    if (!trimmed) {
      setCommentError('답변 내용을 입력해 주세요.');
      return;
    }
    setCommentError(null);
    setIsSubmittingComment(true);
    try {
      await createPostComment(postDetail.id, trimmed);
      const refreshed = await getBoardPostDetail(postDetail.id);
      setPostDetail(refreshed);
      setCommentContent('');
    } catch (err: unknown) {
      const status = axios.isAxiosError(err) ? err.response?.status : undefined;
      if (status === 409) {
        setCommentError('이미 답변이 등록된 게시글입니다.');
      } else if (status === 403) {
        setCommentError('답변 작성 권한이 없습니다.');
      } else {
        setCommentError('답변 등록에 실패했습니다. 잠시 후 다시 시도해 주세요.');
      }
    } finally {
      setIsSubmittingComment(false);
    }
  };

  const handleImageUpload = (imageInfo: BoardImage) => {
    setUploadedImages((prev) => [...prev, imageInfo]);
  };

  const handleAnswerImageChange = (image: BoardImage | null) => {
    setAnswerImage(image);
  };

  const handleSubmit = async () => {
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      if (activeTab === 'error' && reportSubCategory === 'answerData') {
        // 정답 데이터 신고 — JSON 직렬화된 단일 사례 전송
        if (!answerErrorType || !answerInputSentence.trim() || !answerCorrectContent.trim()) {
          setSubmitError('필수 항목을 모두 입력해 주세요.');
          return;
        }
        const trimmedInput = answerInputSentence.trim();
        const trimmedCorrect = answerCorrectContent.trim();
        const caseObject = {
          aiServiceName: LLM_SERVICE_NAME,
          errorType: answerErrorType,
          inputSentence: trimmedInput,
          correctContent: trimmedCorrect,
          imageObjectKey: answerImage?.objectKey ?? null,
        };
        const images: BoardImage[] = answerImage ? [answerImage] : [];
        await createPost({
          boardTypeId: answerSuggestionBoardTypeId,
          title: buildAnswerTitle(answerErrorType, trimmedInput),
          content: JSON.stringify({ cases: [caseObject] }),
          images,
        });
      } else {
        const targetBoardTypeId = activeTab === 'suggestion' ? suggestionBoardTypeId : errorBoardTypeId;
        // 본문에서 <img> 제거 — 이미지는 별도 갤러리로 표시되므로 중복 렌더링 방지
        const contentWithoutImages = editorHtmlRef.current.replace(/<img\b[^>]*\/?>/gi, '');
        await createPost({
          boardTypeId: targetBoardTypeId,
          title: writeTitle.trim(),
          content: contentWithoutImages,
          images: uploadedImages,
        });
      }
      setViewMode('done');
    } catch {
      setSubmitError('게시글 등록에 실패했습니다. 잠시후 다시 시도해주세요.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return {
    activeTab,
    setActiveTab,
    reportSubCategory,
    setReportSubCategory,
    viewMode,
    setViewMode,
    currentPage,
    setCurrentPage,
    posts,
    totalItems,
    isLoading,
    submitError,
    setSubmitError,
    writeTitle,
    setWriteTitle,
    editorContent,
    setEditorContent,
    editorHtmlRef,
    uploadedImages,
    isSubmitting,
    handleGoToWrite,
    handleBackToList,
    handleBackToListAfterSubmit,
    handleImageUpload,
    handleSubmit,
    postDetail,
    isLoadingDetail,
    detailError,
    handleGoToDetail,
    commentContent,
    setCommentContent,
    isSubmittingComment,
    commentError,
    setCommentError,
    handleSubmitComment,
    answerErrorType,
    setAnswerErrorType,
    answerInputSentence,
    setAnswerInputSentence,
    answerCorrectContent,
    setAnswerCorrectContent,
    answerImage,
    handleAnswerImageChange,
  };
}
