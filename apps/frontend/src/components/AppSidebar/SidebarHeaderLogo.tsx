// created by ARES team [2026-04-28]
import HeaderIcon from '../../assets/icons/header-icon.svg?react';

interface SidebarHeaderLogoProps {
  onClick: () => void;
}

function SidebarHeaderLogo({ onClick }: SidebarHeaderLogoProps) {
  return (
    <div
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        cursor: 'pointer'
      }}
    >
      <HeaderIcon width={12} height={12} style={{ color: 'var(--color-grayscale-500)' }} />
      <span style={{
        fontSize: '13px',
        fontWeight: '500',
        color: 'var(--color-grayscale-500)'
      }}>
        대영유비텍 LLM
      </span>
    </div>
  );
}

export default SidebarHeaderLogo;