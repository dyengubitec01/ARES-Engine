// created by ARES team [2026-01-30]
import type React from 'react';
import { useState, useEffect, useRef, useCallback } from 'react';
import { DocumentFile, DocumentTab, UploadProgress } from './types';
import { docsFavIcon, docsFavFillIcon, docsUploadIcon } from '../../assets/docs';
import DocsDownloadIcon from '../../assets/docs/download.svg?react';
import { chatIcon } from '../../assets/chats';
import StatusBadge from '../../components/common/StatusBadge';
import Pagination from '../../components/common/Pagination';
import DropdownMenu from '../../components/common/DropdownMenu';
import Checkbox from '../../components/common/Checkbox';
import type { SortOrder } from '../../components/common/SortToggleButton';
import DocumentPageHeader from './DocumentPageHeader';
import DocumentFileCell from './DocumentFileCell';
import TagAssignModal from './TagAssignModal';
import { type DocumentTag } from '../../services/tag.service';
import SelectionActionBar from '../../components/common/SelectionActionBar';
import { useModal } from '../../contexts/ModalContext';
import { useAuth } from '../auth/AuthContext';
import { downloadFile } from '../../services/document.service';
import { softDeleteDocument } from '../../services/admin.service';
import { GRADIENT, GRADIENT_ACTIVE_SHADOW, gradientButtonBase } from '../../styles/buttonStyles';
import TableSkeleton from '../../components/common/TableSkeleton';
import BoardModal from '../../components/common/BoardModal';
import { BoardTypeIdMap } from '../../components/common/Board/useBoard';
import { getBoardTypes } from '../../services/board.service';
import { usePersistedToggle } from '../../hooks/usePersistedToggle';
import { useToasts } from '../../hooks/useToasts';

// 상태별 설정
const PROCESSING_STATUS = { bg: 'var(--status-processing-bg)', text: 'AI 처리 중', color: 'var(--status-processing-text)', border: '1px solid var(--status-processing-border)', tooltip: '문서를 AI 지식으로 변환하고 있습니다.' } as const;
const EMBEDDING_STATUS_CONFIG = {
  uploading: { bg: 'var(--color-grayscale-100)', text: '업로드 중', color: 'var(--color-grayscale-400)', border: '1px solid var(--color-grayscale-150)', tooltip: '파일을 전송 중입니다. 잠시만 기다려주세요.' },
  uploaded: { bg: 'var(--status-uploaded-bg)', text: '업로드 완료', color: 'var(--status-uploaded-text)', border: '1px solid var(--status-uploaded-border)', tooltip: '전송 완료. AI 학습을 요청해주세요.' },
  pending_approval: { bg: 'var(--status-pending-bg)', text: '승인 대기', color: 'var(--status-pending-text)', border: '1px solid var(--status-pending-border)', tooltip: '관리자가 확인 중입니다. 승인 후 AI 학습이 시작됩니다.' },
  queued: PROCESSING_STATUS,
  parsing: PROCESSING_STATUS,
  chunking: PROCESSING_STATUS,
  embedding: PROCESSING_STATUS,
  upserting: PROCESSING_STATUS,
  rejected: { bg: 'var(--status-rejected-bg)', text: '승인 반려', color: 'var(--status-rejected-text)', border: '1px solid var(--status-rejected-border)', tooltip: '관리자가 요청을 반려했습니다.' },
  completed: { bg: 'var(--status-success-bg)', text: '사용 가능', color: 'var(--status-success-text)', border: '1px solid var(--status-success-border)', tooltip: '학습 완료. 이제 채팅 답변에 이 문서가 활용됩니다.' },
  failed: { bg: 'var(--status-error-bg)', text: '오류', color: 'var(--status-error-text)', border: '1px solid var(--status-error-border)', tooltip: '데이터 처리 오류입니다. 다시 업로드해 주세요.' },
  default: { bg: 'var(--color-grayscale-100)', text: '업로드 중', color: 'var(--color-grayscale-400)', border: '1px solid var(--color-grayscale-150)', tooltip: '파일을 전송 중입니다. 잠시만 기다려주세요.' },
} as const;

const GUIDE_STEPS = [
  { num: 1, bg: '#EDFAF5', color: '#0EA874', title: '파일 업로드', desc: '보관함에 파일이 저장됩니다' },
  { num: 2, bg: '#FEF9EC', color: '#E29500', title: 'AI 지식 추가 요청', desc: '팀장 승인 후 AI 학습이 시작됩니다' },
  { num: 3, bg: 'var(--color-primary-100)', color: 'var(--color-primary-600)', title: 'AI 응답에 활용', desc: 'AI 어시스턴트가 문서를 참고합니다.' },
] as const;

export interface MyDocumentsListProps {
  myDocuments: DocumentFile[];
  isLoadingMyDocuments: boolean;
  activeTab: DocumentTab;
  sortOrder: SortOrder;
  onSortToggle: () => void;
  uploads: Map<string, UploadProgress>;
  fileInputRef: React.RefObject<HTMLInputElement>;
  selectedDocIds: string[];
  embeddingDocIds: Set<string>;
  embeddingProgress: Map<string, number>;
  isEmbedding: boolean;
  currentPage: number;
  totalItems: number;
  onPageChange: (page: number) => void;
  onToggleFavorite: (documentId: string, isFavorite: boolean) => Promise<void>;
  onFileSelect: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onUploadClick: () => void;
  onRemoveUpload: (fileName: string) => void;
  onToggleDocSelection: (documentId: string) => void;
  onRequestEmbedding: () => Promise<void>;
  onTabChange: (tab: DocumentTab) => void;
  onRefresh: () => Promise<void>;
  knowledgeToggleState: Record<string, boolean>;
  onKnowledgeToggle: (docId: string, contentId: string) => void;
  onFileDrop?: (files: FileList) => void;
  dashboardRefreshKey?: number;
  onHelpClick?: () => void;
  onSearchChange: (value: string) => void;
  deptOptions: { id: string; label: string }[];
  selectedDeptIds: string[];
  onDeptIdsChange: (ids: string[]) => void;
  tagOptions: { id: string; label: string }[];
  selectedTagIds: string[];
  onTagIdsChange: (ids: string[]) => void;
  onAfterTagCreated?: () => void;
  availableTags: DocumentTag[];
  onAfterTagsChanged?: () => void;
}

function MyDocumentsList({
  myDocuments,
  isLoadingMyDocuments,
  activeTab,
  sortOrder,
  onSortToggle,
  uploads,
  fileInputRef,
  selectedDocIds,
  embeddingDocIds,
  embeddingProgress,
  isEmbedding,
  currentPage,
  totalItems,
  onPageChange,
  onToggleFavorite,
  onFileSelect,
  onUploadClick,
  onRemoveUpload,
  onToggleDocSelection,
  onRequestEmbedding,
  onTabChange,
  onRefresh,
  knowledgeToggleState,
  onKnowledgeToggle,
  onFileDrop,
  dashboardRefreshKey,
  onHelpClick,
  onSearchChange,
  deptOptions,
  selectedDeptIds,
  onDeptIdsChange,
  tagOptions,
  selectedTagIds,
  onTagIdsChange,
  onAfterTagCreated,
  availableTags,
  onAfterTagsChanged,
}: MyDocumentsListProps) {

  const { showAlert, showConfirm } = useModal();
  const { isDownload, isAdmin, isSoftDelete } = useAuth();
  const canDelete = isAdmin || isSoftDelete;

  const [errorReportOpen, setErrorReportOpen] = useState(false);
  const [errorReportBoardTypeIds, setErrorReportBoardTypeIds] = useState<BoardTypeIdMap | null>(null);
  const { showError, showSuccess, ToastStack } = useToasts();

  const [tagAssignTarget, setTagAssignTarget] = useState<DocumentFile | null>(null);

  const handleErrorReport = async () => {
    try {
      const types = await getBoardTypes();
      const errorType = types.find(t => t.name === 'feedback');
      const suggestionType = types.find(t => t.name === 'suggestion');
      const answerSuggestionType = types.find(t => t.name === 'answer_suggestion');
      if (errorType && suggestionType && answerSuggestionType) {
        setErrorReportBoardTypeIds({
          error: errorType.id,
          suggestion: suggestionType.id,
          answerSuggestion: answerSuggestionType.id,
        });
        setErrorReportOpen(true);
      }
    } catch {
      // 실패 시 무시
    }
  };

  const handleDelete = (): void => {
    if (selectedDocIds.length === 0) {
      showAlert('문서 선택 필요', '삭제할 문서를 선택해주세요.', '확인');
      return;
    }
    showConfirm(
      '문서 삭제',
      `선택한 ${selectedDocIds.length}개 문서를 삭제하시겠습니까?`,
      async () => {
        try {
          for (const documentId of selectedDocIds) {
            await softDeleteDocument(documentId);
          }
          await onRefresh();
          showSuccess({ title: '삭제 완료', message: '문서가 삭제되었습니다.' });
        } catch {
          showError({ title: '삭제 실패', message: '잠시 후 다시 시도해주세요.' });
        }
      },
      '삭제',
      '취소'
    );
  };

  const [isDragOver, setIsDragOver] = useState(false);
  const [isDropZoneHover, setIsDropZoneHover] = useState(false);
  const uploadPanel = usePersistedToggle('upload_panel_open', false);
  const [floatingBtnTop, setFloatingBtnTop] = useState(50);
  const isDraggingBtn = useRef(false);
  const hasDragged = useRef(false);
  const dragStartY = useRef(0);
  const dragStartTop = useRef(0);

  const handleBtnMouseDown = useCallback((e: React.MouseEvent) => {
    isDraggingBtn.current = true;
    hasDragged.current = false;
    dragStartY.current = e.clientY;
    dragStartTop.current = floatingBtnTop;
    e.preventDefault();
  }, [floatingBtnTop]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDraggingBtn.current) return;
      const parentEl = document.querySelector('[data-floating-parent]') as HTMLElement;
      if (!parentEl) return;
      const parentRect = parentEl.getBoundingClientRect();
      const deltaY = e.clientY - dragStartY.current;
      if (Math.abs(deltaY) > 3) hasDragged.current = true;
      const newTopPx = (dragStartTop.current / 100) * parentRect.height + deltaY;
      const newTopPercent = Math.max(10, Math.min(90, (newTopPx / parentRect.height) * 100));
      setFloatingBtnTop(newTopPercent);
    };
    const handleMouseUp = () => {
      isDraggingBtn.current = false;
    };
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, []);
  const itemsPerPage = 8;
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  useEffect(() => {
    const handleDocumentClick = () => setOpenMenuId(null);
    document.addEventListener('click', handleDocumentClick);
    return () => document.removeEventListener('click', handleDocumentClick);
  }, []);
  
  const currentDocuments = myDocuments || [];

  const renderHeader = (): JSX.Element => (
    <DocumentPageHeader
      title="문서 목록"
      dashboardRefreshKey={dashboardRefreshKey}
      tabs={[
        { key: 'dept' as DocumentTab, label: '부서 문서' },
        { key: 'my' as DocumentTab, label: '내 문서' },
        { key: 'public' as DocumentTab, label: '공통 문서' },
        { key: 'favorite' as DocumentTab, label: '북마크' },
      ]}
      activeTab={activeTab}
      onTabChange={onTabChange}
      sortOrder={sortOrder}
      onSortToggle={onSortToggle}
      canDelete={canDelete}
      onDelete={handleDelete}
      onHelpClick={onHelpClick}
      onSearchChange={onSearchChange}
      onTagCreated={() => {
        showSuccess({ title: '태그 생성 완료', message: '새 태그가 만들어졌습니다.' });
        onAfterTagCreated?.();
      }}
      onTagCreateError={(title, message) => showError({ title, message })}
      onTagsChanged={() => {
        onAfterTagsChanged?.();
      }}
      deptOptions={deptOptions}
      selectedDeptIds={selectedDeptIds}
      onDeptIdsChange={onDeptIdsChange}
      showDeptFilter={activeTab === 'dept'}
      tagOptions={tagOptions}
      selectedTagIds={selectedTagIds}
      onTagIdsChange={onTagIdsChange}
    />
  );

  // 개별 문서 행 렌더링
  const renderDocumentRow = (doc: DocumentFile): JSX.Element => {
    const isSelected = selectedDocIds.includes(doc.id);
    const isDocEmbedding = embeddingDocIds.has(doc.id);
    const embeddingProgressValue = embeddingProgress.get(doc.id) || 0;

    const getEmbeddingStatusBadge = () => {
      const status = doc.latestContent?.status;

      // 실시간 스트리밍 우선 처리
      if (isDocEmbedding) {
        return (
          <StatusBadge
            label={`임베딩 중 ${embeddingProgressValue}%`}
            bg="var(--color-accent-dark)"
            color="white"
          />
        );
      }

      // 상태별 설정 적용
      const config = EMBEDDING_STATUS_CONFIG[status as keyof typeof EMBEDDING_STATUS_CONFIG] || EMBEDDING_STATUS_CONFIG.default;

      if (status === 'failed') {
        return (
          <StatusBadge
            label={config.text}
            bg={config.bg}
            color={config.color}
            border={config.border}
            tooltip={config.tooltip}
            hoverLabel="오류신고"
            hoverBg="var(--color-error-100)"
            hoverColor="var(--color-error-600)"
            hoverBorder="1px solid var(--color-error-300)"
            onHoverAction={handleErrorReport}
          />
        );
      }

      if (status === 'rejected') {
        const rejectedTooltip = doc.latestContent?.statusReason || config.tooltip;
        return (
          <StatusBadge
            label={config.text}
            bg={config.bg}
            color={config.color}
            border={config.border}
            tooltip={rejectedTooltip}
          />
        );
      }

      return (
        <StatusBadge
          label={config.text}
          bg={config.bg}
          color={config.color}
          border={config.border}
          tooltip={config.tooltip}
        />
      );
    };

    return (
      <tr key={doc.id} style={{
        backgroundColor: isSelected ? 'var(--color-primary-600-100)' : 'transparent',
        transition: 'background-color 0.2s'
      }}>
        <td style={{ padding: '12px', width: '1%', whiteSpace: 'nowrap', textAlign: 'center', borderBottom: '1px solid var(--color-grayscale-150)' }}>
          <Checkbox
            checked={isSelected}
            onChange={() => onToggleDocSelection(doc.id)}
            title={isSelected ? '선택 해제' : '선택'}
          />
        </td>
        <td style={{ padding: '12px', borderBottom: '1px solid var(--color-grayscale-150)', overflow: 'hidden', maxWidth: 0 }}>
          <DocumentFileCell
            filename={doc.latestContent?.originalFilename || doc.title || ''}
            fileSize={doc.latestContent?.fileSize}
            tags={doc.myTags}
            onAddTagClick={() => setTagAssignTarget(doc)}
          />
        </td>
        <td style={{ padding: '12px', color: 'var(--color-grayscale-500)', fontSize: '12px', fontWeight: '400', lineHeight: '16px', letterSpacing: '-0.24px',  textAlign: 'center', whiteSpace: 'nowrap', borderBottom: '1px solid var(--color-grayscale-150)' }}>
          {doc.uploaderDepartment ? doc.uploaderDepartment.split('/').pop() : '-'}
        </td>
        <td style={{ padding: '12px', color: 'var(--color-grayscale-500)', fontSize: '12px', fontWeight: '400', lineHeight: '16px', letterSpacing: '-0.24px',  textAlign: 'center', whiteSpace: 'nowrap', borderBottom: '1px solid var(--color-grayscale-150)' }}>
          {new Date(doc.latestContent?.createdAt || doc.createdAt).toLocaleDateString('en-CA', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            timeZone: 'Asia/Seoul'
          })}
        </td>
        <td style={{ padding: '12px', textAlign: 'center', whiteSpace: 'nowrap', borderBottom: '1px solid var(--color-grayscale-150)' }}>
          {getEmbeddingStatusBadge()}
        </td>
        <td style={{ padding: '12px', textAlign: 'center', whiteSpace: 'nowrap', borderBottom: '1px solid var(--color-grayscale-150)' }}>
          {(() => {
            const isCompleted = doc.latestContent?.status === 'completed';
            const isOn = knowledgeToggleState[doc.id] ?? false;

            if (!isCompleted) {
              return (
                <button
                  disabled
                  style={{
                    width: '36px', height: '20px',
                    borderRadius: '10px',
                    backgroundColor: 'var(--color-grayscale-200)',
                    border: '1px solid var(--color-grayscale-200)',
                    position: 'relative',
                    cursor: 'not-allowed',
                    padding: 0,
                    display: 'inline-flex',
                    alignItems: 'center',
                  }}
                  title="임베딩 완료 후 사용 가능"
                >
                  <span style={{
                    width: '16px', height: '16px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--color-grayscale-100)',
                    position: 'absolute',
                    left: '2px',
                    transition: 'left 0.2s',
                  }} />
                </button>
              );
            }

            return (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onKnowledgeToggle(doc.id, doc.latestContent?.id);
                }}
                style={{
                  width: '36px', height: '20px',
                  borderRadius: '10px',
                  backgroundColor: isOn ? 'var(--color-primary-600)' : 'var(--color-grayscale-300)',
                  border: `1px solid ${isOn ? 'var(--color-primary-600)' : 'var(--color-grayscale-300)'}`,
                  position: 'relative',
                  cursor: 'pointer',
                  padding: 0,
                  display: 'inline-flex',
                  alignItems: 'center',
                  transition: 'background-color 0.2s, border-color 0.2s',
                }}
                title={isOn ? 'AI 지식 활용 끄기' : 'AI 지식 활용 켜기'}
              >
                <span style={{
                  width: '16px', height: '16px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--color-grayscale-50)',
                  position: 'absolute',
                  left: isOn ? '17px' : '2px',
                  transition: 'left 0.2s',
                }} />
              </button>
            );
          })()}
        </td>
        <td style={{ padding: '12px', width: '1%', whiteSpace: 'nowrap', textAlign: 'center', borderBottom: '1px solid var(--color-grayscale-150)' }}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleFavorite(doc.id, doc.isFavorite);
            }}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto',
              transition: 'transform 0.2s',
              padding: '0'
            }}
            onMouseOver={(e) => (e.currentTarget.style.transform = 'scale(1.2)')}
            onMouseOut={(e) => (e.currentTarget.style.transform = 'scale(1)')}
            title={doc.isFavorite ? '북마크 해제' : '북마크'}
          >
            <img
              src={doc.isFavorite ? docsFavFillIcon : docsFavIcon}
              alt={doc.isFavorite ? '북마크됨' : '북마크'}
              style={{ width: '20px', height: '20px' }}
            />
          </button>
        </td>
        {isDownload && (
          <td style={{ padding: '12px', width: '1%', whiteSpace: 'nowrap', textAlign: 'center', borderBottom: '1px solid var(--color-grayscale-150)', position: 'relative' }}>
            <DropdownMenu
              isOpen={openMenuId === doc.id}
              onToggle={() => setOpenMenuId(openMenuId === doc.id ? null : doc.id)}
              onClose={() => setOpenMenuId(null)}
              items={[{
                label: '다운로드',
                icon: DocsDownloadIcon,
                onClick: async () => {
                  try {
                    await downloadFile(doc.latestContent.id, doc.latestContent.originalFilename);
                  } catch {
                    showError({ title: '다운로드 실패', message: '잠시 후 다시 시도해주세요.' });
                  }
                }
              }]}
            />
          </td>
        )}
      </tr>
    );
  };

  const renderHiddenFileInput = (): JSX.Element => {
    return (
      <input
        ref={fileInputRef}
        type="file"
        multiple
        onChange={onFileSelect}
        accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.xlsm,.hwp,.hwpx,.txt,.csv"
        style={{ display: 'none' }}
      />
    );
  };

  const uploadArray = Array.from(uploads.values());
  const dropInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0 && onFileDrop) {
      onFileDrop(e.dataTransfer.files);
    }
  }, [onFileDrop]);

  const handleDropZoneClick = useCallback(() => {
    dropInputRef.current?.click();
  }, []);

  const handleDropInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0 && onFileDrop) {
      onFileDrop(e.target.files);
    }
    if (dropInputRef.current) {
      dropInputRef.current.value = '';
    }
  }, [onFileDrop]);

  // 플로팅 업로드 버튼
  const renderFloatingUploadButton = (): JSX.Element => (
    <button
      onMouseDown={(e) => { handleBtnMouseDown(e); e.currentTarget.style.background = GRADIENT.primaryActive; e.currentTarget.style.boxShadow = GRADIENT_ACTIVE_SHADOW; }}
      onClick={() => {
        if (!hasDragged.current) uploadPanel.toggle();
      }}
      style={{
        position: 'absolute',
        right: 0,
        top: `${floatingBtnTop}%`,
        transform: 'translateY(-50%)',
        zIndex: 10,
        display: 'inline-flex',
        padding: '36px 12px',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        gap: '4px',
        borderRadius: '20px 0 0 20px',
        border: '1px solid var(--color-grayscale-50)',
        borderRight: 'none',
        background: GRADIENT.primarySoft,
        boxShadow: '2px 2px 20px 0 rgba(0, 0, 0, 0.08)',
        cursor: 'grab',
        transition: 'opacity 0.2s',
        userSelect: 'none' as const,
      }}
      onMouseOver={(e) => { e.currentTarget.style.background = GRADIENT.primaryHover; }}
      onMouseOut={(e) => { e.currentTarget.style.background = GRADIENT.primarySoft; e.currentTarget.style.boxShadow = '2px 2px 20px 0 rgba(0, 0, 0, 0.08)'; }}
      onMouseUp={(e) => { e.currentTarget.style.background = GRADIENT.primaryHover; e.currentTarget.style.boxShadow = '2px 2px 20px 0 rgba(0, 0, 0, 0.08)'; }}
      title={uploadPanel.isOpen ? '업로드 패널 닫기' : '업로드 패널 열기'}
    >
      <img
        src={docsUploadIcon}
        alt="upload"
        style={{
          width: '24px',
          height: '24px',
          filter: 'brightness(0) invert(1)',
        }}
      />
      <span style={{
        overflow: 'hidden',
        color: '#FFF',
        textOverflow: 'ellipsis',
        fontSize: '13px',
        fontWeight: '600',
        lineHeight: '20px',
        letterSpacing: '-0.26px',
        
      }}>
        업로드
      </span>
    </button>
  );

  // 드래그앤드롭 업로드 영역 렌더링
  const renderDropZone = (): JSX.Element => (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: '12px',
      flex: 1,
      minHeight: 0,
    }}>
      <div style={{
        width: '260px',
        minHeight: '280px',
        borderRadius: '10px',
        border: '1px solid var(--color-grayscale-200)',
        background: 'var(--color-grayscale-50)',
        boxShadow: '2px 2px 6px 0 rgba(0, 0, 0, 0.05)',
        display: 'flex',
        flexDirection: 'column',
        padding: '10px 12px',
        gap: '8px',
      }}>
        <div style={{ paddingTop: '4px' }}>
          <div style={{
            color: 'var(--color-grayscale-900)',
            fontSize: '14px',
            fontWeight: '600',
            lineHeight: '20px',
            letterSpacing: '-0.28px',
            
          }}>
            파일 업로드
          </div>
          <div style={{
            color: 'var(--color-grayscale-300)',
            fontSize: '11px',
            fontWeight: '400',
            lineHeight: '16px',
            
            marginTop: '4px',
          }}>
            문서를 업로드해 AI 지식으로 활용하세요
          </div>
        </div>

        <input
          ref={dropInputRef}
          type="file"
          multiple
          onChange={handleDropInputChange}
          accept=".pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.xlsm,.hwp,.hwpx,.txt,.csv"
          style={{ display: 'none' }}
        />

        <div
          onClick={handleDropZoneClick}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onMouseEnter={() => setIsDropZoneHover(true)}
          onMouseLeave={() => setIsDropZoneHover(false)}
          style={{
            width: '235px',
            height: '178px',
            boxSizing: 'border-box' as const,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            borderRadius: '10px',
            border: `1px dashed ${(isDragOver || isDropZoneHover) ? 'var(--color-primary-600)' : 'var(--color-grayscale-200)'}`,
            background: (isDragOver || isDropZoneHover) ? 'var(--color-primary-100)' : 'var(--color-grayscale-50)',
            cursor: 'pointer',
            transition: 'border-color 0.2s, background 0.2s, gap 0.2s',
            gap: '8px',
            alignSelf: 'center',
          }}
        >
          {/* 업로드 아이콘 */}
          <div style={{
            borderRadius: '8px',
            border: (isDragOver || isDropZoneHover) ? '1px solid #8C9BFE' : '1px solid var(--color-grayscale-150)',
            background: (isDragOver || isDropZoneHover) ? '#8C9BFE' : 'var(--color-grayscale-150)',
            display: 'flex',
            padding: '8px',
            justifyContent: 'center',
            alignItems: 'center',
            gap: '4px',
            transition: 'background 0.2s, border-color 0.2s',
          }}>
            <img src={docsUploadIcon} alt="upload" style={{
              width: '20px',
              height: '20px',
              filter: (isDragOver || isDropZoneHover) ? 'brightness(0) invert(1)' : 'none',
              transition: 'filter 0.2s',
            }} />
          </div>

          <div style={{
            color: 'var(--color-grayscale-500)',
            textAlign: 'center',

            fontSize: '13px',
            fontStyle: 'normal',
            fontWeight: '600',
            lineHeight: '20px',
            letterSpacing: '-0.26px',
            
          }}>
            파일을 드래그하거나 클릭하세요
          </div>
          <div style={{
            color: 'var(--color-grayscale-300)',
            textAlign: 'center',
            fontSize: '11px',
            fontWeight: '400',
            lineHeight: '16px',
            
          }}>
            PDF, DOC, DOCX, HWP, HWPX,<br />
            XLS, XLSX, CSV, PPT, PPTX
          </div>

          {/* 파일 선택 버튼 */}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onUploadClick();
            }}
            style={{
              borderRadius: '999px',
              border: (isDragOver || isDropZoneHover) ? '1px solid transparent' : '1px solid var(--color-primary-600)',
              background: (isDragOver || isDropZoneHover)
                ? 'linear-gradient(127deg, var(--color-primary-600-400) 0%, var(--color-primary-600) 57.21%, var(--color-primary-600) 95.67%)'
                : 'var(--color-grayscale-50)',
              color: (isDragOver || isDropZoneHover) ? '#FFF' : 'var(--color-primary-600)',
              fontSize: '14px',
              fontWeight: '600',
              lineHeight: '20px',
              letterSpacing: '-0.28px',
              
              padding: '6px 16px',
              cursor: 'pointer',
              transition: 'background 0.2s, color 0.2s, border 0.2s',
              marginTop: '4px',
            }}
          >
            파일 선택
          </button>
        </div>

        {/* 업로드 진행 상태 */}
        {uploadArray.length > 0 && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            maxHeight: '200px',
            overflowY: 'auto',
          }}>
            {uploadArray.map(upload => {
              const progressPercent = upload.status === 'uploading' ? upload.progress : (upload.status === 'uploaded' ? 100 : 0);
              const isComplete = upload.status === 'uploaded' || progressPercent === 100;
              const barColor = isComplete ? 'var(--color-primary-600)' : 'var(--color-primary-600-400)';

              return (
                <div key={upload.fileName} style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '4px',
                }}>
                  <div style={{
                    fontSize: '12px',
                    fontWeight: '500',
                    color: 'var(--color-grayscale-900)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                    title={upload.fileName}
                  >
                    {upload.fileName}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div style={{
                      flex: 1, height: '4px', borderRadius: '2px',
                      background: 'var(--color-grayscale-150)',
                    }}>
                      <div style={{
                        width: `${progressPercent}%`, height: '100%', borderRadius: '2px',
                        background: barColor, transition: 'width 0.3s, background 0.3s',
                      }} />
                    </div>
                    <span style={{
                      fontSize: '11px', fontWeight: '500', color: 'var(--color-grayscale-400)',
                      flexShrink: 0, minWidth: '28px', textAlign: 'right',
                    }}>
                      {progressPercent}%
                    </span>
                    <button
                      onClick={(e) => { e.stopPropagation(); onRemoveUpload(upload.fileName); }}
                      style={{
                        background: 'none', border: 'none', cursor: 'pointer',
                        fontSize: '12px', color: 'var(--color-grayscale-500)', padding: '0',
                        lineHeight: '1', flexShrink: 0, transition: 'color 0.2s',
                      }}
                      onMouseOver={(e) => (e.currentTarget.style.color = 'var(--color-error-500)')}
                      onMouseOut={(e) => (e.currentTarget.style.color = 'var(--color-grayscale-500)')}
                      title="업로드 취소"
                    >
                      ✕
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* AI 지식 추가 버튼 */}
      {isEmbedding && (
        <button
          onClick={onRequestEmbedding}
          disabled={selectedDocIds.length === 0}
          style={{
            ...gradientButtonBase,
            background: selectedDocIds.length > 0 ? GRADIENT.primary : GRADIENT.primarySoft,
            padding: '10px 12px',
            height: '46px',
            boxSizing: 'border-box' as const,
            borderRadius: '50px',
            cursor: selectedDocIds.length > 0 ? 'pointer' : 'not-allowed',
            color: '#FFF',
            fontSize: '14px',
            fontWeight: '600',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '5px',
            opacity: selectedDocIds.length > 0 ? 1 : 0.6,
            width: '260px',
          }}
          onMouseOver={(e) => {
            if (selectedDocIds.length > 0) {
              e.currentTarget.style.background = GRADIENT.primaryHover;
            }
          }}
          onMouseOut={(e) => {
            if (selectedDocIds.length > 0) {
              e.currentTarget.style.background = GRADIENT.primary;
            }
          }}
          title={selectedDocIds.length > 0 ? `${selectedDocIds.length}개 문서 AI 지식 추가 요청` : '문서를 선택해주세요'}
        >
          <img src={chatIcon} alt="AI 지식 추가 요청" style={{ width: '20px', height: '20px' }} />
          <span>AI 지식 추가 요청</span>
        </button>
      )}

      {/* 문서 활용 방법 가이드 카드 (업로드 중에는 숨김) */}
      {uploadArray.length === 0 && <div style={{
        padding: '12px 16px',
        gap: '10px',
        borderRadius: '10px',
        border: '1px solid var(--color-grayscale-200)',
        background: 'var(--color-grayscale-50)',
        display: 'flex',
        flexDirection: 'column',
      }}>
        <div style={{
          color: 'var(--color-grayscale-300)',

          fontSize: '11px',
          fontStyle: 'normal',
          fontWeight: 500,
          lineHeight: '16px',
          
        }}>
          문서를 AI 지식으로 활용하는 방법
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          {GUIDE_STEPS.map(step => (
            <div key={step.num} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
              <span style={{
                borderRadius: '10px',
                background: step.bg,
                color: step.color,
                textAlign: 'center' as const,

                fontSize: '10px',
                fontStyle: 'normal',
                fontWeight: 700,
                lineHeight: '15px',
                minWidth: '18px',
                height: '18px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}>{step.num}</span>
              <div>
                <div style={{
                  color: 'var(--color-grayscale-500)',

                  fontSize: '13px',
                  fontStyle: 'normal',
                  fontWeight: 600,
                  lineHeight: '20px',
                  letterSpacing: '-0.26px',

                }}>{step.title}</div>
                <div style={{
                  color: 'var(--color-grayscale-400)',

                  fontSize: '11px',
                  fontStyle: 'normal',
                  fontWeight: 400,
                  lineHeight: '16px',

                }}>{step.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </div>}
    </div>
  );

  // 테이블 헤더 공통 스타일
  const headerCellStyle = {
    backgroundColor: 'var(--color-grayscale-150)',
    padding: '10px 20px',
    fontSize: '13px',
    fontWeight: '500',
    color: 'var(--color-grayscale-900)',
    textAlign: 'center' as const,
    whiteSpace: 'nowrap' as const,
  };

  // 테이블 렌더링
  const renderTable = (): JSX.Element => (
    <div style={{ overflowX: 'hidden' }}>
      <table style={{
        width: '100%',
        tableLayout: 'auto',
        borderCollapse: 'separate',
        borderSpacing: 0,
        backgroundColor: 'transparent',
      }}>
        <thead>
          <tr style={{ height: '36px' }}>
            <th style={{
              ...headerCellStyle,
              width: '1%',
              whiteSpace: 'nowrap',
              borderTopLeftRadius: '10px',
            }}>
              <Checkbox
                checked={currentDocuments.length > 0 && currentDocuments.every(doc => selectedDocIds.includes(doc.id))}
                onChange={(e) => {
                  if (e.target.checked) {
                    currentDocuments.forEach(doc => {
                      if (!selectedDocIds.includes(doc.id)) {
                        onToggleDocSelection(doc.id);
                      }
                    });
                  } else {
                    currentDocuments.forEach(doc => {
                      if (selectedDocIds.includes(doc.id)) {
                        onToggleDocSelection(doc.id);
                      }
                    });
                  }
                }}
                title="전체 선택"
              />
            </th>
            <th style={{
              ...headerCellStyle,
              padding: '10px 12px',
              textAlign: 'left',
            }}>
              파일 이름
            </th>
            <th style={{
              ...headerCellStyle,
              width: '1%',
              whiteSpace: 'nowrap',
            }}>
              부서
            </th>
            <th style={{
              ...headerCellStyle,
              width: '1%',
              whiteSpace: 'nowrap',
            }}>
              업로드일
            </th>
            <th style={{
              ...headerCellStyle,
              width: '1%',
              whiteSpace: 'nowrap',
            }}>
              상태
            </th>
            <th style={{
              ...headerCellStyle,
              width: '1%',
              whiteSpace: 'nowrap',
            }}>
              AI 지식 활용
            </th>
            <th style={{
              ...headerCellStyle,
              width: '1%',
              whiteSpace: 'nowrap',
              ...(!isDownload ? { borderTopRightRadius: '10px' } : {}),
            }}>
              북마크
            </th>
            {isDownload && (
              <th style={{
                ...headerCellStyle,
                width: '1%',
                whiteSpace: 'nowrap',
                borderTopRightRadius: '10px'
              }}>
                더보기
              </th>
            )}
          </tr>
        </thead>
        <tbody>
          {currentDocuments.map(renderDocumentRow)}
        </tbody>
      </table>
    </div>
  );

  const emptyMessages: Record<DocumentTab, string> = {
    my: '내 문서가 없습니다.',
    dept: '부서 문서가 없습니다.',
    public: '공통 문서가 없습니다.',
    favorite: '북마크 문서가 없습니다.',
  };
  const emptyMessage = emptyMessages[activeTab];

  const isEmpty = currentDocuments.length === 0 && uploadArray.length === 0;

  const renderBody = (): JSX.Element => {
    if (isLoadingMyDocuments) {
      return <TableSkeleton />;
    }
    if (isEmpty) {
      return (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-grayscale-500)' }}>
          {emptyMessage}
        </div>
      );
    }
    return (
      <div style={{ minHeight: '536px' }}>
        {renderTable()}
      </div>
    );
  };

  return (
    <div data-floating-parent style={{ display: 'flex', flexDirection: 'column', height: isLoadingMyDocuments || isEmpty ? '100%' : undefined, position: 'relative' }}>
      {ToastStack}
      {renderHiddenFileInput()}
      {renderHeader()}
      {renderFloatingUploadButton()}
      <div style={{ flex: isLoadingMyDocuments || isEmpty ? 1 : undefined, padding: isLoadingMyDocuments || isEmpty ? '12px 40px 19px 40px' : '12px 40px 0 40px', display: 'flex', gap: '25px' }}>
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
          {renderBody()}
        </div>
        {uploadPanel.isOpen && (
          <div style={{ display: 'flex', flexDirection: 'column', paddingTop: '0' }}>
            {renderDropZone()}
          </div>
        )}
      </div>
      <div style={{ flexShrink: 0, padding: '0 40px 19px 40px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {!isLoadingMyDocuments && !isEmpty && (
          isEmbedding && selectedDocIds.length > 0 ? (
            <SelectionActionBar
              selectedCount={selectedDocIds.length}
              actions={[{ label: 'AI 지식 추가 요청', onClick: onRequestEmbedding }]}
              onClear={() => selectedDocIds.forEach(id => onToggleDocSelection(id))}
            />
          ) : totalItems > 0 ? (
            <Pagination
              currentPage={currentPage}
              totalItems={totalItems}
              itemsPerPage={itemsPerPage}
              onPageChange={onPageChange}
            />
          ) : null
        )}
      </div>
      {errorReportBoardTypeIds && (
        <BoardModal
          isOpen={errorReportOpen}
          onClose={() => setErrorReportOpen(false)}
          boardTypeIds={errorReportBoardTypeIds}
          initialViewMode="write"
        />
      )}
      <TagAssignModal
        isOpen={tagAssignTarget !== null}
        onClose={() => setTagAssignTarget(null)}
        documentId={tagAssignTarget?.id ?? null}
        documentName={
          tagAssignTarget?.latestContent?.originalFilename ?? tagAssignTarget?.title ?? ''
        }
        availableTags={availableTags}
        initialSelectedTagIds={tagAssignTarget?.myTags?.map((t) => t.id) ?? []}
        onAssigned={() => {
          showSuccess({ title: '태그 적용 완료', message: '태그가 적용되었습니다.' });
          onAfterTagsChanged?.();
        }}
        onError={(title, message) => showError({ title, message })}
      />
    </div>
  );
}

export default MyDocumentsList;
