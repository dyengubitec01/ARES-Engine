// created by ARES team [2026-04-28]
import AdminChatIcon from '../../assets/admin/admin-chat.svg?react';
import AdminChat2Icon from '../../assets/admin/admin-chat2.svg?react';

interface AdminBackToChatButtonProps {
  isCollapsed: boolean;
  onClick: () => void;
}

function AdminBackToChatButton({ isCollapsed, onClick }: AdminBackToChatButtonProps) {
  if (isCollapsed) {
    return (
      <button
        onClick={onClick}
        style={{
          padding: '8px 12px',
          backgroundColor: 'transparent',
          borderRadius: '8px',
          border: 'none',
          cursor: 'pointer',
          transition: 'all 0.2s',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
        onMouseOver={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--color-grayscale-150)';
        }}
        onMouseOut={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent';
        }}
      >
        <AdminChatIcon width={24} height={24} style={{ color: 'var(--icon-color)' }} />
      </button>
    );
  }

  return (
    <div
      onClick={onClick}
      style={{
        padding: '7px 12px',
        backgroundColor: 'transparent',
        borderRadius: '8px',
        border: 'none',
        cursor: 'pointer',
        transition: 'all 0.2s',
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}
      onMouseOver={(e) => {
        e.currentTarget.style.backgroundColor = 'var(--color-grayscale-150)';
      }}
      onMouseOut={(e) => {
        e.currentTarget.style.backgroundColor = 'transparent';
      }}
    >
      <AdminChatIcon width={24} height={24} style={{ color: 'var(--icon-color)', flexShrink: 0 }} />
      <span style={{
        flex: 1,
        fontWeight: '400',
        color: 'var(--color-grayscale-900)',
        fontSize: '16px'
      }}>
        채팅으로 돌아가기
      </span>
      <AdminChat2Icon width={24} height={24} style={{ color: '#8E8E8E', flexShrink: 0 }} />
    </div>
  );
}

export default AdminBackToChatButton;