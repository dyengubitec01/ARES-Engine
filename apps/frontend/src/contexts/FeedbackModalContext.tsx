import { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { getBoardTypes } from '../services/board.service';
import BoardModal from '../components/common/BoardModal';
import { BoardTypeIdMap } from '../components/common/Board/useBoard';

interface FeedbackModalContextValue {
  openModal: () => Promise<void>;
  openModalWithPost: (postId: string) => Promise<void>;
  closeModal: () => void;
}

const FeedbackModalContext = createContext<FeedbackModalContextValue | undefined>(undefined);

export function FeedbackModalProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false);
  const [initialPostId, setInitialPostId] = useState<string | null>(null);
  const [boardTypeIds, setBoardTypeIds] = useState<BoardTypeIdMap | null>(null);

  const ensureBoardTypeIds = useCallback(async (): Promise<BoardTypeIdMap | null> => {
    if (boardTypeIds) return boardTypeIds;
    try {
      const types = await getBoardTypes();
      const errorType = types.find(t => t.name === 'feedback');
      const suggestionType = types.find(t => t.name === 'suggestion');
      const answerSuggestionType = types.find(t => t.name === 'answer_suggestion');
      if (!errorType) {
        console.error('[FeedbackModal] "feedback" 게시판 타입을 찾을 수 없습니다.');
        return null;
      }
      if (!suggestionType) {
        console.error('[FeedbackModal] "suggestion" 게시판 타입을 찾을 수 없습니다.');
        return null;
      }
      if (!answerSuggestionType) {
        console.error('[FeedbackModal] "answer_suggestion" 게시판 타입을 찾을 수 없습니다.');
        return null;
      }
      const ids: BoardTypeIdMap = {
        error: errorType.id,
        suggestion: suggestionType.id,
        answerSuggestion: answerSuggestionType.id,
      };
      setBoardTypeIds(ids);
      return ids;
    } catch {
      // apiClient 인터셉터에서 로깅됨
      return null;
    }
  }, [boardTypeIds]);

  const openModal = useCallback(async () => {
    setInitialPostId(null);
    const ids = await ensureBoardTypeIds();
    if (ids) setIsOpen(true);
  }, [ensureBoardTypeIds]);

  const openModalWithPost = useCallback(async (postId: string) => {
    setInitialPostId(postId);
    const ids = await ensureBoardTypeIds();
    if (ids) setIsOpen(true);
  }, [ensureBoardTypeIds]);

  const closeModal = useCallback(() => {
    setIsOpen(false);
    setInitialPostId(null);
  }, []);

  return (
    <FeedbackModalContext.Provider value={{ openModal, openModalWithPost, closeModal }}>
      {children}
      {boardTypeIds && (
        <BoardModal
          isOpen={isOpen}
          onClose={closeModal}
          boardTypeIds={boardTypeIds}
          initialPostId={initialPostId}
        />
      )}
    </FeedbackModalContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useFeedbackModal(): FeedbackModalContextValue {
  const ctx = useContext(FeedbackModalContext);
  if (!ctx) throw new Error('useFeedbackModal must be used within FeedbackModalProvider');
  return ctx;
}
