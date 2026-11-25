// created by ARES team [2026-03-24]
import { useRef, useEffect, useState, type ComponentType, type SVGProps } from 'react';
import { createPortal } from 'react-dom';
import ViewMoreIcon from '../../assets/icons/more.svg?react';

export interface DropdownMenuItem {
  label: string;
  icon?: ComponentType<SVGProps<SVGSVGElement>>;
  onClick: () => void | Promise<void>;
}

interface DropdownMenuProps {
  isOpen: boolean;
  onToggle: () => void;
  onClose: () => void;
  items: DropdownMenuItem[];
}

function DropdownMenu({ isOpen, onToggle, onClose, items }: DropdownMenuProps) {
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState<{ top: number; left: number }>({ top: 0, left: 0 });

  // 버튼 위치 기준으로 드롭다운 좌표 계산
  useEffect(() => {
    if (isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      setPosition({
        top: rect.bottom + 4,
        left: rect.right,
      });
    }
  }, [isOpen]);

  // 외부 클릭 감지
  useEffect(() => {
    if (!isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        (!buttonRef.current || !buttonRef.current.contains(target)) &&
        (!menuRef.current || !menuRef.current.contains(target))
      ) {
        onClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, onClose]);

  return (
    <>
      <button
        ref={buttonRef}
        onClick={(e) => {
          e.stopPropagation();
          onToggle();
        }}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          margin: '0 auto',
          padding: '0',
          transition: 'opacity 0.2s'
        }}
        onMouseOver={(e) => (e.currentTarget.style.opacity = '0.6')}
        onMouseOut={(e) => (e.currentTarget.style.opacity = '1')}
      >
        <ViewMoreIcon width={20} height={20} style={{ color: 'var(--color-grayscale-400)' }} />
      </button>
      {isOpen && createPortal(
        <div
          ref={menuRef}
          onClick={(e) => e.stopPropagation()}
          style={{
            position: 'fixed',
            top: `${position.top}px`,
            left: `${position.left}px`,
            transform: 'translateX(-100%)',
            zIndex: 10000,
            backgroundColor: 'var(--menu-bg)',
            borderRadius: '8px',
            boxShadow: 'var(--shadow-dropdown)',
            minWidth: '120px',
            overflow: 'hidden'
          }}
        >
          {items.map((item) => (
            <button
              key={item.label}
              onClick={async (e) => {
                e.stopPropagation();
                onClose();
                await item.onClick();
              }}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 14px',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '13px',
                color: 'var(--color-grayscale-900)',
                whiteSpace: 'nowrap'
              }}
              onMouseOver={(e) => (e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100)')}
              onMouseOut={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              {item.icon && <item.icon width={16} height={16} style={{ color: 'var(--color-grayscale-900)' }} />}
              {item.label}
            </button>
          ))}
        </div>,
        document.body
      )}
    </>
  );
}

export default DropdownMenu;
