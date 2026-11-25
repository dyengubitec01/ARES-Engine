// created by ARES team [2026-04-28]
import type { MutableRefObject } from 'react';
import { toastFailedIcon } from '../../../assets/icons';
import { BoardImage } from '../../../services/board.service';
import {
  GRADIENT,
  GRADIENT_ACTIVE_SHADOW,
  gradientButtonBase,
  secondaryButtonStyle,
  secondaryButtonHoverHandlers,
} from '../../../styles/buttonStyles';
import TiptapEditor from '../TiptapEditor';
import AnswerDataReportForm from './AnswerDataReportForm';
import { BoardTab, ReportSubCategory } from './useBoard';
import { AnswerErrorType } from '../../../constants/answerSuggestion';
import { useScrollFade } from '../../../hooks/useScrollFade';

const labelStyle = {
  fontSize: '13px',
  fontStyle: 'normal' as const,
  fontWeight: 500,
  lineHeight: '20px',
  letterSpacing: '-0.26px',

  color: 'var(--color-grayscale-500, #757578)',
  marginBottom: '8px',
};

const inputBoxStyle = {
  borderRadius: '16px',
  border: '1px solid var(--color-grayscale-200, #DDD)',
  background: 'var(--color-grayscale-50, #FFF)',
  boxShadow: '2px 2px 12px 0 rgba(0, 0, 0, 0.05)',
};

interface BoardWriteViewProps {
  activeTab: BoardTab;
  reportSubCategory: ReportSubCategory;
  writeTitle: string;
  setWriteTitle: (v: string) => void;
  editorContent: string;
  setEditorContent: (v: string) => void;
  editorHtmlRef: MutableRefObject<string>;
  onImageUpload: (img: BoardImage) => void;
  onBackToList: () => void;
  onClose: () => void;
  onSubmit: () => void;
  submitError: string | null;
  setSubmitError: (v: string | null) => void;
  isSubmitting: boolean;
  answerErrorType: AnswerErrorType | null;
  setAnswerErrorType: (v: AnswerErrorType) => void;
  answerInputSentence: string;
  setAnswerInputSentence: (v: string) => void;
  answerCorrectContent: string;
  setAnswerCorrectContent: (v: string) => void;
  answerImage: BoardImage | null;
  onAnswerImageChange: (image: BoardImage | null) => void;
}

function BoardWriteView({
  activeTab,
  reportSubCategory,
  writeTitle,
  setWriteTitle,
  editorContent,
  setEditorContent,
  editorHtmlRef,
  onImageUpload,
  onBackToList,
  onClose,
  onSubmit,
  submitError,
  setSubmitError,
  isSubmitting,
  answerErrorType,
  setAnswerErrorType,
  answerInputSentence,
  setAnswerInputSentence,
  answerCorrectContent,
  setAnswerCorrectContent,
  answerImage,
  onAnswerImageChange,
}: BoardWriteViewProps) {
  const isAnswerData = activeTab === 'error' && reportSubCategory === 'answerData';
  const titleLabel = activeTab === 'suggestion' ? '제안명' : '오류 제목';
  const isGeneralFormComplete =
    writeTitle.trim().length > 0 && editorContent.length > 0 && editorContent !== '<p></p>';
  const isAnswerFormComplete =
    answerErrorType !== null &&
    answerInputSentence.trim().length > 0 &&
    answerCorrectContent.trim().length > 0;
  const isFormComplete = isAnswerData ? isAnswerFormComplete : isGeneralFormComplete;
  const isDisabled = !isFormComplete || isSubmitting;
  const clearSubmitError = () => {
    if (submitError) setSubmitError(null);
  };
  const { ref: scrollContainerRef, showTopFade, showBottomFade, handleScroll } = useScrollFade<HTMLDivElement>(10, { eager: true });

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        padding: '40px 40px 36px',
        flexShrink: 0,
      }}>
        <button
          onClick={onBackToList}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            backgroundColor: 'transparent',
            border: '1px solid var(--color-grayscale-300, #B9B9B9)',
            borderRadius: '999px',
            cursor: 'pointer',
            padding: '11px 20px',
            fontSize: '13px',
            fontWeight: 500,
            color: 'var(--color-grayscale-400)',
          }}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M10 12L6 8L10 4" stroke="var(--color-grayscale-400)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          목록으로
        </button>
      </div>

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minHeight: 0 }}>
        {showTopFade && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '48px',
            background: 'linear-gradient(to bottom, var(--color-scroll-fade), transparent)',
            pointerEvents: 'none',
            zIndex: 1,
          }} />
        )}
        {showBottomFade && (
          <div style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: '48px',
            background: 'linear-gradient(to top, var(--color-scroll-fade), transparent)',
            pointerEvents: 'none',
            zIndex: 1,
          }} />
        )}
        <div ref={scrollContainerRef} onScroll={handleScroll} style={{ height: '100%', overflow: 'auto', padding: '0 40px 36px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {isAnswerData ? (
            <AnswerDataReportForm
              errorType={answerErrorType}
              setErrorType={setAnswerErrorType}
              inputSentence={answerInputSentence}
              setInputSentence={setAnswerInputSentence}
              correctContent={answerCorrectContent}
              setCorrectContent={setAnswerCorrectContent}
              image={answerImage}
              onImageChange={onAnswerImageChange}
              clearSubmitError={clearSubmitError}
            />
          ) : (
            <>
              <div>
                <div style={labelStyle}>{titleLabel}<span style={{ color: 'var(--color-error-500)', marginLeft: '4px' }}>*</span></div>
                <input
                  type="text"
                  value={writeTitle}
                  onChange={(e) => {
                    setWriteTitle(e.target.value);
                    if (submitError) setSubmitError(null);
                  }}
                  placeholder="제목을 입력해주세요."
                  style={{
                    ...inputBoxStyle,
                    width: '100%',
                    padding: '10px 14px',

                    fontSize: '14px',
                    fontStyle: 'normal',
                    fontWeight: 400,
                    lineHeight: '20px',
                    letterSpacing: '-0.28px',
                    color: 'var(--color-grayscale-900)',
                    outline: 'none',
                    boxSizing: 'border-box' as const,
                    transition: 'border-color 0.2s',
                  }}
                  onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--color-primary-600)'; }}
                  onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--color-grayscale-200, #DDD)'; }}
                />
              </div>

              <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
                <div style={labelStyle}>상세 내용<span style={{ color: 'var(--color-error-500)', marginLeft: '4px' }}>*</span></div>
                <div style={{ ...inputBoxStyle, flex: 1, minHeight: 0, overflow: 'hidden' }}>
                  <TiptapEditor
                    boardTypeName={activeTab === 'suggestion' ? 'suggestion' : 'feedback'}
                    onUpdate={(html) => {
                      editorHtmlRef.current = html;
                      setEditorContent(html);
                      if (submitError) setSubmitError(null);
                    }}
                    onImageUpload={onImageUpload}
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {submitError && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          margin: '0 32px 12px',
          color: 'var(--color-error-500)',
          fontSize: '13px',
          fontWeight: 500,
          lineHeight: '20px',
          letterSpacing: '-0.26px',
          flexShrink: 0,
        }}>
          <img src={toastFailedIcon} alt="" style={{ width: '14px', height: '14px', flexShrink: 0 }} />
          <span>{submitError}</span>
        </div>
      )}

      <div style={{
        display: 'flex',
        gap: '16px',
        padding: '0 40px 40px',
        flexShrink: 0,
      }}>
        <button
          onClick={onClose}
          style={secondaryButtonStyle}
          {...secondaryButtonHoverHandlers}
        >
          닫기
        </button>

        <button
          onClick={onSubmit}
          disabled={isDisabled}
          style={{
            ...gradientButtonBase,
            background: GRADIENT.primarySoft,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            padding: '10px 28px',
            width: '406px',
            borderRadius: '999px',
            cursor: isDisabled ? 'not-allowed' : 'pointer',
            opacity: isDisabled ? 0.5 : 1,
            transition: 'opacity 0.2s',
            flexShrink: 0,
          }}
          onMouseOver={(e) => { if (!isDisabled) e.currentTarget.style.background = GRADIENT.primaryHover; }}
          onMouseOut={(e) => { e.currentTarget.style.background = isDisabled ? GRADIENT.primarySoft : GRADIENT.primarySoft; e.currentTarget.style.boxShadow = 'none'; }}
          onMouseDown={(e) => { if (!isDisabled) { e.currentTarget.style.background = GRADIENT.primaryActive; e.currentTarget.style.boxShadow = GRADIENT_ACTIVE_SHADOW; } }}
          onMouseUp={(e) => { if (!isDisabled) { e.currentTarget.style.background = GRADIENT.primaryHover; e.currentTarget.style.boxShadow = 'none'; } }}
        >
          {isSubmitting ? (
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg"
              style={{ animation: 'spin 1s linear infinite' }}>
              <circle cx="9" cy="9" r="7" stroke="#fff" strokeWidth="2" strokeDasharray="32" strokeDashoffset="10" strokeLinecap="round" />
            </svg>
          ) : (
            '제출하기'
          )}
        </button>
      </div>
    </div>
  );
}

export default BoardWriteView;
