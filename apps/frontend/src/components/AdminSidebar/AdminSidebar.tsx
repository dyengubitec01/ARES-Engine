// created by ARES team [2026-04-28]
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../features/auth/AuthContext';
import { useAlarms } from '../../hooks/useAlarms';
import NewChatButton from '../common/NewChatButton';
import NotificationButton from '../common/NotificationButton';
import ProfileSection from '../common/ProfileSection';
import SidebarShell from '../common/SidebarShell';
import AdminHeaderLogo from './AdminHeaderLogo';
import AdminMenuList from './AdminMenuList';

export type AdminMenu = '권한 관리' | '사용자 관리' | '문서 관리';
export type AdminIconComp = React.FC<React.SVGProps<SVGSVGElement>>;

interface UseAdminSidebarArgs {
  activeMenu: AdminMenu;
  onMenuChange: (menu: AdminMenu) => void;
}

interface UseAdminSidebarOutput {
  headerActions: (isCollapsed: boolean) => React.ReactNode;
  headerTrailingActions: (isCollapsed: boolean) => React.ReactNode;
  sidebarActions: (isCollapsed: boolean, expandSidebar?: () => void) => React.ReactNode;
  sidebarContent: (isCollapsed: boolean) => React.ReactNode;
}

const ALL_ADMIN_MENUS: AdminMenu[] = ['권한 관리', '사용자 관리', '문서 관리'];

export function useAdminSidebar({ activeMenu, onMenuChange }: UseAdminSidebarArgs): UseAdminSidebarOutput {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
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

  const handleBackToChat = (): void => {
    navigate('/chat');
  };

  const handleLogout = async (): Promise<void> => {
    await logout();
  };

  // 사용자 권한에 따른 메뉴 필터링
  const hasSystemAuthority = user?.authorities?.includes('admin') || false;
  const filteredMenuItems = ALL_ADMIN_MENUS.filter(() => hasSystemAuthority);

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
    return <AdminHeaderLogo />;
  };

  const headerTrailingActions = (isCollapsed: boolean): React.ReactNode => {
    if (isCollapsed) return null;
    return <NotificationButton {...notificationProps} />;
  };

  const sidebarContent = (isCollapsed: boolean): React.ReactNode => (
    <SidebarShell
      profile={
        <ProfileSection
          userName={user?.name}
          userEmail={user?.email}
          isCollapsed={isCollapsed}
          onLogout={handleLogout}
        />
      }
    >
      <AdminMenuList
        isCollapsed={isCollapsed}
        menuItems={filteredMenuItems}
        activeMenu={activeMenu}
        onMenuChange={onMenuChange}
        onBackToChat={handleBackToChat}
      />
    </SidebarShell>
  );

  const sidebarActions = (isCollapsed: boolean): React.ReactNode => (
    <>
      {/* 알림 버튼 (접힘 상태 전용) */}
      {isCollapsed && <NotificationButton {...notificationProps} />}

      {/* New Chat 버튼 */}
      <NewChatButton
        isCollapsed={isCollapsed}
        onClick={(e) => { e.stopPropagation(); navigate('/chat'); }}
      />
    </>
  );

  return {
    headerActions,
    headerTrailingActions,
    sidebarActions,
    sidebarContent,
  };
}