// created by ARES team [2026-04-28]
import { BoardTab } from './useBoard';

interface BoardTabsProps {
  activeTab: BoardTab;
  onTabChange: (tab: BoardTab) => void;
}

function BoardTabs({ activeTab, onTabChange }: BoardTabsProps) {
  return (
    <div style={{ display: 'flex', flexShrink: 0 }}>
      {(['error', 'suggestion', 'usability'] as const).map((tab) => {
        const isActive = activeTab === tab;
        const label =
          tab === 'error' ? '오류 신고하기'
          : tab === 'suggestion' ? '서비스 제안하기'
          : '사용성 평가하기';
        return (
          <button
            key={tab}
            onClick={() => onTabChange(tab)}
            style={{
              flex: '1 0 0',
              padding: '20px 16px 14px',
              backgroundColor: isActive ? 'var(--color-primary-100, #F2F3FF)' : 'transparent',
              border: 'none',
              borderBottom: isActive ? '2px solid var(--color-primary-600, #626BF7)' : '2px solid var(--color-grayscale-150)',
              fontSize: '15px',
              fontWeight: isActive ? 600 : 400,
              color: isActive ? 'var(--color-primary-600)' : 'var(--color-grayscale-400)',
              cursor: 'pointer',
              transition: 'color 0.2s, background-color 0.2s',
              textAlign: 'center',
            }}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

export default BoardTabs;