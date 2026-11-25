import { useState } from 'react';
import DocumentStatusDashboard from './DocumentStatusDashboard';
import SortToggleButton from '../../components/common/SortToggleButton';
import type { SortOrder } from '../../components/common/SortToggleButton';
import DeleteIcon from '../../assets/docs/delete.svg?react';
import { helpCircleIcon } from '../../assets/icons';
import TagCreateModal from './TagCreateModal';
import TagManageModal from './TagManageModal';
import FilterDropdown, { type FilterOption } from './FilterDropdown';
import DocumentSearchInput from './DocumentSearchInput';

interface DocumentPageHeaderProps<T extends string> {
  title: string;
  dashboardRefreshKey?: number;
  tabs: { key: T; label: string }[];
  activeTab: T;
  onTabChange: (tab: T) => void;
  sortOrder: SortOrder;
  onSortToggle: () => void;
  canDelete: boolean;
  onDelete: () => void;
  onHelpClick?: () => void;
  onSearchChange?: (value: string) => void;
  onTagCreated?: () => void;
  onTagCreateError?: (title: string, message: string) => void;
  onTagsChanged?: () => void;
  deptOptions?: FilterOption[];
  selectedDeptIds?: string[];
  onDeptIdsChange?: (ids: string[]) => void;
  showDeptFilter?: boolean;
  tagOptions?: FilterOption[];
  selectedTagIds?: string[];
  onTagIdsChange?: (ids: string[]) => void;
}

function DocumentPageHeader<T extends string>({
  title,
  dashboardRefreshKey,
  tabs,
  activeTab,
  onTabChange,
  sortOrder,
  onSortToggle,
  canDelete,
  onDelete,
  onHelpClick,
  onSearchChange,
  onTagCreated,
  onTagCreateError,
  onTagsChanged,
  deptOptions,
  selectedDeptIds,
  onDeptIdsChange,
  showDeptFilter,
  tagOptions,
  selectedTagIds,
  onTagIdsChange,
}: DocumentPageHeaderProps<T>) {
  const [isTagModalOpen, setIsTagModalOpen] = useState(false);
  const [isTagManageOpen, setIsTagManageOpen] = useState(false);

  return (
    <>
    <div style={{
      padding: '15px 40px 0 40px',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '30px' }}>
        <div style={{ fontSize: '28px', fontWeight: '600', color: 'var(--color-grayscale-900)' }}>
          {title}
        </div>
        {onHelpClick && (
          <button
            onClick={onHelpClick}
            title="도움말"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'transparent',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            <img src={helpCircleIcon} alt="도움말" style={{ width: '16px', height: '16px' }} />
          </button>
        )}
      </div>
      <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '16px' }}>
        <DocumentStatusDashboard refreshKey={dashboardRefreshKey} />
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
      }}>
        <div style={{
          display: 'flex',
          borderRadius: '8px',
          background: 'var(--color-grayscale-150)',
          padding: '4px',
        }}>
          {tabs.map(tab => (
            <button
              key={tab.key}
              onClick={() => onTabChange(tab.key)}
              style={{
                border: 'none',
                cursor: 'pointer',

                fontSize: '14px',
                fontStyle: 'normal',
                lineHeight: '20px',
                letterSpacing: '-0.28px',

                textAlign: 'center' as const,
                transition: 'all 0.2s',
                ...(activeTab === tab.key
                  ? {
                      borderRadius: '4px',
                      background: 'var(--color-grayscale-50)',
                      boxShadow: '0 1px 3px 0 rgba(26, 22, 64, 0.05), 0 1px 2px 0 rgba(26, 22, 64, 0.04)',
                      color: 'var(--color-primary-700)',
                      fontWeight: '600',
                      padding: '5px 14px',
                      flexDirection: 'column' as const,
                      justifyContent: 'center',
                      alignItems: 'center',
                    }
                  : {
                      background: 'none',
                      color: 'var(--color-grayscale-400)',
                      fontWeight: '500',
                      padding: '5px 14px',
                    }),
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '4px' }}>
          {onSearchChange && <DocumentSearchInput onValueChange={onSearchChange} />}
          {tagOptions && selectedTagIds && onTagIdsChange && (
            <>
              <button
                type="button"
                onClick={() => setIsTagModalOpen(true)}
                style={{
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  padding: '6px 16px',
                  borderRadius: '8px',
                  border: '1px solid var(--color-grayscale-200)',
                  background: 'var(--color-grayscale-100)',
                  cursor: 'pointer',
                  marginRight: '8px',
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
                  }}
                >
                  태그 추가
                </span>
              </button>
              <FilterDropdown
                defaultLabel="전체 태그"
                options={tagOptions}
                selectedIds={selectedTagIds}
                onChange={onTagIdsChange}
                emptyMessage={`내 태그가 없습니다.\n'태그 추가' 버튼으로 만들어 보세요.`}
                footerContent={(close) => (
                  <button
                    type="button"
                    onClick={() => {
                      close();
                      setIsTagManageOpen(true);
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: '100%',
                      padding: '8px',
                      border: 'none',
                      background: 'transparent',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      color: 'var(--color-primary-600)',
                      fontFamily: 'Pretendard',
                      fontSize: '13px',
                      fontWeight: 500,
                      lineHeight: '18px',
                    }}
                    onMouseOver={(e) => {
                      e.currentTarget.style.background = 'var(--color-grayscale-100)';
                    }}
                    onMouseOut={(e) => {
                      e.currentTarget.style.background = 'transparent';
                    }}
                  >
                    태그 관리
                  </button>
                )}
              />
            </>
          )}
          {showDeptFilter && deptOptions && selectedDeptIds && onDeptIdsChange && (
            <FilterDropdown
              defaultLabel="전체 문서"
              options={deptOptions}
              selectedIds={selectedDeptIds}
              onChange={onDeptIdsChange}
            />
          )}
          <SortToggleButton sortOrder={sortOrder} onToggle={onSortToggle} />
          {canDelete && (
            <button
              onClick={onDelete}
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
              onMouseOver={(e) => { e.currentTarget.style.opacity = '0.6'; }}
              onMouseOut={(e) => { e.currentTarget.style.opacity = '1'; }}
              title="선택 문서 삭제"
            >
              <span>삭제</span>
              <DeleteIcon width={16} height={16} style={{ color: 'var(--color-grayscale-900)' }} />
            </button>
          )}
        </div>
      </div>
    </div>
    {tagOptions && selectedTagIds && onTagIdsChange && (
      <TagManageModal
        isOpen={isTagManageOpen}
        onClose={() => setIsTagManageOpen(false)}
        onChanged={() => onTagsChanged?.()}
        onError={(title, message) => onTagCreateError?.(title, message)}
      />
    )}
    {tagOptions && selectedTagIds && onTagIdsChange && (
      <TagCreateModal
        isOpen={isTagModalOpen}
        onClose={() => setIsTagModalOpen(false)}
        onCreated={() => onTagCreated?.()}
        onError={(title, message) => onTagCreateError?.(title, message)}
      />
    )}
    </>
  );
}

export default DocumentPageHeader;
