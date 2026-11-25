// created by ARES team [2025-12-15]
import { useState, useEffect } from 'react';
import PageLayout from '../layouts/PageLayout';
import { useAuth } from '../features/auth/AuthContext';
import { useModal } from '../contexts/ModalContext';
import {
  getAdminUsers,
  getAdminAuthorities,
  grantAuthorities,
  revokeAuthorities,
  getAdminDocuments,
  AdminUser,
  Authority,
  AdminDocument,
  PaginationMeta
} from '../services/admin.service';
import AdminUserManagement from '../features/admin/AdminUserManagement';
import AdminAuthority from '../features/admin/AdminAuthority';
import AdminDocumentStorage from '../features/admin/AdminDocumentStorage';
import { useAdminSidebar, AdminMenu } from '../components/AdminSidebar';
import type { SortOrder } from '../components/common/SortToggleButton';

function AdminMainPage() {
  const { user, refreshSession } = useAuth();
  const { showAlert } = useModal();
  const [allUsers, setAllUsers] = useState<AdminUser[]>([]);
  const [authorities, setAuthorities] = useState<Authority[]>([]);
  const [adminDocuments, setAdminDocuments] = useState<AdminDocument[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeMenu, setActiveMenu] = useState<AdminMenu>(() => {
    const stored = localStorage.getItem('adminActiveMenu') as AdminMenu;
    if (stored === '권한 관리' || stored === '사용자 관리' || stored === '문서 관리') {
      return stored;
    }
    return '권한 관리';
  });
  const [processingUserId, setProcessingUserId] = useState<string | null>(null);
  const [adminSortOrder, setAdminSortOrder] = useState<SortOrder>(
    () => (localStorage.getItem('adminDocSortOrder') as SortOrder) || 'desc'
  );
  const [usersMeta, setUsersMeta] = useState<PaginationMeta | null>(null);
  const [adminDocMeta, setAdminDocMeta] = useState<PaginationMeta | null>(null);


  const handleAdminSortToggle = (): void => {
    const newSort: SortOrder = adminSortOrder === 'desc' ? 'asc' : 'desc';
    setAdminSortOrder(newSort);
    localStorage.setItem('adminDocSortOrder', newSort);
  };

  // 페이지네이션 상태
  const [currentPage, setCurrentPage] = useState<number>(1);
  const pageLimit = 9;

  const [userSearchQuery, setUserSearchQuery] = useState('');

  // 사용자 목록 및 권한 목록 조회
  const fetchUsers = async (page = currentPage, search?: string): Promise<void> => {
    try {
      setIsLoading(true);
      setError(null);
      const result = await getAdminUsers(page, pageLimit, search);
      setAllUsers(result.items);
      setUsersMeta(result.meta);
    } catch {
      setError('사용자 목록을 불러오는데 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const fetchData = async () => {
      if (activeMenu === '사용자 관리') {
        await fetchUsers(1);
      }

      if (activeMenu === '권한 관리') {
        try {
          setIsLoading(true);
          setError(null);
          const [usersResult, authoritiesData] = await Promise.all([
            getAdminUsers(1, pageLimit),
            getAdminAuthorities()
          ]);
          setAllUsers(usersResult.items);
          setUsersMeta(usersResult.meta);
          setAuthorities(authoritiesData);
        } catch {
          setError('권한 정보를 불러오는데 실패했습니다.');
        } finally {
          setIsLoading(false);
        }
      }
    };

    setCurrentPage(1);
    fetchData();
    // activeMenu 변경시만 데이터 로드 의도 (fetchData를 deps에 추가하면 매 렌더마다 재실행)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeMenu]);

  const refreshUsers = async (): Promise<void> => {
    try {
      const result = await getAdminUsers(currentPage, pageLimit, userSearchQuery || undefined);
      setAllUsers(result.items);
      setUsersMeta(result.meta);
    } catch {
      // apiClient 인터셉터에서 로깅됨
    }
  };

  // 페이지 변경 핸들러
  const handlePageChange = (page: number): void => {
    setCurrentPage(page);
    if (activeMenu === '사용자 관리' || activeMenu === '권한 관리') {
      fetchUsers(page);
    } else if (activeMenu === '문서 관리') {
      fetchAdminDocuments(page);
    }
  };

  // 탭 변경 시 페이지 초기화
  const handleMenuChange = (menu: AdminMenu): void => {
    setActiveMenu(menu);
    localStorage.setItem('adminActiveMenu', menu);
    setCurrentPage(1);
  };

  // 전체 문서 목록 조회
  useEffect(() => {
    if (activeMenu === '문서 관리') {
      fetchAdminDocuments(1);
    }
    // activeMenu/정렬 변경시만 실행 의도 (fetchAdminDocuments를 deps에 추가하면 매 렌더마다 재실행)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeMenu, adminSortOrder]);

  const fetchAdminDocuments = async (page = currentPage): Promise<void> => {
    try {
      setIsLoading(true);
      setError(null);
      const sort = adminSortOrder === 'asc' ? 'oldest' : 'latest';
      const result = await getAdminDocuments(page, 9, sort);
      setAdminDocuments(result.items);
      setAdminDocMeta(result.meta);
    } catch {
      setError('문서 목록을 불러오는데 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  // 개별 권한 토글
  const handleToggleAuthority = async (userId: string, authorityName: string, shouldGrant: boolean): Promise<void> => {
    try {
      setProcessingUserId(userId);

      if (shouldGrant) {
        await grantAuthorities(userId, [authorityName]);
      } else {
        await revokeAuthorities(userId, [authorityName]);
      }

      await refreshUsers();

      if (userId === user?.userId) {
        await refreshSession();
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : '';
      await showAlert('권한 변경 실패', message || '권한 변경에 실패했습니다.', '확인');
    } finally {
      setProcessingUserId(null);
    }
  };

  const sidebar = useAdminSidebar({ activeMenu, onMenuChange: handleMenuChange });

  // 메뉴별 콘텐츠 렌더링
  const renderContent = (): JSX.Element => {
    switch (activeMenu) {
      case '사용자 관리':
        return (
          <AdminUserManagement
            users={allUsers}
            isLoading={isLoading}
            error={error}
            meta={usersMeta}
            currentPage={currentPage}
            onPageChange={handlePageChange}
            onRefreshUsers={refreshUsers}
            onSearch={(query) => {
              setUserSearchQuery(query);
              setCurrentPage(1);
              fetchUsers(1, query || undefined);
            }}
          />
        );

      case '권한 관리':
        return (
          <AdminAuthority
            users={allUsers}
            authorities={authorities}
            isLoading={isLoading}
            error={error}
            processingUserId={processingUserId}
            onToggleAuthority={handleToggleAuthority}
            meta={usersMeta}
            currentPage={currentPage}
            onPageChange={handlePageChange}
          />
        );

      case '문서 관리':
        return (
          <AdminDocumentStorage
            adminDocuments={adminDocuments}
            isLoading={isLoading}
            error={error}
            sortOrder={adminSortOrder}
            onSortToggle={handleAdminSortToggle}
            onRefreshDocuments={fetchAdminDocuments}
            meta={adminDocMeta}
            currentPage={currentPage}
            onPageChange={handlePageChange}
          />
        );

      default:
        return (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--color-grayscale-500)' }}>
            콘텐츠를 불러올 수 없습니다.
          </div>
        );
    }
  };

  return (
    <PageLayout
      showSidebarToggle={true}
      sidebarHeaderActions={sidebar.headerActions}
      sidebarHeaderTrailingActions={sidebar.headerTrailingActions}
      sidebarContent={sidebar.sidebarContent}
      sidebarActions={sidebar.sidebarActions}
    >
      {renderContent()}
    </PageLayout>
  );
}

export default AdminMainPage;