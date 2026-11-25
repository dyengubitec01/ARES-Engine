import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import apiClient from '../../lib/apiClient';
import Pagination from '../../components/common/Pagination';
import type { SortOrder } from '../../components/common/SortToggleButton';
import StatusBadge from '../../components/common/StatusBadge';
import CustomModal from '../../components/common/CustomModal';
import approvalIcon from '../../assets/docs/approval.svg';
import { useModal } from '../../contexts/ModalContext';
import { useAuth } from '../auth/AuthContext';
import { softDeleteDocument } from '../../services/admin.service';
import { approveEmbedRequests, rejectEmbedRequests } from '../../services/document.service';
import { formatFileSize, getFileExtensionUpperCase } from '../../lib/fileUtils';
import DocumentPageHeader from './DocumentPageHeader';
import DocumentFileCell from './DocumentFileCell';
import ApprovalTableShell, { type ApprovalTableColumn } from './ApprovalTableShell';
import TableSkeleton from '../../components/common/TableSkeleton';
import SelectionActionBar from '../../components/common/SelectionActionBar';
import { useToasts } from '../../hooks/useToasts';
import { GRADIENT } from '../../styles/buttonStyles';

type ApprovalTab = 'request' | 'approved' | 'rejected';
const VALID_TABS: ApprovalTab[] = ['request', 'approved', 'rejected'];

const TAB_TYPE_MAP: Record<ApprovalTab, string> = {
  request: 'pending',
  approved: 'approved',
  rejected: 'rejected',
};

type ReviewAction = 'approve' | 'reject';

interface ReviewHistoryItem {
  reviewerName: string;
  action: ReviewAction;
  reason: string | null;
  reviewedAt: string;
}

interface EmbedRequestItem {
  versionId: string;
  documentId: string;
  title: string;
  versionNo: number;
  filename: string;
  fileSize: number;
  mimeType: string;
  uploaderName: string;
  uploaderDepartment: string;
  reviewerName: string | null;
  status: string;
  statusReason: string | null;
  requestedAt: string | null;
  createdAt: string;
  reviewHistory: ReviewHistoryItem[];
}

interface EmbedRequestsResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    items: EmbedRequestItem[];
    meta: {
      total: number;
      page: number;
      limit: number;
      totalPages: number;
    };
  };
}

const PROCESSING_BADGE = { text: 'AI 처리 중', bg: 'var(--status-processing-bg)', color: 'var(--status-processing-text)', border: '1px solid var(--status-processing-border)' };
const STATUS_BADGE_CONFIG: Record<string, { text: string; bg: string; color: string; border: string }> = {
  pending_approval: { text: '승인 대기', bg: 'var(--status-pending-bg)', color: 'var(--status-pending-text)', border: '1px solid var(--status-pending-border)' },
  queued: PROCESSING_BADGE,
  parsing: PROCESSING_BADGE,
  chunking: PROCESSING_BADGE,
  embedding: PROCESSING_BADGE,
  upserting: PROCESSING_BADGE,
  completed: { text: '사용 가능', bg: 'var(--status-success-bg)', color: 'var(--status-success-text)', border: '1px solid var(--status-success-border)' },
  rejected: { text: '승인 반려', bg: 'var(--status-rejected-bg)', color: 'var(--status-rejected-text)', border: '1px solid var(--status-rejected-border)' },
  failed: { text: '오류', bg: 'var(--status-error-bg)', color: 'var(--status-error-text)', border: '1px solid var(--status-error-border)' },
};

function DocumentApprovalList() {
  const { showAlert, showConfirm } = useModal();
  const { isAdmin, isSoftDelete } = useAuth();
  const canDelete = isAdmin || isSoftDelete;

  const [searchParams, setSearchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');
  const activeTab: ApprovalTab = VALID_TABS.includes(tabParam as ApprovalTab)
    ? (tabParam as ApprovalTab)
    : 'request';

  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [items, setItems] = useState<EmbedRequestItem[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [approvalTargetIds, setApprovalTargetIds] = useState<string[]>([]);
  const [rejectionTargetIds, setRejectionTargetIds] = useState<string[]>([]);
  const [rejectionReason, setRejectionReason] = useState('');
  const { showError, showSuccess, ToastStack } = useToasts();
  const itemsPerPage = 8;

  const fetchItems = useCallback(async () => {
    try {
      setIsLoading(true);
      const params = new URLSearchParams();
      params.append('type', TAB_TYPE_MAP[activeTab]);
      params.append('page', String(currentPage));
      params.append('limit', String(itemsPerPage));
      params.append('sort', sortOrder === 'asc' ? 'oldest' : 'latest');

      const response = await apiClient.get<EmbedRequestsResponse>('/documents/embed-requests', { params });
      const data = response.data?.data;
      if (data) {
        setItems(data.items);
        setTotalItems(data.meta.total);
      }
    } catch {
      setItems([]);
      setTotalItems(0);
    } finally {
      setIsLoading(false);
    }
  }, [activeTab, currentPage, sortOrder]);

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);


  const handleTabChange = (tab: ApprovalTab): void => {
    setSearchParams(tab === 'request' ? {} : { tab });
    setCurrentPage(1);
    setSelectedIds([]);
  };

  const handleSortToggle = (): void => {
    setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc');
    setCurrentPage(1);
    setSelectedIds([]);
  };

  const handleDelete = (): void => {
    if (selectedIds.length === 0) {
      showAlert('문서 선택 필요', '삭제할 문서를 선택해주세요.', '확인');
      return;
    }
    showConfirm(
      '문서 삭제',
      `선택한 ${selectedIds.length}개 문서를 삭제하시겠습니까?`,
      async () => {
        try {
          for (const documentId of selectedIds) {
            await softDeleteDocument(documentId);
          }
          setSelectedIds([]);
          await fetchItems();
          showSuccess({ title: '삭제 완료', message: '문서가 삭제되었습니다.' });
        } catch {
          showError({ title: '삭제 실패', message: '잠시 후 다시 시도해주세요.' });
        }
      },
      '삭제',
      '취소'
    );
  };

  const handleApprove = (versionIds: string | string[]): void => {
    const ids = Array.isArray(versionIds) ? versionIds : [versionIds];
    setApprovalTargetIds(ids);
  };

  const handleConfirmApprove = async (): Promise<void> => {
    try {
      const response = await approveEmbedRequests(approvalTargetIds);
      const errorResults = response.data.results.filter(r => r.status === 'error');

      if (errorResults.length > 0) {
        showError({ message: '문제가 발생했습니다.' });
              } else {
        const successResults = response.data.results.filter(r => r.status !== 'error');
        const firstItem = items.find(i => i.versionId === successResults[0]?.versionId);
        const firstName = firstItem?.filename || successResults[0]?.versionId || '';
        const toastMessage = successResults.length > 1
          ? `'${firstName}' 외 ${successResults.length - 1}개 파일이 승인 완료되었습니다.`
          : `'${firstName}' 파일이 승인 완료되었습니다.`;

        showSuccess({ title: '승인 완료', message: toastMessage });
      }

      setApprovalTargetIds([]);
      setSelectedIds([]);
      await fetchItems();
    } catch {
      showError({ message: '문제가 발생했습니다.' });
            setApprovalTargetIds([]);
    }
  };

  const handleReject = (versionIds: string | string[]): void => {
    const ids = Array.isArray(versionIds) ? versionIds : [versionIds];
    setRejectionTargetIds(ids);
    setRejectionReason('');
  };

  const handleConfirmReject = async (): Promise<void> => {
    try {
      const items = rejectionTargetIds.map(versionId => ({
        versionId,
        reason: rejectionReason.trim(),
      }));
      const response = await rejectEmbedRequests(items);
      const errorResults = response.data.results.filter(r => r.status === 'error');

      if (errorResults.length > 0) {
        showError({ message: '문제가 발생했습니다.' });
              } else {
        showSuccess({ title: '반려 완료', message: response.message });
      }

      setRejectionTargetIds([]);
      setRejectionReason('');
      setSelectedIds([]);
      await fetchItems();
    } catch {
      showError({ message: '문제가 발생했습니다.' });
            setRejectionTargetIds([]);
      setRejectionReason('');
    }
  };

  const getStatusBadge = (status: string): JSX.Element => {
    const config = STATUS_BADGE_CONFIG[status] || { text: status, bg: '#F2F3F5', color: '#4B4D55', border: '1px solid var(--color-grayscale-150)' };
    return <StatusBadge label={config.text} bg={config.bg} color={config.color} border={config.border} />;
  };

  const formatDate = (dateStr: string | null): string => {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
  };

  const tabs: { key: ApprovalTab; label: string }[] = [
    { key: 'request', label: 'AI 지식 추가 요청' },
    { key: 'approved', label: '승인 내역' },
    { key: 'rejected', label: '반려 내역' },
  ];

  const emptyMessages: Record<ApprovalTab, string> = {
    request: 'AI 지식 추가 요청이 없습니다.',
    approved: '승인 내역이 없습니다.',
    rejected: '반려 내역이 없습니다.',
  };

  const requestColumns: ApprovalTableColumn<EmbedRequestItem>[] = [
    {
      key: 'filename',
      label: '파일 이름',
      headerStyle: { padding: '10px 12px', textAlign: 'left' },
      cellStyle: { textAlign: 'left', overflow: 'hidden', maxWidth: 0 },
      render: (item) => <DocumentFileCell filename={item.filename} fileSize={item.fileSize} />,
    },
    {
      key: 'uploaderName',
      label: '요청자',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { whiteSpace: 'nowrap' },
      render: (item) => item.uploaderName,
    },
    {
      key: 'uploaderDepartment',
      label: '부서',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { textAlign: 'center', whiteSpace: 'nowrap' },
      render: (item) => item.uploaderDepartment ? item.uploaderDepartment.split('/').pop() : '-',
    },
    {
      key: 'status',
      label: '상태',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { textAlign: 'center', whiteSpace: 'nowrap' },
      render: (item) => getStatusBadge(item.status),
    },
    {
      key: 'requestedAt',
      label: '요청일',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { fontWeight: '400', whiteSpace: 'nowrap' },
      render: (item) => formatDate(item.requestedAt),
    },
    {
      key: 'actions',
      label: '문서 승인 설정',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { textAlign: 'center', whiteSpace: 'nowrap' },
      render: (item) => (
        <div style={{ display: 'flex', justifyContent: 'center', gap: '10px' }}>
          <button onClick={() => handleApprove(item.versionId)}
            style={{ width: '63px', height: '32px', borderRadius: '8px', border: '1px solid var(--color-primary-600, #626BF7)', background: 'var(--color-grayscale-50)', color: 'var(--color-primary-600, #626BF7)', fontSize: '13px', fontWeight: '600', lineHeight: '20px', letterSpacing: '-0.26px',  cursor: 'pointer', transition: 'background 0.2s, color 0.2s' }}
            onMouseOver={(e) => { e.currentTarget.style.background = 'var(--color-primary-200)'; e.currentTarget.style.color = 'var(--color-grayscale-50)'; }}
            onMouseOut={(e) => { e.currentTarget.style.background = 'var(--color-grayscale-50)'; e.currentTarget.style.color = 'var(--color-primary-600, #626BF7)'; }}
            onMouseDown={(e) => { e.currentTarget.style.background = 'var(--color-primary-600, #626BF7)'; e.currentTarget.style.color = 'var(--color-grayscale-50)'; }}
            onMouseUp={(e) => { e.currentTarget.style.background = 'var(--color-primary-200)'; e.currentTarget.style.color = 'var(--color-grayscale-50)'; }}>
            승인
          </button>
          <button onClick={() => handleReject(item.versionId)}
            style={{ width: '63px', height: '32px', borderRadius: '8px', border: '1px solid var(--color-grayscale-400)', background: 'var(--color-grayscale-50)', color: 'var(--color-grayscale-400)', fontSize: '13px', fontWeight: '600', lineHeight: '20px', letterSpacing: '-0.26px',  cursor: 'pointer', transition: 'background 0.2s, color 0.2s' }}
            onMouseOver={(e) => { e.currentTarget.style.background = 'var(--color-grayscale-150)'; e.currentTarget.style.color = 'var(--color-grayscale-900)'; }}
            onMouseOut={(e) => { e.currentTarget.style.background = 'var(--color-grayscale-50)'; e.currentTarget.style.color = 'var(--color-grayscale-400)'; }}
            onMouseDown={(e) => { e.currentTarget.style.background = 'var(--color-grayscale-150)'; e.currentTarget.style.color = 'var(--color-grayscale-900)'; }}
            onMouseUp={(e) => { e.currentTarget.style.background = 'var(--color-grayscale-150)'; e.currentTarget.style.color = 'var(--color-grayscale-900)'; }}>
            반려
          </button>
        </div>
      ),
    },
  ];

  const approvedColumns: ApprovalTableColumn<EmbedRequestItem>[] = [
    {
      key: 'filename',
      label: '파일 이름',
      headerStyle: { padding: '10px 12px', textAlign: 'left' },
      cellStyle: { textAlign: 'left', overflow: 'hidden', maxWidth: 0 },
      render: (item) => <DocumentFileCell filename={item.filename} fileSize={item.fileSize} />,
    },
    {
      key: 'uploaderName',
      label: '요청자',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { whiteSpace: 'nowrap' },
      render: (item) => item.uploaderName,
    },
    {
      key: 'uploaderDepartment',
      label: '부서',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { textAlign: 'center', whiteSpace: 'nowrap' },
      render: (item) => item.uploaderDepartment ? item.uploaderDepartment.split('/').pop() : '-',
    },
    {
      key: 'reviewerName',
      label: '승인자',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { whiteSpace: 'nowrap' },
      render: (item) => item.reviewerName || '-',
    },
    {
      key: 'processedAt',
      label: '처리일',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { fontWeight: '400', whiteSpace: 'nowrap' },
      render: (item) => formatDate(item.reviewHistory?.[0]?.reviewedAt ?? null),
    },
  ];

  const rejectedColumns: ApprovalTableColumn<EmbedRequestItem>[] = [
    {
      key: 'filename',
      label: '파일 이름',
      headerStyle: { padding: '10px 12px', textAlign: 'left', width: '30%' },
      cellStyle: { textAlign: 'left', overflow: 'hidden', maxWidth: 0 },
      render: (item) => <DocumentFileCell filename={item.filename} fileSize={item.fileSize} />,
    },
    {
      key: 'uploaderName',
      label: '요청자',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { whiteSpace: 'nowrap' },
      render: (item) => item.uploaderName,
    },
    {
      key: 'uploaderDepartment',
      label: '부서',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { textAlign: 'center', whiteSpace: 'nowrap' },
      render: (item) => item.uploaderDepartment ? item.uploaderDepartment.split('/').pop() : '-',
    },
    {
      key: 'rejecter',
      label: '반려자',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { whiteSpace: 'nowrap' },
      render: (item) => item.reviewHistory?.[0]?.reviewerName || item.reviewerName || '-',
    },
    {
      key: 'reviewedAt',
      label: '처리일',
      headerStyle: { width: '1%', whiteSpace: 'nowrap' },
      cellStyle: { fontWeight: '400', whiteSpace: 'nowrap' },
      render: (item) => formatDate(item.reviewHistory?.[0]?.reviewedAt ?? null),
    },
    {
      key: 'reason',
      label: '반려사유',
      headerStyle: { whiteSpace: 'nowrap', maxWidth: '210px', width: '210px', textAlign: 'center' },
      cellStyle: { textAlign: 'center', overflow: 'hidden' },
      render: (item) => (
        <div style={{
          color: 'var(--color-warning-700)',
          fontSize: '12px',
          fontWeight: '400',
          lineHeight: '16px',
          letterSpacing: '-0.24px',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {item.reviewHistory?.[0]?.reason || '-'}
        </div>
      ),
    },
  ];

  const activeColumns = activeTab === 'request' ? requestColumns
    : activeTab === 'approved' ? approvedColumns
    : rejectedColumns;

  const renderActiveTable = (): JSX.Element => (
    <ApprovalTableShell
      items={items}
      getItemId={(item) => item.versionId}
      selectedIds={selectedIds}
      onToggleAll={(checked) => checked ? setSelectedIds(items.map(i => i.versionId)) : setSelectedIds([])}
      onToggleOne={(id) => setSelectedIds(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])}
      columns={activeColumns}
    />
  );

  const renderHeader = (): JSX.Element => (
    <DocumentPageHeader
      title="문서 승인 관리"
      tabs={tabs}
      activeTab={activeTab}
      onTabChange={handleTabChange}
      sortOrder={sortOrder}
      onSortToggle={handleSortToggle}
      canDelete={canDelete}
      onDelete={handleDelete}
    />
  );

  const approvalTargetItems = items.filter(item => approvalTargetIds.includes(item.versionId));


  const renderApprovalModal = (): JSX.Element => (
    <CustomModal
      isOpen={approvalTargetIds.length > 0}
      type="confirm"
      title="AI 지식 추가를 승인할까요?"
      titleIcon={approvalIcon}
      titleGap="4px"
      message="승인시 AI 지식에 임베딩이 시작됩니다."
      width="450px"
      confirmText="승인"
      cancelText="취소"
      confirmColor={GRADIENT.primarySoft}
      onConfirm={handleConfirmApprove}
      onCancel={() => setApprovalTargetIds([])}
    >
      <div style={{
        borderRadius: '8px',
        border: '1px solid var(--color-grayscale-150, #E8E7F0)',
        background: 'var(--color-grayscale-50, #FFF)',
        boxShadow: '0 1px 3px 0 rgba(26, 22, 64, 0.05), 0 1px 2px 0 rgba(26, 22, 64, 0.04)',
        maxHeight: approvalTargetItems.length > 3 ? `${3 * 56 + 2 * 1}px` : 'none',
        overflowY: approvalTargetItems.length > 3 ? 'auto' : 'visible',
      }}>
        {approvalTargetItems.map((item, index) => (
          <div key={item.versionId}>
            <div style={{ padding: '8px 16px' }}>
              <div style={{

                fontSize: '13px',
                fontWeight: '500',
                lineHeight: '20px',
                letterSpacing: '-0.26px',
                
                color: 'var(--color-grayscale-900, #31343E)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}>
                {item.filename}
              </div>
              <div style={{

                fontSize: '11px',
                fontWeight: '500',
                lineHeight: '16px',
                
                color: 'var(--color-grayscale-400, #8E8E8E)',
              }}>
                {formatFileSize(item.fileSize)}{getFileExtensionUpperCase(item.filename) && ` | ${getFileExtensionUpperCase(item.filename)}`}
              </div>
            </div>
            {index < approvalTargetItems.length - 1 && (
              <div style={{ height: '1px', background: 'var(--color-grayscale-200, #DDD)', margin: '0 16px' }} />
            )}
          </div>
        ))}
      </div>
    </CustomModal>
  );

  const rejectionTargetItems = items.filter(item => rejectionTargetIds.includes(item.versionId));

  const renderRejectionModal = (): JSX.Element => (
    <CustomModal
      isOpen={rejectionTargetIds.length > 0}
      type="confirm"
      title="AI 지식 추가 요청을 반려할까요?"
      titleIcon={approvalIcon}
      titleGap="4px"
      message="반려 사유는 요청자에게 전달됩니다."
      width="450px"
      confirmText="반려 처리"
      cancelText="취소"
      confirmColor={GRADIENT.primarySoft}
      confirmDisabled={rejectionReason.trim().length === 0}
      onConfirm={handleConfirmReject}
      onCancel={() => { setRejectionTargetIds([]); setRejectionReason(''); }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* 파일 정보 */}
        <div style={{
          borderRadius: '8px',
          border: '1px solid var(--color-grayscale-150, #E8E7F0)',
          background: 'var(--color-grayscale-50, #FFF)',
          boxShadow: '0 1px 3px 0 rgba(26, 22, 64, 0.05), 0 1px 2px 0 rgba(26, 22, 64, 0.04)',
          maxHeight: rejectionTargetItems.length > 3 ? `${3 * 56 + 2 * 1}px` : 'none',
          overflowY: rejectionTargetItems.length > 3 ? 'auto' : 'visible',
        }}>
          {rejectionTargetItems.map((item, index) => (
            <div key={item.versionId}>
              <div style={{ padding: '8px 16px' }}>
                <div style={{

                  fontSize: '13px',
                  fontWeight: '500',
                  lineHeight: '20px',
                  letterSpacing: '-0.26px',
                  
                  color: 'var(--color-grayscale-900, #31343E)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }} title={item.filename}>
                  {item.filename}
                </div>
                <div style={{

                  fontSize: '11px',
                  fontWeight: '500',
                  lineHeight: '16px',
                  
                  color: 'var(--color-grayscale-400, #8E8E8E)',
                }}>
                  {formatFileSize(item.fileSize)}{getFileExtensionUpperCase(item.filename) && ` | ${getFileExtensionUpperCase(item.filename)}`}
                </div>
              </div>
              {index < rejectionTargetItems.length - 1 && (
                <div style={{ height: '1px', background: 'var(--color-grayscale-200, #DDD)', margin: '0 16px' }} />
              )}
            </div>
          ))}
        </div>

        {/* 반려 사유 입력 */}
        <div>
          <div style={{

            fontSize: '13px',
            fontWeight: '500',
            lineHeight: '20px',
            letterSpacing: '-0.26px',
            
            color: 'var(--color-grayscale-500, #757578)',
            marginBottom: '8px',
            display: 'flex',
            alignItems: 'center',
            gap: '2px',
          }}>
            반려사유
            <span style={{ color: '#E53E3E' }}>*</span>
          </div>
          <textarea
            value={rejectionReason}
            onChange={(e) => {
              if (e.target.value.length <= 200) setRejectionReason(e.target.value);
            }}
            placeholder="반려 사유를 입력해주세요"
            style={{
              width: '100%',
              height: '100px',
              padding: '12px',
              borderRadius: '8px',
              border: '1px solid var(--color-grayscale-150, #E8E7F0)',
              background: 'var(--color-grayscale-50, #FFF)',
  
              fontSize: '13px',
              fontWeight: '400',
              lineHeight: '20px',
              color: 'var(--color-grayscale-900, #31343E)',
              resize: 'none',
              outline: 'none',
              boxSizing: 'border-box',
            }}
            onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--color-primary-600, #626BF7)'; }}
            onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--color-grayscale-150, #E8E7F0)'; }}
          />
          <div style={{
            textAlign: 'right',

            fontSize: '11px',
            fontWeight: '400',
            lineHeight: '16px',
            color: 'var(--color-grayscale-400, #8E8E8E)',
            marginTop: '4px',
          }}>
            {rejectionReason.length}/200
          </div>
        </div>
      </div>
    </CustomModal>
  );

  const renderBulkActionBar = (): JSX.Element | null => {
    if (selectedIds.length === 0 || activeTab !== 'request') return null;
    return (
      <SelectionActionBar
        selectedCount={selectedIds.length}
        actions={[{ label: '일괄 승인', onClick: () => handleApprove(selectedIds), width: '80px' }]}
        onClear={() => setSelectedIds([])}
      />
    );
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', position: 'relative' }}>
      {ToastStack}
      {renderApprovalModal()}
      {renderRejectionModal()}
      {renderHeader()}
      <div style={{ padding: '12px 40px 0 40px' }}>
        {isLoading ? (
          <TableSkeleton />
        ) : items.length === 0 ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: '536px',
            color: 'var(--color-grayscale-500)',
          }}>
            {emptyMessages[activeTab]}
          </div>
        ) : (
          <div style={{ minHeight: '536px' }}>
            {renderActiveTable()}
          </div>
        )}
      </div>
      <div style={{ flexShrink: 0, padding: '0 40px 19px 40px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {!isLoading && items.length > 0 && (
          selectedIds.length > 0 && activeTab === 'request'
            ? renderBulkActionBar()
            : totalItems > 0 && (
              <Pagination
                currentPage={currentPage}
                totalItems={totalItems}
                itemsPerPage={itemsPerPage}
                onPageChange={setCurrentPage}
              />
            )
        )}
      </div>
    </div>
  );
}

export default DocumentApprovalList;
