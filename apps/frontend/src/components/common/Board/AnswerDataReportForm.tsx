// created by ARES team [2026-06-01]
import { useRef, useState } from 'react';
import { uploadBoardImage, BoardImage } from '../../../services/board.service';
import { ANSWER_ERROR_TYPES, AnswerErrorType } from '../../../constants/answerSuggestion';

const labelStyle = {
  fontSize: '13px',
  fontStyle: 'normal' as const,
  fontWeight: 500,
  lineHeight: '20px',
  letterSpacing: '-0.26px',
  color: 'var(--color-grayscale-500, #757578)',
  marginBottom: '8px',
};

const requiredMarkStyle = {
  color: 'var(--color-error-500)',
  marginLeft: '4px',
};

const inputBoxBase = {
  width: '100%',
  borderRadius: '12px',
  border: '1px solid var(--color-grayscale-200, #DDD)',
  background: 'var(--color-grayscale-50, #FFF)',
  boxShadow: '2px 2px 12px 0 rgba(0, 0, 0, 0.05)',
  padding: '10px 14px',
  fontSize: '14px',
  fontWeight: 400,
  lineHeight: '20px',
  letterSpacing: '-0.28px',
  color: 'var(--color-grayscale-900)',
  outline: 'none',
  fontFamily: 'inherit',
  boxSizing: 'border-box' as const,
  transition: 'border-color 0.2s',
};

interface AnswerDataReportFormProps {
  errorType: AnswerErrorType | null;
  setErrorType: (v: AnswerErrorType) => void;
  inputSentence: string;
  setInputSentence: (v: string) => void;
  correctContent: string;
  setCorrectContent: (v: string) => void;
  image: BoardImage | null;
  onImageChange: (image: BoardImage | null) => void;
  clearSubmitError: () => void;
}

function AnswerDataReportForm({
  errorType,
  setErrorType,
  inputSentence,
  setInputSentence,
  correctContent,
  setCorrectContent,
  image,
  onImageChange,
  clearSubmitError,
}: AnswerDataReportFormProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = '';

    setIsUploading(true);
    setUploadError(null);
    try {
      const uploaded = await uploadBoardImage(file, 'answer_suggestion');
      onImageChange(uploaded);
      clearSubmitError();
    } catch {
      setUploadError('이미지 업로드에 실패했습니다. 잠시 후 다시 시도해 주세요.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleRemoveImage = () => {
    onImageChange(null);
    setUploadError(null);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* 오류 화면 (선택) */}
      <div>
        <div style={labelStyle}>오류 화면</div>
        {image ? (
          <div style={{
            position: 'relative',
            borderRadius: '12px',
            border: '1px solid var(--color-grayscale-200, #DDD)',
            background: 'var(--color-grayscale-50, #FFF)',
            padding: '12px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
          }}>
            <img
              src={image.viewUrl}
              alt={image.originalFilename}
              style={{ width: '64px', height: '64px', objectFit: 'cover', borderRadius: '8px', border: '1px solid var(--color-grayscale-200, #DDD)' }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: '13px',
                fontWeight: 500,
                color: 'var(--color-grayscale-900)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {image.originalFilename}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--color-grayscale-400)', marginTop: '4px' }}>
                {(image.fileSize / 1024).toFixed(1)} KB
              </div>
            </div>
            <button
              type="button"
              onClick={handleRemoveImage}
              style={{
                padding: '6px 12px',
                borderRadius: '999px',
                border: '1px solid var(--color-grayscale-300, #B9B9B9)',
                background: 'transparent',
                color: 'var(--color-grayscale-500)',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              삭제
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            style={{
              width: '100%',
              padding: '24px',
              borderRadius: '12px',
              border: '1.5px dashed var(--color-grayscale-200, #DDD)',
              background: 'var(--color-grayscale-50, #FFF)',
              cursor: isUploading ? 'wait' : 'pointer',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: '8px',
              transition: 'border-color 0.15s, background-color 0.15s',
            }}
            onMouseEnter={(e) => {
              if (!isUploading) e.currentTarget.style.borderColor = 'var(--color-primary-600)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--color-grayscale-200)';
            }}
          >
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <rect x="3" y="3" width="18" height="18" rx="3" stroke="var(--color-grayscale-400, #8E8E8E)" strokeWidth="1.5" />
              <circle cx="9" cy="9" r="1.5" fill="var(--color-grayscale-400, #8E8E8E)" />
              <path d="M3 16L8 11L13 16L17 12L21 16" stroke="var(--color-grayscale-400, #8E8E8E)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <div style={{ fontSize: '13px', color: 'var(--color-grayscale-500, #757578)', fontWeight: 500 }}>
              {isUploading ? '업로드 중...' : '클릭하여 스크린샷 업로드'}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--color-grayscale-400, #8E8E8E)' }}>
              JPG, PNG, GIF, WEBP (10MB 이하)
            </div>
          </button>
        )}
        {uploadError && (
          <div style={{ fontSize: '12px', color: 'var(--color-error-500)', marginTop: '6px' }}>
            {uploadError}
          </div>
        )}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/gif,image/webp"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </div>

      {/* 오류 유형 (필수) */}
      <div>
        <div style={labelStyle}>
          오류 유형<span style={requiredMarkStyle}>*</span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {ANSWER_ERROR_TYPES.map((type) => {
            const active = errorType === type;
            return (
              <button
                key={type}
                type="button"
                onClick={() => {
                  setErrorType(type);
                  clearSubmitError();
                }}
                style={{
                  padding: '8px 16px',
                  borderRadius: '999px',
                  border: active ? '1px solid var(--color-primary-600, #626BF7)' : '1px solid var(--color-grayscale-200, #DDD)',
                  backgroundColor: active ? 'var(--color-primary-100, #F2F3FF)' : 'var(--color-grayscale-50, #FFF)',
                  color: active ? 'var(--color-primary-600, #626BF7)' : 'var(--color-grayscale-500, #757578)',
                  fontSize: '13px',
                  fontWeight: active ? 600 : 400,
                  lineHeight: '20px',
                  letterSpacing: '-0.26px',
                  cursor: 'pointer',
                  transition: 'background-color 0.15s, color 0.15s, border-color 0.15s',
                }}
              >
                {type}
              </button>
            );
          })}
        </div>
      </div>

      {/* 입력 문장 (필수) */}
      <div>
        <div style={labelStyle}>
          입력 문장<span style={requiredMarkStyle}>*</span>
        </div>
        <textarea
          value={inputSentence}
          onChange={(e) => {
            setInputSentence(e.target.value);
            clearSubmitError();
          }}
          placeholder="AI에게 입력한 문장을 적어주세요."
          style={{
            ...inputBoxBase,
            minHeight: '96px',
            resize: 'vertical',
          }}
          onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--color-primary-600)'; }}
          onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--color-grayscale-200, #DDD)'; }}
        />
      </div>

      {/* 올바른 내용 (필수, 1줄) */}
      <div>
        <div style={labelStyle}>
          올바른 내용 (1줄)<span style={requiredMarkStyle}>*</span>
        </div>
        <input
          type="text"
          value={correctContent}
          onChange={(e) => {
            // 줄바꿈 차단 (1줄 제한)
            setCorrectContent(e.target.value.replace(/[\r\n]+/g, ' '));
            clearSubmitError();
          }}
          placeholder="실제 사실이나 올바른 계산 결과, 혹은 의도했던 답변 내용 등을 작성해주세요."
          style={inputBoxBase}
          onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--color-primary-600)'; }}
          onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--color-grayscale-200, #DDD)'; }}
        />
      </div>
    </div>
  );
}

export default AnswerDataReportForm;
