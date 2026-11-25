// created by ARES team [2026-04-28]
import { ComponentType, SVGProps } from 'react';

interface DocAccordionItemProps {
  Icon: ComponentType<SVGProps<SVGSVGElement>>;
  label: string;
  isActive: boolean;
  onClick: () => void;
  onHoverChange: (hovered: boolean) => void;
}

function DocAccordionItem({ Icon, label, isActive, onClick, onHoverChange }: DocAccordionItemProps) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      onMouseOver={() => onHoverChange(true)}
      onMouseOut={() => onHoverChange(false)}
      style={{
        width: '100%',
        padding: '7px 12px 7px 24px',
        backgroundColor: 'transparent',
        color: isActive ? 'var(--color-primary-600)' : 'var(--color-grayscale-900)',
        border: 'none',
        borderRadius: '8px',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        transition: 'color 0.2s',
      }}
    >
      <Icon
        width={20}
        height={20}
        style={{
          flexShrink: 0,
          color: isActive ? 'var(--icon-active-color)' : 'var(--icon-color)',
          transition: 'color 0.2s',
        }}
      />
      <span style={{ fontSize: '16px', fontWeight: '400' }}>{label}</span>
    </button>
  );
}

export default DocAccordionItem;