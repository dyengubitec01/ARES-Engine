// created by ARES team [2026-03-20]
import { useBoard, BoardViewMode, BoardTypeIdMap } from './Board/useBoard';
import BoardListView from './Board/BoardListView';
import BoardWriteView from './Board/BoardWriteView';
import BoardDoneView from './Board/BoardDoneView';
import BoardDetailView from './Board/BoardDetailView';

interface BoardModalProps {
  isOpen: boolean;
  onClose: () => void;
  boardTypeIds: BoardTypeIdMap;
  initialViewMode?: BoardViewMode;
  initialPostId?: string | null;
}

function BoardModal({ isOpen, onClose, boardTypeIds, initialViewMode = 'list', initialPostId = null }: BoardModalProps) {
  const board = useBoard({ isOpen, boardTypeIds, initialViewMode, initialPostId });

  if (!isOpen) return null;

  const renderContent = () => {
    switch (board.viewMode) {
      case 'write':
        return (
          <BoardWriteView
            activeTab={board.activeTab}
            reportSubCategory={board.reportSubCategory}
            writeTitle={board.writeTitle}
            setWriteTitle={board.setWriteTitle}
            editorContent={board.editorContent}
            setEditorContent={board.setEditorContent}
            editorHtmlRef={board.editorHtmlRef}
            onImageUpload={board.handleImageUpload}
            onBackToList={board.handleBackToList}
            onClose={onClose}
            onSubmit={board.handleSubmit}
            submitError={board.submitError}
            setSubmitError={board.setSubmitError}
            isSubmitting={board.isSubmitting}
            answerErrorType={board.answerErrorType}
            setAnswerErrorType={board.setAnswerErrorType}
            answerInputSentence={board.answerInputSentence}
            setAnswerInputSentence={board.setAnswerInputSentence}
            answerCorrectContent={board.answerCorrectContent}
            setAnswerCorrectContent={board.setAnswerCorrectContent}
            answerImage={board.answerImage}
            onAnswerImageChange={board.handleAnswerImageChange}
          />
        );
      case 'done':
        return (
          <BoardDoneView
            activeTab={board.activeTab}
            setActiveTab={board.setActiveTab}
            setViewMode={board.setViewMode}
            onBackToList={board.handleBackToListAfterSubmit}
            onClose={onClose}
            onPageReset={board.setCurrentPage}
          />
        );
      case 'detail':
        return (
          <BoardDetailView
            postDetail={board.postDetail}
            isLoading={board.isLoadingDetail}
            error={board.detailError}
            suggestionBoardTypeId={boardTypeIds.suggestion}
            answerSuggestionBoardTypeId={boardTypeIds.answerSuggestion}
            onBackToList={board.handleBackToList}
            onClose={onClose}
            commentContent={board.commentContent}
            setCommentContent={board.setCommentContent}
            isSubmittingComment={board.isSubmittingComment}
            commentError={board.commentError}
            setCommentError={board.setCommentError}
            onSubmitComment={board.handleSubmitComment}
          />
        );
      default:
        return (
          <BoardListView
            activeTab={board.activeTab}
            setActiveTab={board.setActiveTab}
            reportSubCategory={board.reportSubCategory}
            setReportSubCategory={board.setReportSubCategory}
            posts={board.posts}
            totalItems={board.totalItems}
            isLoading={board.isLoading}
            currentPage={board.currentPage}
            onPageChange={board.setCurrentPage}
            onClose={onClose}
            onGoToWrite={board.handleGoToWrite}
            onGoToDetail={board.handleGoToDetail}
          />
        );
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
      }}
    >
      <div
        style={{
          position: 'relative',
          backgroundColor: 'var(--color-grayscale-50)',
          borderRadius: '16px',
          boxShadow: 'var(--shadow-modal)',
          width: '608px',
          height: '660px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          animation: 'modalFadeIn 0.2s ease-out',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {renderContent()}
      </div>

      <style>
        {`
          @keyframes modalFadeIn {
            from { opacity: 0; transform: scale(0.95) translateY(-10px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
          }
          @keyframes spin {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
        `}
      </style>
    </div>
  );
}

export default BoardModal;
