// created by ARES team [2026-06-17]
import { useEffect, useState } from 'react';
import { assignTagsToDocument, type DocumentTag } from '../../services/tag.service';
import Checkbox from '../../components/common/Checkbox';

interface TagAssignModalProps {
  isOpen: boolean;
  onClose: () => void;
  documentId: string | null;
  documentName: string;
  availableTags: DocumentTag[];
  initialSelectedTagIds: string[];
  onAssigned: () => void;
  onError?: (title: string, message: string) => void;
}

function TagAssignModal({
  isOpen,
  onClose,
  documentId,
  documentName,
  availableTags,
  initialSelectedTagIds,
  onAssigned,
  onError,
}: TagAssignModalProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>(initialSelectedTagIds);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setSelectedIds(initialSelectedTagIds);
      setIsSubmitting(false);
    }
  }, [isOpen, initialSelectedTagIds]);

  if (!isOpen) return null;

  const toggle = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  };

  const handleSubmit = async () => {
    if (!documentId || isSubmitting) return;
    setIsSubmitting(true);
    try {
      await assignTagsToDocument(documentId, selectedIds);
      onAssigned();
      onClose();
    } catch {
      onError?.('태그 적용 실패', '태그 적용 중 오류가 발생했습니다.');
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
          maxHeight: '520px',
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
          태그 지정
        </div>
        <div
          style={{
            marginTop: '6px',
            color: 'var(--color-grayscale-500)',
            fontFamily: 'Pretendard',
            fontSize: '12px',
            fontWeight: 400,
            lineHeight: '18px',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
          title={documentName}
        >
          {documentName}
        </div>

        <div
          style={{
            marginTop: '16px',
            flex: 1,
            overflowY: 'auto',
            minHeight: 0,
            border: '1px solid var(--color-grayscale-200)',
            borderRadius: '10px',
            padding: '6px',
            boxSizing: 'border-box',
          }}
        >
          {availableTags.length === 0 ? (
            <div
              style={{
                padding: '24px 8px',
                textAlign: 'center',
                color: 'var(--color-grayscale-400)',
                fontFamily: 'Pretendard',
                fontSize: '13px',
                lineHeight: '20px',
                whiteSpace: 'pre-wrap',
              }}
            >
              {`사용할 태그가 없습니다.\n'태그 추가' 버튼으로 만들어 보세요.`}
            </div>
          ) : (
            availableTags.map((tag) => {
              const checked = selectedIds.includes(tag.id);
              return (
                <button
                  key={tag.id}
                  type="button"
                  onClick={() => toggle(tag.id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    width: '100%',
                    padding: '8px',
                    border: 'none',
                    background: 'transparent',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    textAlign: 'left',
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.background = 'var(--color-grayscale-100)';
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.background = 'transparent';
                  }}
                >
                  <Checkbox checked={checked} onChange={() => toggle(tag.id)} />
                  <span
                    style={{
                      color: 'var(--color-grayscale-900)',
                      fontFamily: 'Pretendard',
                      fontSize: '13px',
                      fontWeight: 400,
                      lineHeight: '18px',
                      flex: 1,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {tag.name}
                  </span>
                </button>
              );
            })
          )}
        </div>

        <div
          style={{
            marginTop: '20px',
            display: 'flex',
            justifyContent: 'space-between',
            gap: '12px',
          }}
        >
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            style={{
              flex: 1,
              padding: '14px 0 13px 0',
              borderRadius: '10px',
              border: '1px solid #D4D4D4',
              background: '#FFF',
              color: '#292B2F',
              fontFamily: 'Pretendard',
              fontSize: '14px',
              fontWeight: 500,
              lineHeight: 'normal',
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
            }}
          >
            취소
          </button>
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting}
            style={{
              flex: 1,
              padding: '14px 0 13px 0',
              borderRadius: '10px',
              border: 'none',
              background: '#626BF7',
              color: '#FFF',
              fontFamily: 'Pretendard',
              fontSize: '14px',
              fontWeight: 500,
              lineHeight: 'normal',
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
              opacity: isSubmitting ? 0.5 : 1,
            }}
          >
            적용
          </button>
        </div>
      </div>
    </div>
  );
}

export default TagAssignModal;
