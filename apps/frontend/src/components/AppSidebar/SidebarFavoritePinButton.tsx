// created by ARES team [2026-04-28]
import ChatFavPinIcon from '../../assets/chats/fav-pin.svg?react';

interface SidebarFavoritePinButtonProps {
  onClick: () => void;
}

function SidebarFavoritePinButton({ onClick }: SidebarFavoritePinButtonProps) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      style={{
        width: '48px',
        padding: '8px 12px',
        backgroundColor: 'transparent',
        color: 'var(--color-grayscale-900)',
        border: 'none',
        borderRadius: '8px',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'all 0.2s',
      }}
      onMouseOver={(e) => {
        e.currentTarget.style.backgroundColor = 'var(--color-grayscale-150)';
      }}
      onMouseOut={(e) => {
        e.currentTarget.style.backgroundColor = 'transparent';
      }}
      title="즐겨찾기"
    >
      <ChatFavPinIcon width={24} height={24} style={{ color: 'var(--icon-color)', flexShrink: 0 }} />
    </button>
  );
}

export default SidebarFavoritePinButton;