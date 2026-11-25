// created by ARES team [2026-04-28]
import { submitIcon } from '../../../assets/icons';
import {
  GRADIENT,
  gradientButtonBase,
  secondaryButtonStyle,
  secondaryButtonHoverHandlers,
  buildGradientHoverHandlers,
} from '../../../styles/buttonStyles';

interface SurveyDoneViewProps {
  onClose: () => void;
  onRestart: () => void;
}

function SurveyDoneView({ onClose, onRestart }: SurveyDoneViewProps) {
  return (
    <>
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
          평가가 완료되었습니다!
        </div>
        <div style={{ fontSize: '14px', color: 'var(--color-grayscale-400)', textAlign: 'center' }}>
          소중한 의견 감사합니다.
        </div>
      </div>
      <div style={{ display: 'flex', gap: '16px', padding: '0 40px 40px', flexShrink: 0 }}>
        <button
          onClick={onClose}
          style={secondaryButtonStyle}
          {...secondaryButtonHoverHandlers}
        >
          닫기
        </button>
        <button
          onClick={onRestart}
          style={{
            ...gradientButtonBase,
            background: GRADIENT.primarySoft,
            padding: '10px 28px',
            width: '406px',
            borderRadius: '999px',
            transition: 'opacity 0.2s',
            flexShrink: 0,
          }}
          {...buildGradientHoverHandlers(false)}
        >
          다시 평가하기
        </button>
      </div>
    </>
  );
}

export default SurveyDoneView;