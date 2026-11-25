// created by ARES team [2026-06-15]
import { ReactNode, useEffect, useRef, useState } from 'react';
import ToggleIcon from '../../assets/icons/toggle.svg?react';
import Checkbox from '../../components/common/Checkbox';

export interface FilterOption {
  id: string;
  label: string;
}

interface FilterDropdownProps {
  defaultLabel: string;
  options: FilterOption[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
  emptyMessage?: string;
  footerContent?: (closeDropdown: () => void) => ReactNode;
}

function FilterDropdown({
  defaultLabel,
  options,
  selectedIds,
  onChange,
  emptyMessage,
  footerContent,
}: FilterDropdownProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [isOpen]);

  const buttonLabel = (() => {
    if (selectedIds.length === 0) return defaultLabel;
    const firstSelected = options.find((o) => selectedIds.includes(o.id));
    if (!firstSelected) return defaultLabel;
    if (selectedIds.length === 1) return firstSelected.label;
    return `${firstSelected.label} +${selectedIds.length - 1}`;
  })();

  const toggleId = (id: string) => {
    if (selectedIds.includes(id)) {
      onChange(selectedIds.filter((x) => x !== id));
    } else {
      onChange([...selectedIds, id]);
    }
  };

  const handleSelectAll = () => {
    onChange([]);
  };

  return (
    <div ref={containerRef} style={{ position: 'relative', marginRight: '8px' }}>
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '16px',
          padding: '6px 6px 6px 16px',
          borderRadius: '8px',
          border: '1px solid var(--color-grayscale-200)',
          background: 'var(--color-grayscale-100)',
          cursor: 'pointer',
        }}
      >
        <span
          style={{
            color: 'var(--color-grayscale-400)',
            fontFamily: 'Pretendard',
            fontSize: '13px',
            fontStyle: 'normal',
            fontWeight: 500,
            lineHeight: '20px',
            letterSpacing: '-0.26px',
            whiteSpace: 'nowrap',
          }}
        >
          {buttonLabel}
        </span>
        <ToggleIcon
          width={16}
          height={16}
          style={{
            color: 'var(--color-grayscale-400)',
            flexShrink: 0,
            transition: 'transform 0.2s',
            transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
          }}
        />
      </button>

      {isOpen && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            minWidth: '200px',
            maxHeight: '320px',
            overflowY: 'auto',
            background: 'var(--color-grayscale-50)',
            border: '1px solid var(--color-grayscale-200)',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.08)',
            padding: '6px',
            zIndex: 10,
            boxSizing: 'border-box',
          }}
        >
          {options.length === 0 ? (
            <div
              style={{
                padding: '12px 8px',
                color: 'var(--color-grayscale-500)',
                fontFamily: 'Pretendard',
                fontSize: '13px',
                fontWeight: 400,
                lineHeight: '18px',
                whiteSpace: 'pre-wrap',
              }}
            >
              {emptyMessage ?? '항목이 없습니다.'}
            </div>
          ) : (
            <>
              <button
                type="button"
                onClick={handleSelectAll}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  width: '100%',
                  padding: '8px',
                  border: 'none',
                  background: 'transparent',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
                onMouseOver={(e) => { e.currentTarget.style.background = 'var(--color-grayscale-100)'; }}
                onMouseOut={(e) => { e.currentTarget.style.background = 'transparent'; }}
              >
                <Checkbox
                  checked={selectedIds.length === 0}
                  onChange={handleSelectAll}
                />
                <span
                  style={{
                    color: 'var(--color-grayscale-900)',
                    fontFamily: 'Pretendard',
                    fontSize: '13px',
                    fontWeight: 500,
                    lineHeight: '18px',
                  }}
                >
                  {defaultLabel}
                </span>
              </button>
              <div style={{ height: '1px', background: 'var(--color-grayscale-200)', margin: '4px 0' }} />
              {options.map((opt) => {
                const checked = selectedIds.includes(opt.id);
                return (
                  <button
                    key={opt.id}
                    type="button"
                    onClick={() => toggleId(opt.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      width: '100%',
                      padding: '8px',
                      border: 'none',
                      background: 'transparent',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                    onMouseOver={(e) => { e.currentTarget.style.background = 'var(--color-grayscale-100)'; }}
                    onMouseOut={(e) => { e.currentTarget.style.background = 'transparent'; }}
                  >
                    <Checkbox checked={checked} onChange={() => toggleId(opt.id)} />
                    <span
                      style={{
                        color: 'var(--color-grayscale-900)',
                        fontFamily: 'Pretendard',
                        fontSize: '13px',
                        fontWeight: 400,
                        lineHeight: '18px',
                        flex: 1,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                    >
                      {opt.label}
                    </span>
                  </button>
                );
              })}
            </>
          )}
          {footerContent && (
            <>
              <div style={{ height: '1px', background: 'var(--color-grayscale-200)', margin: '4px 0' }} />
              {footerContent(() => setIsOpen(false))}
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default FilterDropdown;
