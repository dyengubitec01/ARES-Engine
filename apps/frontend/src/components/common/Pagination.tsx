// created by ARES team [2026-03-12]
import { useState } from 'react';
import { pageNextIcon, pageLastIcon } from '../../assets/icons';

export interface PaginationProps {
  currentPage: number;
  totalItems: number;
  itemsPerPage: number;
  onPageChange: (page: number) => void;
  itemLabel?: string;
}

const COLORS = {
  active: 'var(--color-secondary-300)',
  hover: 'var(--color-grayscale-100)',
  default: 'var(--color-grayscale-50)',
  textActive: 'var(--color-grayscale-50)',
  textDisabled: '#9ca3af',
  textDefault: 'var(--color-grayscale-900, #31343E)',
  border: 'var(--color-grayscale-150)'
} as const;

const BASE_BUTTON_STYLE = {
  padding: '6px 10px',
  border: `1px solid ${COLORS.border}`,
  borderRadius: '6px',
  fontSize: '13px',
  fontStyle: 'normal' as const,
  fontWeight: '400',
  lineHeight: '18px',
  letterSpacing: '-0.26px',
  
  transition: 'all 0.2s'
} as const;

interface PageButtonProps {
  onClick: () => void;
  disabled?: boolean;
  isActive?: boolean;
  children: React.ReactNode;
}

function PageButton({ onClick, disabled = false, isActive = false, children }: PageButtonProps) {
  const [isHovered, setIsHovered] = useState(false);

  const getBackgroundColor = () => {
    if (isActive) return COLORS.active;
    if (disabled) return COLORS.hover;
    if (isHovered) return COLORS.hover;
    return COLORS.default;
  };

  const getTextColor = () => {
    if (isActive) return COLORS.textActive;
    if (disabled) return COLORS.textDisabled;
    return COLORS.textDefault;
  };

  const getFontWeight = () => {
    if (isActive) return '600';
    return '400';
  };

  return (
    <button
      onClick={onClick}
      disabled={disabled}
      onMouseOver={() => !isActive && !disabled && setIsHovered(true)}
      onMouseOut={() => setIsHovered(false)}
      style={{
        ...BASE_BUTTON_STYLE,
        backgroundColor: getBackgroundColor(),
        color: getTextColor(),
        fontWeight: getFontWeight(),
        cursor: disabled ? 'not-allowed' : 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
      }}
    >
      {children}
    </button>
  );
}

function Pagination({
  currentPage,
  totalItems,
  itemsPerPage,
  onPageChange
}: PaginationProps) {

  if (totalItems === 0) return null;

  const totalPages = Math.ceil(totalItems / itemsPerPage);
  const maxVisiblePages = 5;

  let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
  const endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

  if (endPage - startPage + 1 < maxVisiblePages) {
    startPage = Math.max(1, endPage - maxVisiblePages + 1);
  }

  const pageNumbers = Array.from(
    { length: endPage - startPage + 1 },
    (_, i) => startPage + i
  );

  return (
    <div style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      gap: '8px',
      padding: '16px 20px',
      backgroundColor: 'transparent'
    }}>
      <PageButton
        onClick={() => onPageChange(1)}
        disabled={currentPage === 1}
      >
        <img src={pageLastIcon} alt="" style={{ width: '16px', height: '16px', opacity: currentPage === 1 ? 0.4 : 1 }} />
        <span>처음</span>
      </PageButton>

      <PageButton
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage === 1}
      >
        <img src={pageNextIcon} alt="" style={{ width: '16px', height: '16px', opacity: currentPage === 1 ? 0.4 : 1 }} />
        <span>뒤로</span>
      </PageButton>

      {pageNumbers.map((pageNum) => (
        <PageButton
          key={pageNum}
          onClick={() => onPageChange(pageNum)}
          isActive={currentPage === pageNum}
        >
          {pageNum}
        </PageButton>
      ))}

      <PageButton
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage === totalPages}
      >
        <span>다음</span>
        <img src={pageNextIcon} alt="" style={{ width: '16px', height: '16px', transform: 'rotate(180deg)', opacity: currentPage === totalPages ? 0.4 : 1 }} />
      </PageButton>

      <PageButton
        onClick={() => onPageChange(totalPages)}
        disabled={currentPage === totalPages}
      >
        <span>마지막</span>
        <img src={pageLastIcon} alt="" style={{ width: '16px', height: '16px', transform: 'rotate(180deg)', opacity: currentPage === totalPages ? 0.4 : 1 }} />
      </PageButton>
    </div>
  );
}

export default Pagination;
