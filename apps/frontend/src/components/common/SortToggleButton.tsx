// created by ARES team [2026-03-20]
import AscSortIcon from '../../assets/docs/asc-sort.svg?react';
import DescSortIcon from '../../assets/docs/desc-sort.svg?react';

export type SortOrder = 'desc' | 'asc';

interface SortToggleButtonProps {
  sortOrder: SortOrder;
  onToggle: () => void;
}

function SortToggleButton({ sortOrder, onToggle }: SortToggleButtonProps) {
  const label = sortOrder === 'desc' ? '최신순' : '오래된순';
  const Icon = sortOrder === 'desc' ? DescSortIcon : AscSortIcon;

  return (
    <button
      onClick={onToggle}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        padding: '8px 4px',
        fontSize: '14px',
        fontWeight: '400',
        color: 'var(--color-grayscale-900)',
        transition: 'opacity 0.2s',
      }}
      onMouseOver={(e) => {
        e.currentTarget.style.opacity = '0.6';
      }}
      onMouseOut={(e) => {
        e.currentTarget.style.opacity = '1';
      }}
      title={sortOrder === 'desc' ? '오래된순으로 변경' : '최신순으로 변경'}
    >
      <span>{label}</span>
      <Icon width={16} height={16} style={{ color: 'var(--color-grayscale-900)' }} />
    </button>
  );
}

export default SortToggleButton;
