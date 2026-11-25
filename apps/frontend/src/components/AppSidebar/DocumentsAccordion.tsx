// created by ARES team [2026-04-28]
import { useState } from 'react';
import DocUserIcon from '../../assets/icons/doc-user.svg?react';
import DocIcon from '../../assets/icons/doc.svg?react';
import DocEmbeddingIcon from '../../assets/icons/doc-embedding.svg?react';
import ToggleIcon from '../../assets/icons/toggle.svg?react';
import DocAccordionItem from './DocAccordionItem';

interface DocumentsAccordionProps {
  isCollapsed: boolean;
  isOpen: boolean;
  onToggle: () => void;
  onCollapsedClick: () => void;
  isDocumentsPage: boolean;
  isDocumentsListPage: boolean;
  isDocumentsApprovalPage: boolean;
  showApprovalMenu: boolean;
  onListClick: () => void;
  onApprovalClick: () => void;
}

function DocumentsAccordion({
  isCollapsed,
  isOpen,
  onToggle,
  onCollapsedClick,
  isDocumentsPage,
  isDocumentsListPage,
  isDocumentsApprovalPage,
  showApprovalMenu,
  onListClick,
  onApprovalClick,
}: DocumentsAccordionProps) {
  const [hoveredDocsMenu, setHoveredDocsMenu] = useState<'list' | 'approval' | null>(null);

  const isListActive = isDocumentsListPage || hoveredDocsMenu === 'list';
  const isApprovalActive = isDocumentsApprovalPage || hoveredDocsMenu === 'approval';

  return (
    <div style={{ width: isCollapsed ? '48px' : '100%', flexShrink: 0 }}>
      <button
        onClick={(e) => {
          e.stopPropagation();
          if (isCollapsed) {
            onCollapsedClick();
          } else {
            onToggle();
          }
        }}
        style={{
          width: '100%',
          height: isCollapsed ? 'auto' : 'auto',
          padding: isCollapsed ? '8px 12px' : '7px 12px',
          backgroundColor: isDocumentsPage ? 'var(--color-grayscale-150)' : 'transparent',
          color: 'var(--color-grayscale-900)',
          border: 'none',
          borderRadius: '8px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: isCollapsed ? 'center' : 'space-between',
          transition: 'all 0.2s',
        }}
        onMouseOver={(e) => {
          e.currentTarget.style.backgroundColor = 'var(--color-grayscale-150)';
        }}
        onMouseOut={(e) => {
          if (!isDocumentsPage) {
            e.currentTarget.style.backgroundColor = 'transparent';
          }
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: isCollapsed ? '0' : '8px' }}>
          <DocUserIcon width={24} height={24} style={{ color: 'var(--icon-color)', flexShrink: 0 }} />
          {!isCollapsed && <span style={{ fontSize: '16px', fontWeight: '400' }}>문서 보관함</span>}
        </div>
        {!isCollapsed && (
          <ToggleIcon
            width={24}
            height={24}
            style={{
              color: '#8E8E8E',
              transition: 'transform 0.2s',
              transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)',
              flexShrink: 0,
            }}
          />
        )}
      </button>

      {!isCollapsed && isOpen && (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          gap: '4px',
          marginTop: '2px',
        }}>
          <DocAccordionItem
            Icon={DocIcon}
            label="문서 목록"
            isActive={isListActive}
            onClick={onListClick}
            onHoverChange={(hovered) => setHoveredDocsMenu(hovered ? 'list' : null)}
          />

          {showApprovalMenu && (
            <DocAccordionItem
              Icon={DocEmbeddingIcon}
              label="문서 승인 관리"
              isActive={isApprovalActive}
              onClick={onApprovalClick}
              onHoverChange={(hovered) => setHoveredDocsMenu(hovered ? 'approval' : null)}
            />
          )}
        </div>
      )}
    </div>
  );
}

export default DocumentsAccordion;