// created by ARES team [2026-06-15]
import { useEffect, useState } from 'react';
import axios from 'axios';
import { createDocumentTag, type DocumentTag } from '../../services/tag.service';
import { mapBackendCodeToFrontend, DOCUMENT_CODES, ERROR_MESSAGES } from '../../constants/customCodes';

const DEFAULT_TAG_COLOR = '#9A9180';

interface TagCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreated?: (tag: DocumentTag) => void;
  onError?: (title: string, message: string) => void;
}

function TagCreateModal({ isOpen, onClose, onCreated, onError }: TagCreateModalProps) {
  const [name, setName] = useState('');
  const [inlineError, setInlineError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setName('');
      setInlineError(null);
      setIsSubmitting(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const trimmedName = name.trim();
  const isSubmitDisabled = !trimmedName || isSubmitting;

  const handleSubmit = async () => {
    if (isSubmitDisabled) return;
    setInlineError(null);
    setIsSubmitting(true);
    try {
      const tag = await createDocumentTag({ name: trimmedName, color: DEFAULT_TAG_COLOR });
      onCreated?.(tag);
      onClose();
    } catch (err: unknown) {
      const backendCode = axios.isAxiosError(err) ? err.response?.data?.code : undefined;
      const frontendCode = backendCode ? mapBackendCodeToFrontend(backendCode) : null;

      if (frontendCode === DOCUMENT_CODES.DOC_TAG_DUPLICATE) {
        setInlineError(ERROR_MESSAGES[DOCUMENT_CODES.DOC_TAG_DUPLICATE]);
        return;
      }

      const fallbackMessage = frontendCode
        ? ERROR_MESSAGES[frontendCode]
        : ERROR_MESSAGES[DOCUMENT_CODES.DOC_TAG_CREATE_FAILED];
      onError?.('태그 생성 실패', fallbackMessage);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.4)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: '420px',
          height: '208px',
          borderRadius: '16px',
          background: '#FFF',
          boxShadow: '0 10px 30px 0 rgba(0, 0, 0, 0.14)',
          padding: '24px',
          boxSizing: 'border-box',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          style={{
            color: '#292B2F',
            fontFamily: 'Pretendard',
            fontSize: '17px',
            fontStyle: 'normal',
            fontWeight: 700,
            lineHeight: 'normal',
          }}
        >
          새 태그
        </div>

        <input
          type="text"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (inlineError) setInlineError(null);
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
              e.preventDefault();
              handleSubmit();
            }
          }}
          maxLength={50}
          placeholder="태그 이름"
          style={{
            width: '372px',
            padding: '14px',
            marginTop: '28px',
            borderRadius: '10px',
            border: `1px solid ${inlineError ? '#EF4444' : '#D4D4D4'}`,
            background: '#FFF',
            boxSizing: 'border-box',
            outline: 'none',
            color: '#292B2F',
            fontFamily: 'Pretendard',
            fontSize: '14px',
            fontStyle: 'normal',
            fontWeight: 400,
            lineHeight: 'normal',
          }}
        />

        {inlineError && (
          <div
            style={{
              marginTop: '6px',
              color: '#EF4444',
              fontFamily: 'Pretendard',
              fontSize: '12px',
              fontWeight: 400,
              lineHeight: 'normal',
            }}
          >
            {inlineError}
          </div>
        )}

        <div
          style={{
            marginTop: 'auto',
            display: 'flex',
            justifyContent: 'space-between',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            style={{
              width: '180px',
              padding: '14px 0 13px 0',
              borderRadius: '10px',
              border: '1px solid #D4D4D4',
              background: '#FFF',
              color: '#292B2F',
              fontFamily: 'Pretendard',
              fontSize: '14px',
              fontStyle: 'normal',
              fontWeight: 500,
              lineHeight: 'normal',
              cursor: 'pointer',
            }}
          >
            취소
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitDisabled}
            style={{
              width: '180px',
              padding: '14px 0 13px 0',
              borderRadius: '10px',
              border: 'none',
              background: '#626BF7',
              color: '#FFF',
              fontFamily: 'Pretendard',
              fontSize: '14px',
              fontStyle: 'normal',
              fontWeight: 500,
              lineHeight: 'normal',
              cursor: isSubmitDisabled ? 'not-allowed' : 'pointer',
              opacity: isSubmitDisabled ? 0.5 : 1,
            }}
          >
            만들기
          </button>
        </div>
      </div>
    </div>
  );
}

export default TagCreateModal;
