// created by ARES team [2026-04-28]
import { useState } from 'react';
import SearchIcon from '../../assets/icons/search.svg?react';

interface SidebarSearchInputProps {
  isCollapsed: boolean;
  searchQuery: string;
  setSearchQuery: (v: string) => void;
  expandSidebar?: () => void;
}

function SidebarSearchInput({ isCollapsed, searchQuery, setSearchQuery, expandSidebar }: SidebarSearchInputProps) {
  const [isSearchFocused, setIsSearchFocused] = useState<boolean>(false);
  const isSearchInputMode = isSearchFocused || searchQuery.trim() !== '';

  if (!isCollapsed && isSearchInputMode) {
    return (
      <div
        style={{
          width: '100%',
          padding: '7px 12px',
          marginTop: '12px',
          marginBottom: '0',
          borderRadius: '999px',
          border: '1px solid var(--color-grayscale-200)',
          background: 'var(--color-grayscale-50)',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          flexShrink: 0,
          boxSizing: 'border-box',
        }}
      >
        <SearchIcon
          width={24}
          height={24}
          style={{
            flexShrink: 0,
            color: searchQuery.trim() === '' ? 'var(--color-grayscale-400)' : 'var(--icon-color)',
          }}
        />
        <input
          type="text"
          className="sidebar-search-input"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onFocus={() => setIsSearchFocused(true)}
          onBlur={() => setIsSearchFocused(false)}
          placeholder="검색어를 입력하세요"
          autoFocus
          style={{
            flex: 1,
            minWidth: 0,
            border: 'none',
            outline: 'none',
            background: 'transparent',
            padding: 0,
            color: 'var(--color-grayscale-900)',
            fontFamily: 'Pretendard',
            fontSize: '16px',
            fontStyle: 'normal',
            fontWeight: 400,
            lineHeight: '26px',
            letterSpacing: '-0.32px',
          }}
        />
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        if (isCollapsed && expandSidebar) {
          expandSidebar();
        }
        setIsSearchFocused(true);
      }}
      onMouseOver={(e) => {
        if (isCollapsed) {
          e.currentTarget.style.backgroundColor = 'var(--color-grayscale-150)';
        }
      }}
      onMouseOut={(e) => {
        e.currentTarget.style.backgroundColor = 'transparent';
      }}
      aria-label="검색"
      style={{
        width: isCollapsed ? '48px' : '100%',
        padding: isCollapsed ? '8px 12px' : '7px 12px',
        marginTop: isCollapsed ? '0' : '12px',
        marginBottom: isCollapsed ? '-12px' : '0',
        backgroundColor: 'transparent',
        border: '1px solid transparent',
        borderRadius: '8px',
        boxSizing: 'border-box',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: isCollapsed ? 'center' : 'flex-start',
        gap: isCollapsed ? '0' : '12px',
        color: 'var(--color-grayscale-900)',
        fontFamily: 'Pretendard',
        fontSize: '16px',
        fontStyle: 'normal',
        fontWeight: 400,
        lineHeight: '26px',
        letterSpacing: '-0.32px',
        flexShrink: 0,
        transition: 'background-color 0.2s',
      }}
    >
      <SearchIcon width={24} height={24} style={{ flexShrink: 0, color: 'var(--icon-color)' }} />
      {!isCollapsed && <span>검색</span>}
    </button>
  );
}

export default SidebarSearchInput;