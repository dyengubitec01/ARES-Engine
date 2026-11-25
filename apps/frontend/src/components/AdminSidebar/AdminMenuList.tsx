// created by ARES team [2026-04-28]
import AdminUserIcon from '../../assets/admin/user.svg?react';
import AdminGroupIcon from '../../assets/admin/group.svg?react';
import AdminDocFolderIcon from '../../assets/admin/docfolder.svg?react';
import AdminMenuItem from './AdminMenuItem';
import AdminBackToChatButton from './AdminBackToChatButton';
import type { AdminMenu, AdminIconComp } from './AdminSidebar';

interface MenuIconConfig {
  Icon: AdminIconComp;
  width: number;
  height: number;
}

const menuIconMap: Record<AdminMenu, MenuIconConfig> = {
  '권한 관리': { Icon: AdminGroupIcon, width: 24, height: 24 },
  '사용자 관리': { Icon: AdminUserIcon, width: 24, height: 24 },
  '문서 관리': { Icon: AdminDocFolderIcon, width: 21, height: 20 }
};

interface AdminMenuListProps {
  isCollapsed: boolean;
  menuItems: AdminMenu[];
  activeMenu: AdminMenu;
  onMenuChange: (menu: AdminMenu) => void;
  onBackToChat: () => void;
}

function AdminMenuList({ isCollapsed, menuItems, activeMenu, onMenuChange, onBackToChat }: AdminMenuListProps) {
  const containerStyle = isCollapsed
    ? {
        flex: 1,
        display: 'flex',
        flexDirection: 'column' as const,
        alignItems: 'center',
        padding: '10px 0',
        gap: '8px'
      }
    : {
        flex: 1,
        overflowY: 'auto' as const,
        padding: '2px 20px',
        display: 'flex' as const,
        flexDirection: 'column' as const,
        gap: '8px'
      };

  return (
    <div style={containerStyle}>
      {menuItems.map((menu) => {
        const { Icon, width, height } = menuIconMap[menu];
        return (
          <AdminMenuItem
            key={menu}
            Icon={Icon}
            iconWidth={width}
            iconHeight={height}
            label={menu}
            isActive={activeMenu === menu}
            isCollapsed={isCollapsed}
            onClick={() => onMenuChange(menu)}
          />
        );
      })}

      <hr style={{
        width: 'calc(100% - 40px)',
        border: 'none',
        borderTop: '1px solid var(--color-grayscale-200)',
        margin: '16px auto',
      }} />

      <AdminBackToChatButton isCollapsed={isCollapsed} onClick={onBackToChat} />
    </div>
  );
}

export default AdminMenuList;