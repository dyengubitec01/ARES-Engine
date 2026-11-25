// created by ARES team [2026-01-30]
import { useState, useEffect } from 'react';
import { AdminDocumentStorageProps } from './types';
import { softDeleteDocument, hardDeleteDocument } from '../../services/admin.service';
import Pagination from '../../components/common/Pagination';
import { useModal } from '../../contexts/ModalContext';
import { downloadFile } from '../../services/document.service';
import { formatFileSize, formatDate, getFileExtensionUpperCase } from '../../lib/fileUtils';
import StatusBadge from '../../components/common/StatusBadge';
import DocsDownloadIcon from '../../assets/docs/download.svg?react';
import SortToggleButton from '../../components/common/SortToggleButton';
import TableSkeleton from '../../components/common/TableSkeleton';
import DropdownMenu from '../../components/common/DropdownMenu';
import { adminHeaderCellStyle, adminTableStyle, adminTitleStyle, adminCellStyle } from '../../styles/tableStyles';
import Checkbox from '../../components/common/Checkbox';

function AdminDocumentStorage({ adminDocuments, isLoading, error, sortOrder, onSortToggle, onRefreshDocuments, meta, currentPage, onPageChange }: AdminDocumentStorageProps) {
  const { showAlert, showConfirm } = useModal();
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [isDeleting, setIsDeleting] = useState(false);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  useEffect(() => {
    const handleDocumentClick = () => setOpenMenuId(null);
    document.addEventListener('click', handleDocumentClick);
    return () => document.removeEventListener('click', handleDocumentClick);
  }, []);

  const currentDocuments = adminDocuments;

  // 상태 배지 렌더링
  const PROCESSING_BADGE = { text: '처리 중', bg: 'var(--status-processing-bg)', color: 'var(--status-processing-text)', border: '1px solid var(--status-processing-border)' };
  const STATUS_CONFIG = {
    uploading: { text: '업로드 중', bg: 'var(--color-grayscale-100)', color: 'var(--color-grayscale-400)', border: '1px solid var(--color-grayscale-150)' },
    uploaded: { text: '업로드 완료', bg: 'var(--status-uploaded-bg)', color: 'var(--status-uploaded-text)', border: '1px solid var(--status-uploaded-border)' },
    pending_approval: { text: '승인 대기', bg: 'var(--status-pending-bg)', color: 'var(--status-pending-text)', border: '1px solid var(--status-pending-border)' },
    queued: PROCESSING_BADGE,
    parsing: PROCESSING_BADGE,
    chunking: PROCESSING_BADGE,
    embedding: PROCESSING_BADGE,
    upserting: PROCESSING_BADGE,
    rejected: { text: '승인 반려', bg: 'var(--status-rejected-bg)', color: 'var(--status-rejected-text)', border: '1px solid var(--status-rejected-border)' },
    completed: { text: '사용 가능', bg: 'var(--status-success-bg)', color: 'var(--status-success-text)', border: '1px solid var(--status-success-border)' },
    failed: { text: '오류', bg: 'var(--status-error-bg)', color: 'var(--status-error-text)', border: '1px solid var(--status-error-border)' },
    default: { text: '업로드 중', bg: 'var(--color-grayscale-100)', color: 'var(--color-grayscale-400)', border: '1px solid var(--color-grayscale-150)' },
  } as const;

  const renderStatusBadge = (status: string | undefined): JSX.Element => {
    const config = STATUS_CONFIG[status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.default;
    return <StatusBadge label={config.text} bg={config.bg} color={config.color} border={config.border} />;
  };

  // 전체 선택 토글
  const handleToggleSelectAll = (): void => {
    const allCurrentSelected = currentDocuments.length > 0 && 
      currentDocuments.every(doc => selectedDocIds.includes(doc.id));
    
    if (allCurrentSelected) {
      const currentDocIds = new Set(currentDocuments.map(doc => doc.id));
      setSelectedDocIds(prevIds => prevIds.filter(id => !currentDocIds.has(id)));
    } else {
      const currentDocIds = currentDocuments.map(doc => doc.id);
      setSelectedDocIds(prevIds => {
        const newIds = new Set([...prevIds, ...currentDocIds]);
        return Array.from(newIds);
      });
    }
  };

  // 개별 선택 토글
  const handleToggleSelect = (documentId: string): void => {
    setSelectedDocIds(prevIds => {
      if (prevIds.includes(documentId)) {
        return prevIds.filter(id => id !== documentId);
      } else {
        return [...prevIds, documentId];
      }
    });
  };

  // 일반 삭제 (Soft Delete)
  const handleSoftDelete = async (): Promise<void> => {
    if (selectedDocIds.length === 0) {
      await showAlert('문서 선택 필요', '삭제할 문서를 선택해주세요.', '확인');
      return;
    }

    showConfirm(
      '문서를 삭제하시겠습니까?',
      `선택한 ${selectedDocIds.length}개의 문서를 삭제하시겠습니까?`,
      async () => {
        try {
          setIsDeleting(true);
          
          // 각 문서에 대해 순차적으로 삭제 요청
          for (const documentId of selectedDocIds) {
            try {
              await softDeleteDocument(documentId);
            } catch {
              // apiClient 인터셉터에서 로깅됨
            }
          }

          // 선택 해제
          setSelectedDocIds([]);

          // 문서 목록 새로고침
          await onRefreshDocuments();

          await showAlert('삭제 완료', '선택한 문서가 삭제되었습니다.', '확인');
        } catch {
          await showAlert('삭제 실패', '문서 삭제 중 오류가 발생했습니다.', '확인');
        } finally {
          setIsDeleting(false);
        }
      },
      '삭제',
      '취소',
      'var(--color-warning-500)'
    );
  };

  // 영구 삭제 (Hard Delete)
  const handleHardDelete = async (): Promise<void> => {
    if (selectedDocIds.length === 0) {
      await showAlert('문서 선택 필요', '삭제할 문서를 선택해주세요.', '확인');
      return;
    }

    showConfirm(
      '⚠️ 영구 삭제 경고',
      `선택한 ${selectedDocIds.length}개의 문서를 영구적으로 삭제하시겠습니까?\n\n이 작업은 되돌릴 수 없으며, 데이터베이스와 저장소에서 완전히 삭제됩니다.`,
      async () => {
        try {
          setIsDeleting(true);
          
          // 각 문서에 대해 순차적으로 삭제 요청
          for (const documentId of selectedDocIds) {
            try {
              await hardDeleteDocument(documentId);
            } catch {
              // apiClient 인터셉터에서 로깅됨
            }
          }

          // 선택 해제
          setSelectedDocIds([]);

          // 문서 목록 새로고침
          await onRefreshDocuments();

          await showAlert('영구 삭제 완료', '선택한 문서가 영구적으로 삭제되었습니다.', '확인');
        } catch {
          await showAlert('삭제 실패', '문서 영구 삭제 중 오류가 발생했습니다.', '확인');
        } finally {
          setIsDeleting(false);
        }
      },
      '영구 삭제',
      '취소',
      'var(--color-error-500)'
    );
  };

  return (
    <div style={{ flex: 1, padding: '0 20px 19px', overflowY: 'auto' }}>
        <div style={{
          padding: '19px 20px 0 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '33px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <h2 style={{ ...adminTitleStyle, margin: 0 }}>
              전체 문서 목록
            </h2>
            <SortToggleButton sortOrder={sortOrder} onToggle={onSortToggle} />
          </div>

          {/* 삭제 버튼들 */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={handleSoftDelete}
              disabled={selectedDocIds.length === 0 || isDeleting}
              style={{
                padding: '6px 12px',
                backgroundColor: selectedDocIds.length > 0 && !isDeleting ? 'var(--color-warning-500)' : 'var(--color-grayscale-200)',
                border: 'none',
                borderRadius: '6px',
                cursor: selectedDocIds.length > 0 && !isDeleting ? 'pointer' : 'not-allowed',
                fontSize: '13px',
                fontWeight: 'bold',
                color: selectedDocIds.length > 0 && !isDeleting ? 'white' : 'var(--color-grayscale-500)',
                transition: 'all 0.2s',
                opacity: selectedDocIds.length > 0 && !isDeleting ? 1 : 0.6
              }}
              onMouseOver={(e) => {
                if (selectedDocIds.length > 0 && !isDeleting) {
                  e.currentTarget.style.backgroundColor = 'var(--color-warning-600)';
                }
              }}
              onMouseOut={(e) => {
                if (selectedDocIds.length > 0 && !isDeleting) {
                  e.currentTarget.style.backgroundColor = 'var(--color-warning-500)';
                }
              }}
              title={selectedDocIds.length > 0 ? `${selectedDocIds.length}개 문서 삭제` : '문서를 선택해주세요'}
            >
              {isDeleting ? '처리 중...' : `삭제${selectedDocIds.length > 0 ? ` (${selectedDocIds.length})` : ''}`}
            </button>
            
            <button
              onClick={handleHardDelete}
              disabled={selectedDocIds.length === 0 || isDeleting}
              style={{
                padding: '6px 12px',
                backgroundColor: selectedDocIds.length > 0 && !isDeleting ? 'var(--color-error-500)' : 'var(--color-grayscale-200)',
                border: 'none',
                borderRadius: '6px',
                cursor: selectedDocIds.length > 0 && !isDeleting ? 'pointer' : 'not-allowed',
                fontSize: '13px',
                fontWeight: 'bold',
                color: selectedDocIds.length > 0 && !isDeleting ? 'white' : 'var(--color-grayscale-500)',
                transition: 'all 0.2s',
                opacity: selectedDocIds.length > 0 && !isDeleting ? 1 : 0.6
              }}
              onMouseOver={(e) => {
                if (selectedDocIds.length > 0 && !isDeleting) {
                  e.currentTarget.style.backgroundColor = 'var(--color-error-400)';
                }
              }}
              onMouseOut={(e) => {
                if (selectedDocIds.length > 0 && !isDeleting) {
                  e.currentTarget.style.backgroundColor = 'var(--color-error-500)';
                }
              }}
              title={selectedDocIds.length > 0 ? `${selectedDocIds.length}개 문서 영구 삭제` : '문서를 선택해주세요'}
            >
              {isDeleting ? '처리 중...' : `영구 삭제${selectedDocIds.length > 0 ? ` (${selectedDocIds.length})` : ''}`}
            </button>
          </div>
        </div>

        {isLoading ? (
          <TableSkeleton />
        ) : error ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-error-500)' }}>
            {error}
          </div>
        ) : adminDocuments.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-grayscale-500)' }}>
            등록된 문서가 없습니다.
          </div>
        ) : (
          <div style={{ overflowX: 'auto', padding: '0 20px' }}>
            <table style={{ ...adminTableStyle, tableLayout: 'auto', minWidth: undefined }}>
              <thead>
                <tr style={{ height: '36px' }}>
                  <th style={{ ...adminHeaderCellStyle, width: '1%', whiteSpace: 'nowrap', borderTopLeftRadius: '10px' }}>
                    <Checkbox
                      checked={currentDocuments.length > 0 && currentDocuments.every(doc => selectedDocIds.includes(doc.id))}
                      onChange={handleToggleSelectAll}
                      title={currentDocuments.length > 0 && currentDocuments.every(doc => selectedDocIds.includes(doc.id)) ? '전체 선택 해제' : '전체 선택'}
                      size={18}
                    />
                  </th>
                  <th style={{ ...adminHeaderCellStyle, textAlign: 'left' }}>파일명</th>
                  <th style={{ ...adminHeaderCellStyle, width: '1%', whiteSpace: 'nowrap' }}>업로드 사용자</th>
                  <th style={{ ...adminHeaderCellStyle, width: '1%', whiteSpace: 'nowrap' }}>상태</th>
                  <th style={{ ...adminHeaderCellStyle, width: '1%', whiteSpace: 'nowrap' }}>마지막 수정일</th>
                  <th style={{ ...adminHeaderCellStyle, width: '1%', whiteSpace: 'nowrap', borderTopRightRadius: '10px' }}>더보기</th>
                </tr>
              </thead>
              <tbody>
                {currentDocuments.map((doc) => {
                  // 파일명: originalFilename 우선, 없으면 title
                  const fileName = doc.latestContent?.originalFilename || doc.title || '-';
                  
                  // 업로드 사용자
                  const uploader = doc.createdBy 
                    ? `${doc.createdBy.name} (${doc.createdBy.email})`
                    : '-';
                  
                  // 상태
                  const status = doc.latestContent?.status;
                  
                  // 파일 크기
                  const fileSize = doc.latestContent?.fileSize;
                  
                  // 마지막 수정일
                  const lastModified = doc.latestContent?.createdAt || doc.createdAt;

                  const isSelected = selectedDocIds.includes(doc.id);

                  return (
                    <tr 
                      key={doc.id}
                      style={{
                        backgroundColor: isSelected ? 'var(--color-primary-600-100)' : 'transparent',
                        transition: 'background-color 0.2s'
                      }}
                    >
                      <td style={{ ...adminCellStyle, width: '1%', whiteSpace: 'nowrap', textAlign: 'center' }}>
                        <Checkbox
                          checked={isSelected}
                          onChange={() => handleToggleSelect(doc.id)}
                          title={isSelected ? '선택 해제' : '선택'}
                          size={18}
                        />
                      </td>
                      <td style={{ ...adminCellStyle, textAlign: 'left', overflow: 'hidden', maxWidth: 0 }}>
                        <div style={{ fontSize: '14px', fontWeight: '500', color: 'var(--color-grayscale-900)', marginBottom: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {fileName}
                        </div>
                        <div style={{ color: 'var(--color-grayscale-400, #8E8E8E)', fontSize: '11px', fontStyle: 'normal', fontWeight: 500, lineHeight: '16px' }}>
                          {formatFileSize(fileSize)}
                          {getFileExtensionUpperCase(fileName) && <> | {getFileExtensionUpperCase(fileName)}</>}
                        </div>
                      </td>
                      <td style={{ ...adminCellStyle, color: 'var(--color-grayscale-500, #757578)', fontSize: '12px', fontWeight: '400', lineHeight: '16px', letterSpacing: '-0.24px', whiteSpace: 'nowrap', textAlign: 'center' }}>
                        {uploader}
                      </td>
                      <td style={{ ...adminCellStyle, whiteSpace: 'nowrap', textAlign: 'center' }}>
                        {renderStatusBadge(status)}
                      </td>
                      <td style={{ ...adminCellStyle, color: 'var(--color-grayscale-500, #757578)', fontSize: '12px', fontWeight: '400', lineHeight: '16px', letterSpacing: '-0.24px', whiteSpace: 'nowrap', textAlign: 'center' }}>
                        {formatDate(lastModified)}
                      </td>
                      <td style={{ ...adminCellStyle, textAlign: 'center', whiteSpace: 'nowrap', position: 'relative' }}>
                        <DropdownMenu
                          isOpen={openMenuId === doc.id}
                          onToggle={() => setOpenMenuId(openMenuId === doc.id ? null : doc.id)}
                          onClose={() => setOpenMenuId(null)}
                          items={[{
                            label: '다운로드',
                            icon: DocsDownloadIcon,
                            onClick: async () => {
                              if (!doc.latestContent) return;
                              try {
                                await downloadFile(doc.latestContent.id, doc.latestContent.originalFilename);
                              } catch {
                                await showAlert('다운로드 실패', '파일 다운로드에 실패했습니다. 잠시 후 다시 시도해주세요.', '확인');
                              }
                            }
                          }]}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && !error && meta && meta.total > 0 && (
          <Pagination
            currentPage={currentPage}
            totalItems={meta.total}
            itemsPerPage={meta.limit}
            onPageChange={onPageChange}
          />
        )}
    </div>
  );
}

export default AdminDocumentStorage;
