// created by ARES team [2025-12-15]
import { useState, useEffect, useRef, ChangeEvent, useMemo, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAppSidebar } from '../components/AppSidebar';
import { useModal } from '../contexts/ModalContext';
import PageLayout from '../layouts/PageLayout';
import { useDocumentUpload } from '../features/documents/useDocumentUpload';
import { DocumentFile, FILE_VALIDATION, GetDocumentsResponse, DocumentTab } from '../features/documents/types';
import type { SortOrder } from '../components/common/SortToggleButton';
import { useKnowledgeToggle } from '../features/documents/useKnowledgeToggle';
import apiClient from '../lib/apiClient';
import MyDocumentsList from '../features/documents/MyDocumentsList';
import { getDocumentTags, type DocumentTag } from '../services/tag.service';
import { createCustomError, getUserFriendlyMessage } from '../lib/customError';
import { DOCUMENT_CODES } from '../constants/customCodes';
import { useAuth } from '../features/auth/AuthContext';
import CustomModal from '../components/common/CustomModal';
import OnboardingGuideModal from '../components/common/OnboardingGuideModal';
import requestIcon from '../assets/docs/request.svg';
import { formatFileSize, getFileExtensionUpperCase } from '../lib/fileUtils';
import Toast from '../components/common/Toast';
import type { ToastItem } from '../components/common/Toast';
import { GRADIENT } from '../styles/buttonStyles';

const VALID_TABS: DocumentTab[] = ['my', 'dept', 'public', 'favorite'];

function MyDocumentsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, isEmbedding, isUploader, isAdmin } = useAuth();
  const canRequestEmbedding = isUploader || isAdmin || isEmbedding;
  const { showAlert } = useModal();

  const tabParam = searchParams.get('tab');
  const activeTab: DocumentTab = VALID_TABS.includes(tabParam as DocumentTab)
    ? (tabParam as DocumentTab)
    : 'dept';

  const sortParam = searchParams.get('sort');
  const sortOrder: SortOrder = sortParam === 'asc' ? 'asc' : 'desc';

  const [searchInput, setSearchInput] = useState<string>('');
  const trimmedKeyword = searchInput.trim();

  const [selectedDeptIds, setSelectedDeptIds] = useState<string[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([]);
  const [availableTags, setAvailableTags] = useState<DocumentTag[]>([]);

  const deptOptions = useMemo(() => {
    if (!user) return [];
    const lastSegment = (path: string) => path.split('/').pop() ?? path;
    const opts: { id: string; label: string }[] = [];
    if (user.authDeptId) {
      opts.push({ id: user.authDeptId, label: user.department ? lastSegment(user.department) : '내 부서' });
    }
    (user.deptPermissions ?? []).forEach((dp) => {
      opts.push({ id: dp.id, label: lastSegment(dp.name) });
    });
    return opts;
  }, [user]);

  const tagOptions = useMemo(
    () => availableTags.map((t) => ({ id: t.id, label: t.name })),
    [availableTags]
  );

  const refreshTags = useCallback(async () => {
    try {
      const tags = await getDocumentTags();
      setAvailableTags(tags);
    } catch {
      // 토스트는 상위에서 처리
    }
  }, []);

  useEffect(() => {
    refreshTags();
  }, [refreshTags]);

  const [myDocuments, setMyDocuments] = useState<DocumentFile[]>([]);
  const [isLoadingMyDocuments, setIsLoadingMyDocuments] = useState(false);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalItems, setTotalItems] = useState<number>(0);
  const itemsPerPage = 8;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { uploads, uploadFile, removeUpload } = useDocumentUpload();

  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);
  const [embeddingDocIds] = useState<Set<string>>(new Set());
  const [embeddingProgress] = useState<Map<string, number>>(new Map());
  const [showEmbeddingModal, setShowEmbeddingModal] = useState(false);
  const [errorToasts, setErrorToasts] = useState<ToastItem[]>([]);
  const [showWarningToast, setShowWarningToast] = useState(false);
  const [warningToastMessage, setWarningToastMessage] = useState('');
  const [dashboardKey, setDashboardKey] = useState(0);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const { toggleState, toggle: handleKnowledgeToggle, initFromDocuments } = useKnowledgeToggle(
    () => setDashboardKey(prev => prev + 1)
  );

  // 중복 문서 업로드 감지
  useEffect(() => {
    const failedUploads = Array.from(uploads.values()).filter(
      (u) => u.status === 'failed' && u.errorCode === DOCUMENT_CODES.DOC_DUPLICATE_FILE
    );
    if (failedUploads.length > 0) {
      setWarningToastMessage('중복 문서입니다. 다른 문서를 올려주세요.');
      setShowWarningToast(true);
      failedUploads.forEach((u) => removeUpload(u.fileName));
    }
  }, [uploads, removeUpload]);

  // AppSidebar 설정
  const handleNewChat = async (): Promise<void> => {
    navigate('/chat');
  };

  const sidebar = useAppSidebar({
    activeRoomId: undefined,
    onNewChat: handleNewChat,
  });

  // 문서 목록 조회 (탭에 따라 쿼리 파라미터 변경)
  const fetchMyDocuments = async (tab: DocumentTab = activeTab, page: number = currentPage): Promise<void> => {
    try {
      setIsLoadingMyDocuments(true);

      const params = new URLSearchParams();
      params.append('page', String(page));
      params.append('limit', String(itemsPerPage));
      params.append('sort', sortOrder === 'asc' ? 'oldest' : 'latest');

      if (trimmedKeyword) {
        params.append('keyword', trimmedKeyword);
      }

      switch (tab) {
        case 'my':
          // 본인이 업로드한 문서만
          params.append('view', 'mine');
          break;
        case 'dept':
          // 부서 문서: 필터 선택 시 해당 부서만(공개/본인 자동포함 없음),
          // 미선택 시 접근 가능한 모든 부서(본인 부서 + 권한 부서 + 공개 부서)
          if (selectedDeptIds.length > 0) {
            params.append('view', 'dept');
            selectedDeptIds.forEach((id) => params.append('deptIds', id));
          } else {
            params.append('view', 'all');
          }
          break;
        case 'public':
          // 전사 공개 부서 문서만
          params.append('view', 'public');
          break;
        case 'favorite':
          // 접근 가능한 모든 문서 중 즐겨찾기한 것만
          params.append('view', 'all');
          params.append('favorite', 'true');
          break;
      }

      selectedTagIds.forEach((id) => params.append('tagIds', id));

      const response = await apiClient.get<GetDocumentsResponse>('/documents', { params });
      const resData = response.data?.data;

      if (resData && Array.isArray(resData.items)) {
        setMyDocuments(resData.items);
        setTotalItems(resData.meta?.total ?? resData.items.length);
        initFromDocuments(resData.items);
      } else {
        console.error('[문서 목록] 실패: 응답 데이터가 올바르지 않음');
        setMyDocuments([]);
        setTotalItems(0);
      }
    } catch {
      setMyDocuments([]);
      setTotalItems(0);
    } finally {
      setIsLoadingMyDocuments(false);
    }
  };

  // activeTab/sortOrder/검색어/필터 변경 시 (마운트 포함) 문서 목록 조회
  useEffect(() => {
    setCurrentPage(1);
    setSelectedDocIds([]);
    fetchMyDocuments(activeTab, 1);
    // 필터 변경시만 재조회 의도 (fetchMyDocuments를 deps에 추가하면 매 렌더마다 재실행)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, sortOrder, trimmedKeyword, selectedDeptIds, selectedTagIds]);

  // 탭 변경 시 부서 필터 초기화 (부서 문서 탭에서만 의미 있음)
  useEffect(() => {
    if (activeTab !== 'dept' && selectedDeptIds.length > 0) {
      setSelectedDeptIds([]);
    }
    // 탭 변경시만 초기화 의도 (selectedDeptIds.length가 effect 트리거할 필요 없음)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  // 탭 변경 시 URL 쿼리 파라미터 갱신
  const handleTabChange = (tab: DocumentTab): void => {
    const newParams: Record<string, string> = {};
    if (tab !== 'dept') newParams.tab = tab;
    if (sortOrder !== 'desc') newParams.sort = sortOrder;
    setSearchParams(newParams);
  };

  // 정렬 토글 핸들러
  const handleSortToggle = (): void => {
    const newSort: SortOrder = sortOrder === 'desc' ? 'asc' : 'desc';
    const newParams: Record<string, string> = {};
    if (activeTab !== 'dept') newParams.tab = activeTab;
    if (newSort !== 'desc') newParams.sort = newSort;
    setSearchParams(newParams);
  };

  // 업로드 완료 시 자동으로 문서 목록 갱신 및 업로드 항목 제거
  useEffect(() => {
    const uploadArray = Array.from(uploads.values());
    const completedUploads = uploadArray.filter(upload => upload.status === 'uploaded');
    
    if (completedUploads.length > 0) {
      fetchMyDocuments();

      completedUploads.forEach(upload => {
        setTimeout(() => {
          removeUpload(upload.fileName);
        }, 1000);
      });
    }
    // uploads 변경시만 실행 의도 (함수들을 deps에 추가하면 매 렌더마다 재실행)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploads]);

  // 문서 즐겨찾기 토글
  const handleToggleFavorite = async (documentId: string, isFavorite: boolean): Promise<void> => {
    setMyDocuments(prevDocs => 
      prevDocs.map(doc => 
        doc.id === documentId 
          ? { ...doc, isFavorite: !isFavorite }
          : doc
      )
    );

    try {
      if (isFavorite) {
        const response = await apiClient.delete(`/documents/${documentId}/favorite`);
        if (response.status === 200) {
          await fetchMyDocuments();
        }
      } else {
        const response = await apiClient.post(`/documents/${documentId}/favorite`);
        if (response.status === 200 || response.status === 201) {
          await fetchMyDocuments();
        }
      }
    } catch {
      setMyDocuments(prevDocs =>
        prevDocs.map(doc =>
          doc.id === documentId
            ? { ...doc, isFavorite: isFavorite }
            : doc
        )
      );

      setErrorToasts(prev => [...prev, { id: Date.now().toString(), title: '북마크 실패', message: getUserFriendlyMessage(createCustomError(DOCUMENT_CODES.DOC_FAVORITE_TOGGLE_FAILED)) }]);
    }
  };

  // 파일 업로드 핸들러
  const handleFileUpload = async (files: FileList | null): Promise<void> => {
    if (!files) return;

    const fileArray = Array.from(files);
    const invalidFiles: string[] = [];
    const validFiles: File[] = [];

    fileArray.forEach(file => {
      if (file.size > FILE_VALIDATION.MAX_SIZE) {
        invalidFiles.push(`${file.name} (크기 초과: ${(file.size / (1024 * 1024)).toFixed(2)}MB)`);
        return;
      }

      const isValidType = (FILE_VALIDATION.ALLOWED_TYPES as readonly string[]).includes(file.type);
      const isValidExtension = (FILE_VALIDATION.ALLOWED_EXTENSIONS as readonly string[]).some(ext =>
        file.name.toLowerCase().endsWith(ext)
      );

      if (isValidType || isValidExtension) {
        validFiles.push(file);
      } else {
        invalidFiles.push(`${file.name} (지원하지 않는 형식)`);
      }
    });

    if (invalidFiles.length > 0) {
      await showAlert(
        '파일 업로드 제한',
        `다음 파일은 업로드할 수 없습니다:\n\n${invalidFiles.join('\n')}\n\n` +
        `제한사항:\n` +
        `- 최대 파일 크기: ${FILE_VALIDATION.MAX_SIZE / (1024 * 1024)}MB\n` +
        `- 지원 형식: PDF, Word, PowerPoint, Excel, HWP, TXT`,
        '확인'
      );
    }

    if (validFiles.length === 0) {
      return;
    }

    validFiles.forEach(file => {
      uploadFile(file).catch(() => {
        // 내부에서 이미 에러 처리됨
      });
    });
  };

  // 파일 업로드 핸들러
  const handleFileSelect = (e: ChangeEvent<HTMLInputElement>): void => {
    handleFileUpload(e.target.files);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleUploadClick = (): void => {
    fileInputRef.current?.click();
  };

  // 문서 선택 토글 핸들러
  const handleToggleDocSelection = (documentId: string): void => {
    setSelectedDocIds(prevIds => {
      if (prevIds.includes(documentId)) {
        return prevIds.filter(id => id !== documentId);
      } else {
        return [...prevIds, documentId];
      }
    });
  };

  // 임베딩 요청 핸들러
  const handleRequestEmbedding = async (): Promise<void> => {
    setShowEmbeddingModal(true);
  };

  const handleConfirmEmbedding = async (): Promise<void> => {
    setShowEmbeddingModal(false);
    try {
      // 선택된 문서를 상태별로 분류
      const selectedDocs = selectedDocIds
        .map(docId => myDocuments.find(doc => doc.id === docId))
        .filter((doc): doc is DocumentFile => !!doc);

      const reEmbedVersionIds = selectedDocs
        .filter(doc => doc.latestContent?.status === 'failed' || doc.latestContent?.status === 'completed')
        .map(doc => doc.latestContent?.id)
        .filter((id): id is string => !!id);

      const embedVersionIds = selectedDocs
        .filter(doc => doc.latestContent?.status !== 'failed' && doc.latestContent?.status !== 'completed')
        .map(doc => doc.latestContent?.id)
        .filter((id): id is string => !!id);

      if (reEmbedVersionIds.length === 0 && embedVersionIds.length === 0) {
        setErrorToasts(prev => [...prev, { id: Date.now().toString(), title: 'AI 지식 추가 요청 실패', message: '문서 버전 정보를 찾을 수 없습니다.' }]);
        return;
      }

      const allResults: { versionId: string; documentId: string; status: string }[] = [];

      // failed/completed 상태: 재임베딩 요청
      if (reEmbedVersionIds.length > 0) {
        const reEmbedResponse = await apiClient.post('/documents/re-embed-requests/batch', { versionIds: reEmbedVersionIds });
        if (reEmbedResponse.data?.success) {
          allResults.push(...(reEmbedResponse.data.data?.results || []));
        }
      }

      // 그 외 상태: 기존 임베딩 요청
      if (embedVersionIds.length > 0) {
        const embedResponse = await apiClient.post('/documents/embed-requests/batch', { versionIds: embedVersionIds });
        if (embedResponse.data?.success) {
          allResults.push(...(embedResponse.data.data?.results || []));
        }
      }

      // 각 문서 상태를 응답 기반으로 로컬 업데이트
      allResults.forEach(result => {
        setMyDocuments(prevDocs =>
          prevDocs.map(doc =>
            doc.id === result.documentId && doc.latestContent
              ? {
                  ...doc,
                  latestContent: {
                    ...doc.latestContent,
                    status: result.status as DocumentFile['latestContent']['status']
                  }
                }
              : doc
          )
        );
      });

      setSelectedDocIds([]);
      setDashboardKey(prev => prev + 1);
    } catch {
      setErrorToasts(prev => [...prev, { id: Date.now().toString(), message: '문제가 발생했습니다.' }]);
    }
  };

  const handlePageChange = (page: number): void => {
    setCurrentPage(page);
    fetchMyDocuments(activeTab, page);
  };

  return (
    <PageLayout
      showSidebarToggle={true}
      sidebarContent={sidebar.sidebarContent}
      sidebarHeaderActions={sidebar.headerActions}
      sidebarHeaderTrailingActions={sidebar.headerTrailingActions}
      sidebarActions={sidebar.sidebarActions}
    >
      {/* 에러 토스트 */}
      {errorToasts.length > 0 && <Toast variant="error" items={errorToasts} onClose={(id: string) => setErrorToasts(prev => prev.filter(t => t.id !== id))} />}
      {/* 중복 문서 경고 토스트 */}
      {showWarningToast && <Toast variant="warning" items={[{ id: 'warning', title: '업로드 오류', message: warningToastMessage }]} onClose={() => setShowWarningToast(false)} />}
      <MyDocumentsList
        myDocuments={myDocuments}
        isLoadingMyDocuments={isLoadingMyDocuments}
        activeTab={activeTab}
        sortOrder={sortOrder}
        onSortToggle={handleSortToggle}
        uploads={uploads}
        fileInputRef={fileInputRef}
        selectedDocIds={selectedDocIds}
        embeddingDocIds={embeddingDocIds}
        embeddingProgress={embeddingProgress}
        isEmbedding={canRequestEmbedding}
        currentPage={currentPage}
        totalItems={totalItems}
        onPageChange={handlePageChange}
        onToggleFavorite={handleToggleFavorite}
        onFileSelect={handleFileSelect}
        onUploadClick={handleUploadClick}
        onRemoveUpload={removeUpload}
        onToggleDocSelection={handleToggleDocSelection}
        onRequestEmbedding={handleRequestEmbedding}
        onTabChange={handleTabChange}
        onRefresh={async () => {
          setSelectedDocIds([]);
          await fetchMyDocuments();
        }}
        knowledgeToggleState={toggleState}
        onKnowledgeToggle={handleKnowledgeToggle}
        onFileDrop={handleFileUpload}
        dashboardRefreshKey={dashboardKey}
        onHelpClick={() => setIsHelpOpen(true)}
        onSearchChange={setSearchInput}
        deptOptions={deptOptions}
        selectedDeptIds={selectedDeptIds}
        onDeptIdsChange={setSelectedDeptIds}
        tagOptions={tagOptions}
        selectedTagIds={selectedTagIds}
        onTagIdsChange={setSelectedTagIds}
        onAfterTagCreated={refreshTags}
        availableTags={availableTags}
        onAfterTagsChanged={async () => {
          await refreshTags();
          await fetchMyDocuments();
        }}
      />
      <CustomModal
        isOpen={showEmbeddingModal}
        type="confirm"
        title="AI 지식 추가 요청"
        titleGap="4px"
        message="문서를 지식 베이스에 추가 요청합니다."
        width="450px"
        confirmText="요청"
        cancelText="취소"
        confirmColor={GRADIENT.primarySoft}
        onConfirm={handleConfirmEmbedding}
        onCancel={() => setShowEmbeddingModal(false)}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', width: '100%' }}>
          {/* 설명 영역 */}
          <div style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '12px',
            padding: '16px',
            borderRadius: '8px',
            border: '1px solid var(--color-warning-400)',
            background: 'var(--color-warning-100)',
            boxSizing: 'border-box',
          }}>
            <img src={requestIcon} alt="" style={{ width: '20px', height: '20px', flexShrink: 0 }} />
            {/* 기존 문구 (승인 절차 복구 시 사용)
            <span style={{
              color: 'var(--color-grayscale-900)',
              fontSize: '13px',
              fontWeight: '500',
              lineHeight: '20px',
              letterSpacing: '-0.26px',
            }}>
              AI 지식 추가는 팀장의 승인이 필요합니다.<br />
              승인 완료 후 AI 어시스턴트가 해당 문서 내용을 바탕으로 답변합니다.
            </span>
            */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <span style={{
                color: 'var(--color-grayscale-900)',
                fontSize: '13px',
                fontWeight: '500',
                lineHeight: '20px',
                letterSpacing: '-0.26px',
              }}>
                요청 시 AI 지식 추가가 진행되며,<br />
                완료 후 AI 어시스턴트가 해당 문서 내용을 바탕으로 답변합니다.
              </span>
              <span style={{
                color: 'var(--color-warning-600)',
                fontSize: '12px',
                fontWeight: '500',
                lineHeight: '18px',
                letterSpacing: '-0.24px',
              }}>
                ※ 차후에는 팀장(이상)급 관리자의 요청/승인 절차가 추가될 예정입니다.
              </span>
            </div>
          </div>

          {/* 선택된 파일 목록 */}
          {(() => {
            const selectedDocs = myDocuments.filter(doc => selectedDocIds.includes(doc.id));
            return (
              <div style={{
                borderRadius: '8px',
                border: '1px solid var(--color-grayscale-150)',
                background: 'var(--color-grayscale-50)',
                boxShadow: '0 1px 3px 0 rgba(26, 22, 64, 0.05), 0 1px 2px 0 rgba(26, 22, 64, 0.04)',
                maxHeight: selectedDocs.length > 3 ? `${3 * 56 + 2 * 1}px` : 'none',
                overflowY: selectedDocs.length > 3 ? 'auto' : 'visible',
              }}>
                {selectedDocs.map((doc, index) => (
                  <div key={doc.id}>
                    <div style={{ padding: '8px 16px' }}>
                      <div style={{
                        fontSize: '13px',
                        fontWeight: '500',
                        lineHeight: '20px',
                        letterSpacing: '-0.26px',

                        color: 'var(--color-grayscale-900)',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}>
                        {doc.latestContent?.originalFilename || doc.title}
                      </div>
                      <div style={{
                        fontSize: '11px',
                        fontWeight: '500',
                        lineHeight: '16px',

                        color: 'var(--color-grayscale-400)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}>
                        <span>{formatFileSize(doc.latestContent?.fileSize)} | {getFileExtensionUpperCase(doc.latestContent?.originalFilename || doc.title)}</span>
                        {(doc.latestContent?.status === 'failed' || doc.latestContent?.status === 'completed') && (
                          <span style={{
                            color: 'var(--color-error-500)',
                            fontSize: '11px',
                            fontWeight: '500',
                            lineHeight: '16px',
                          }}>
                            *이 문서의 경우 승인 절차 없이 즉시 추가됩니다.
                          </span>
                        )}
                      </div>
                    </div>
                    {index < selectedDocs.length - 1 && (
                      <div style={{ height: '1px', background: 'var(--color-grayscale-200)', margin: '0 16px' }} />
                    )}
                  </div>
                ))}
              </div>
            );
          })()}
        </div>
      </CustomModal>
      <OnboardingGuideModal
        isOpen={isHelpOpen || undefined}
        onClose={() => setIsHelpOpen(false)}
      />
    </PageLayout>
  );
}

export default MyDocumentsPage;

