// created by ARES team [2026-04-28]
import type { ComponentType, SVGProps } from 'react';

interface AdminMenuItemProps {
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
  iconWidth?: number;
  iconHeight?: number;
  label: string;
  isActive: boolean;
  isCollapsed: boolean;
  onClick: () => void;
}

function AdminMenuItem({ Icon, iconWidth = 24, iconHeight = 24, label, isActive, isCollapsed, onClick }: AdminMenuItemProps) {
  if (isCollapsed) {
    return (
      <button
        onClick={onClick}
        style={{
          padding: '8px 12px',
          backgroundColor: isActive ? 'var(--color-grayscale-150)' : 'transparent',
          borderRadius: '8px',
          border: 'none',
          cursor: 'pointer',
          transition: 'all 0.2s',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
        onMouseOver={(e) => {
          if (!isActive) {
            e.currentTarget.style.backgroundColor = 'var(--color-grayscale-150)';
          }
        }}
        onMouseOut={(e) => {
          if (!isActive) {
            e.currentTarget.style.backgroundColor = 'transparent';
          }
        }}
      >
        <Icon width={iconWidth} height={iconHeight} style={{ color: 'var(--icon-color)' }} />
      </button>
    );
  }

  return (
    <div
      onClick={onClick}
      style={{
        padding: '7px 12px',
        backgroundColor: isActive ? 'var(--color-grayscale-150)' : 'transparent',
        borderRadius: '8px',
        border: 'none',
        cursor: 'pointer',
        transition: 'all 0.2s',
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
      }}
      onMouseOver={(e) => {
        if (!isActive) {
          e.currentTarget.style.backgroundColor = 'var(--color-grayscale-150)';
        }
      }}
      onMouseOut={(e) => {
        if (!isActive) {
          e.currentTarget.style.backgroundColor = 'transparent';
        }
      }}
    >
      <Icon width={iconWidth} height={iconHeight} style={{ color: 'var(--icon-color)', flexShrink: 0 }} />
      <span style={{
        fontWeight: '400',
        color: 'var(--color-grayscale-900)',
        fontSize: '16px'
      }}>
        {label}
      </span>
    </div>
  );
}

export default AdminMenuItem;