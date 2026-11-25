// created by ARES team [2026-02-23]
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../features/auth/AuthContext';
import { useChatRooms } from '../../features/chat/ChatRoomsContext';
import ChatRoomList from '../../features/chat/ChatRoomList';
import NewChatButton from '../common/NewChatButton';
import NotificationButton from '../common/NotificationButton';
import Toast from '../common/Toast';
import { useAlarms } from '../../hooks/useAlarms';
import { usePersistedToggle } from '../../hooks/usePersistedToggle';
import SidebarHeaderLogo from './SidebarHeaderLogo';
import SidebarSearchInput from './SidebarSearchInput';
import DocumentsAccordion from './DocumentsAccordion';
import SidebarFavoritePinButton from './SidebarFavoritePinButton';


interface AppSidebarProps {
  activeRoomId?: string;
  onRoomSelect?: (roomId: string) => void;
  onNewChat?: () => Promise<void>;
}

interface AppSidebarOutput {
  headerActions: (isCollapsed: boolean) => React.ReactNode;
  headerTrailingActions: (isCollapsed: boolean) => React.ReactNode;
  sidebarActions: (isCollapsed: boolean, expandSidebar?: () => void) => React.ReactNode;
  sidebarContent: (isCollapsed: boolean) => React.ReactNode;
}

export function useAppSidebar({
  activeRoomId,
  onRoomSelect,
  onNewChat,
}: AppSidebarProps): AppSidebarOutput {
  const navigate = useNavigate();
  const location = useLocation();
  const { logout, user, isAdmin } = useAuth();
  const {
    filteredRooms,
    isLoading: isChatRoomsLoading,
    searchQuery,
    setSearchQuery,
    toggleFavorite,
    renameRoom,
    deleteRoom,
    errorToasts,
    clearErrorToast,
  } = useChatRooms();

  const {
    alarmItems,
    notificationCount,
    alarmError,
    clearAlarmError,
    handleNotificationClick,
    handleReadAllAlarms,
    handleReadAlarm,
    handleDeleteAlarm,
  } = useAlarms({ navigate });

  const isDocumentsPage = location.pathname.startsWith('/documents');
  const isDocumentsListPage = location.pathname === '/documents' || (location.pathname.startsWith('/documents') && !location.pathname.startsWith('/documents/approval'));
  const isDocumentsApprovalPage = location.pathname.startsWith('/documents/approval');

  const docAccordion = usePersistedToggle('doc_accordion_open', isDocumentsPage);

  const handleRoomSelect = (roomId: string): void => {
    if (onRoomSelect) {
      onRoomSelect(roomId);
    } else {
      navigate(`/chat/${roomId}`);
    }
  };

  const handleNewChat = async (): Promise<void> => {
    if (onNewChat) {
      await onNewChat();
    }
  };

  const handleLogout = async (): Promise<void> => {
    await logout();
  };

  const handleAdminClick = (): void => {
    navigate('/admin');
  };

  const notificationProps = {
    notificationCount,
    alarmItems,
    alarmError,
    clearAlarmError,
    onReadAllAlarms: handleReadAllAlarms,
    onReadAlarm: handleReadAlarm,
    onDeleteAlarm: handleDeleteAlarm,
    onNotificationClick: handleNotificationClick,
  };

  const headerActions = (isCollapsed: boolean): React.ReactNode => {
    if (isCollapsed) return null;
    return <SidebarHeaderLogo onClick={() => navigate('/chat')} />;
  };

  const headerTrailingActions = (isCollapsed: boolean): React.ReactNode => {
    if (isCollapsed) return null;
    return <NotificationButton {...notificationProps} />;
  };

  const sidebarActions = (isCollapsed: boolean, expandSidebar?: () => void): React.ReactNode => (
    <>
      {/* 알림 버튼 (접힘 상태 전용) */}
      {isCollapsed && <NotificationButton {...notificationProps} />}

      {/* 새 채팅 버튼 */}
      <NewChatButton
        isCollapsed={isCollapsed}
        onClick={(e) => { e.stopPropagation(); handleNewChat(); }}
      />

      {/* 검색 버튼 / 입력창 */}
      <SidebarSearchInput
        isCollapsed={isCollapsed}
        searchQuery={searchQuery}
        setSearchQuery={setSearchQuery}
        expandSidebar={expandSidebar}
      />

      {/* 문서 보관함 + 즐겨찾기 */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: isCollapsed ? 'center' : 'stretch', gap: isCollapsed ? '8px' : '0px', width: '100%' }}>
        <DocumentsAccordion
          isCollapsed={isCollapsed}
          isOpen={docAccordion.isOpen}
          onToggle={docAccordion.toggle}
          onCollapsedClick={() => navigate('/documents')}
          isDocumentsPage={isDocumentsPage}
          isDocumentsListPage={isDocumentsListPage}
          isDocumentsApprovalPage={isDocumentsApprovalPage}
          // 승인 절차 임시 중단으로 admin만 노출 (복원 시 isAdmin || hasEmbeddingAuth 로 원복)
          showApprovalMenu={Boolean(isAdmin)}
          onListClick={() => navigate('/documents')}
          onApprovalClick={() => navigate('/documents/approval')}
        />

        {/* 즐겨찾기 버튼 (접혔을 때만) */}
        {isCollapsed && (
          <SidebarFavoritePinButton onClick={() => expandSidebar?.()} />
        )}
      </div>
    </>
  );

  const sidebarContent = (isCollapsed: boolean): React.ReactNode => (
    <>
      {errorToasts.length > 0 && <Toast variant="error" items={errorToasts} onClose={clearErrorToast} />}
      <ChatRoomList
        rooms={filteredRooms}
        activeRoomId={activeRoomId}
        onRoomSelect={handleRoomSelect}
        onNewChat={handleNewChat}
        onToggleFavorite={toggleFavorite}
        onLogout={handleLogout}
        onRoomRename={renameRoom}
        onRoomDelete={deleteRoom}
        userName={user?.name}
        userEmail={user?.email}
        isAdmin={isAdmin}
        onAdminClick={handleAdminClick}
        isCollapsed={isCollapsed}
        isLoading={isChatRoomsLoading}
      />
    </>
  );

  return {
    headerActions,
    headerTrailingActions,
    sidebarActions,
    sidebarContent
  };
}