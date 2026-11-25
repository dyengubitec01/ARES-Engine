// created by ARES team [2026-06-17]
import { useEffect, useState } from 'react';
import axios from 'axios';
import {
  getDocumentTags,
  updateDocumentTag,
  deleteDocumentTag,
  countDocumentsByTag,
  type DocumentTag,
} from '../../services/tag.service';
import { useModal } from '../../contexts/ModalContext';
import { mapBackendCodeToFrontend, DOCUMENT_CODES, ERROR_MESSAGES } from '../../constants/customCodes';

interface TagManageModalProps {
  isOpen: boolean;
  onClose: () => void;
  onChanged: () => void;
  onError?: (title: string, message: string) => void;
}

function TagManageModal({ isOpen, onClose, onChanged, onError }: TagManageModalProps) {
  const { showConfirm } = useModal();
  const [tags, setTags] = useState<DocumentTag[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [editError, setEditError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadTags = async () => {
    setIsLoading(true);
    try {
      const items = await getDocumentTags();
      setTags(items);
    } catch {
      onError?.('태그 조회 실패', '태그 목록을 불러오지 못했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadTags();
    } else {
      setEditingId(null);
      setEditName('');
      setEditError(null);
      setIsSubmitting(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  if (!isOpen) return null;

  const startEdit = (tag: DocumentTag) => {
    setEditingId(tag.id);
    setEditName(tag.name);
    setEditError(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditName('');
    setEditError(null);
  };

  const saveEdit = async (tagId: string) => {
    const trimmed = editName.trim();
    if (!trimmed) {
      setEditError('태그 이름을 입력해주세요.');
      return;
    }
    setIsSubmitting(true);
    try {
      await updateDocumentTag(tagId, { name: trimmed });
      await loadTags();
      onChanged();
      cancelEdit();
    } catch (err: unknown) {
      const backendCode = axios.isAxiosError(err) ? err.response?.data?.code : undefined;
      const frontendCode = backendCode ? mapBackendCodeToFrontend(backendCode) : null;
      if (frontendCode === DOCUMENT_CODES.DOC_TAG_DUPLICATE) {
        setEditError(ERROR_MESSAGES[DOCUMENT_CODES.DOC_TAG_DUPLICATE]);
      } else {
        setEditError(frontendCode ? ERROR_MESSAGES[frontendCode] : '태그 수정에 실패했습니다.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (tag: DocumentTag) => {
    let count = 0;
    try {
      count = await countDocumentsByTag(tag.id);
    } catch {
      // 카운트 실패는 무시하고 일반 메시지로 진행
    }
    const message =
      count > 0
        ? `이 태그가 부여된 문서 ${count}건에서 함께 제거됩니다.\n삭제하시겠습니까?`
        : '이 태그를 삭제하시겠습니까?';
    showConfirm(
      `'${tag.name}' 태그 삭제`,
      message,
      async () => {
        try {
          await deleteDocumentTag(tag.id);
          await loadTags();
          onChanged();
        } catch {
          onError?.('태그 삭제 실패', '태그 삭제 중 오류가 발생했습니다.');
        }
      },
      '삭제',
      '취소'
    );
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
          width: '460px',
          maxHeight: '560px',
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
            marginBottom: '20px',
          }}
        >
          태그 관리
        </div>

        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
          {isLoading ? (
            <div
              style={{
                padding: '40px 0',
                textAlign: 'center',
                color: 'var(--color-grayscale-400)',
                fontFamily: 'Pretendard',
                fontSize: '13px',
              }}
            >
              불러오는 중...
            </div>
          ) : tags.length === 0 ? (
            <div
              style={{
                padding: '40px 0',
                textAlign: 'center',
                color: 'var(--color-grayscale-400)',
                fontFamily: 'Pretendard',
                fontSize: '13px',
                lineHeight: '20px',
              }}
            >
              내 태그가 없습니다.{'\n'}
              '태그 추가' 버튼으로 만들어 보세요.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {tags.map((tag) => {
                const isEditing = editingId === tag.id;
                return (
                  <div
                    key={tag.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '10px 8px',
                      borderBottom: '1px solid var(--color-grayscale-150)',
                    }}
                  >
                    {isEditing ? (
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => {
                            setEditName(e.target.value);
                            if (editError) setEditError(null);
                          }}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
                              e.preventDefault();
                              saveEdit(tag.id);
                            } else if (e.key === 'Escape') {
                              cancelEdit();
                            }
                          }}
                          maxLength={50}
                          autoFocus
                          disabled={isSubmitting}
                          style={{
                            width: '100%',
                            padding: '8px 10px',
                            borderRadius: '8px',
                            border: `1px solid ${editError ? '#EF4444' : 'var(--color-grayscale-200)'}`,
                            background: '#FFF',
                            boxSizing: 'border-box',
                            outline: 'none',
                            color: '#292B2F',
                            fontFamily: 'Pretendard',
                            fontSize: '13px',
                            fontWeight: 400,
                            lineHeight: 'normal',
                          }}
                        />
                        {editError && (
                          <div
                            style={{
                              color: '#EF4444',
                              fontFamily: 'Pretendard',
                              fontSize: '11px',
                              fontWeight: 400,
                              lineHeight: 'normal',
                            }}
                          >
                            {editError}
                          </div>
                        )}
                      </div>
                    ) : (
                      <span
                        style={{
                          flex: 1,
                          color: 'var(--color-grayscale-900)',
                          fontFamily: 'Pretendard',
                          fontSize: '14px',
                          fontWeight: 500,
                          lineHeight: '20px',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {tag.name}
                      </span>
                    )}

                    {isEditing ? (
                      <>
                        <button
                          type="button"
                          onClick={() => saveEdit(tag.id)}
                          disabled={isSubmitting}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '8px',
                            border: 'none',
                            background: '#626BF7',
                            color: '#FFF',
                            fontFamily: 'Pretendard',
                            fontSize: '12px',
                            fontWeight: 500,
                            lineHeight: 'normal',
                            cursor: isSubmitting ? 'not-allowed' : 'pointer',
                            opacity: isSubmitting ? 0.5 : 1,
                          }}
                        >
                          저장
                        </button>
                        <button
                          type="button"
                          onClick={cancelEdit}
                          disabled={isSubmitting}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '8px',
                            border: '1px solid var(--color-grayscale-200)',
                            background: '#FFF',
                            color: 'var(--color-grayscale-900)',
                            fontFamily: 'Pretendard',
                            fontSize: '12px',
                            fontWeight: 500,
                            lineHeight: 'normal',
                            cursor: isSubmitting ? 'not-allowed' : 'pointer',
                          }}
                        >
                          취소
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => startEdit(tag)}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '8px',
                            border: '1px solid var(--color-grayscale-200)',
                            background: 'var(--color-grayscale-50)',
                            color: 'var(--color-grayscale-900)',
                            fontFamily: 'Pretendard',
                            fontSize: '12px',
                            fontWeight: 500,
                            lineHeight: 'normal',
                            cursor: 'pointer',
                          }}
                        >
                          수정
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(tag)}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '8px',
                            border: '1px solid #FCA5A5',
                            background: '#FFF',
                            color: '#EF4444',
                            fontFamily: 'Pretendard',
                            fontSize: '12px',
                            fontWeight: 500,
                            lineHeight: 'normal',
                            cursor: 'pointer',
                          }}
                        >
                          삭제
                        </button>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div style={{ marginTop: '20px', display: 'flex', justifyContent: 'flex-end' }}>
          <button
            type="button"
            onClick={onClose}
            style={{
              width: '120px',
              padding: '12px 0',
              borderRadius: '10px',
              border: '1px solid var(--color-grayscale-200)',
              background: '#FFF',
              color: '#292B2F',
              fontFamily: 'Pretendard',
              fontSize: '14px',
              fontWeight: 500,
              lineHeight: 'normal',
              cursor: 'pointer',
            }}
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

export default TagManageModal;
