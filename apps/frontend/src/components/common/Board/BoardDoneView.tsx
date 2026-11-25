// created by ARES team [2026-04-28]
import { submitIcon } from '../../../assets/icons';
import {
  GRADIENT,
  gradientButtonBase,
  secondaryButtonStyle,
  secondaryButtonHoverHandlers,
  buildGradientHoverHandlers,
} from '../../../styles/buttonStyles';
import BoardTabs from './BoardTabs';
import { BoardTab, BoardViewMode } from './useBoard';

interface BoardDoneViewProps {
  activeTab: BoardTab;
  setActiveTab: (tab: BoardTab) => void;
  setViewMode: (mode: BoardViewMode) => void;
  onBackToList: () => void;
  onClose: () => void;
  onPageReset: (page: number) => void;
}

function BoardDoneView({ activeTab, setActiveTab, setViewMode, onBackToList, onClose, onPageReset }: BoardDoneViewProps) {
  const handleTabChange = (tab: BoardTab) => {
    setActiveTab(tab);
    setViewMode('list');
    onPageReset(1);
  };

  return (
    <>
      <BoardTabs activeTab={activeTab} onTabChange={handleTabChange} />

      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '12px',
        padding: '0 40px',
      }}>
        <img src={submitIcon} alt="제출 완료" style={{ width: '40px', height: '40px' }} />
        <div style={{ fontSize: '18px', fontWeight: 700, color: 'var(--color-grayscale-900)', textAlign: 'center' }}>
          제출이 완료되었습니다!
        </div>
        <div style={{ fontSize: '14px', color: 'var(--color-grayscale-400)', textAlign: 'center' }}>
          검토 후 처리 결과를 알려드립니다.
        </div>
      </div>

      <div style={{
        display: 'flex',
        gap: '16px',
        padding: '0 40px 40px',
        flexShrink: 0,
      }}>
        <button
          onClick={onBackToList}
          style={secondaryButtonStyle}
          {...secondaryButtonHoverHandlers}
        >
          목록으로 돌아가기
        </button>

        <button
          onClick={onClose}
          style={{
            ...gradientButtonBase,
            background: GRADIENT.primarySoft,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '10px 28px',
            flex: 1,
            borderRadius: '999px',
            transition: 'opacity 0.2s',
          }}
          {...buildGradientHoverHandlers(false)}
        >
          닫기
        </button>
      </div>
    </>
  );
}

export default BoardDoneView;
