// created by ARES team [2026-03-19]
import { feedbackIcon } from '../../assets/icons';
import { useFeedbackModal } from '../../contexts/FeedbackModalContext';

function ErrorReportButton() {
  const { openModal } = useFeedbackModal();

  return (
    <button
      onClick={openModal}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        backgroundColor: 'transparent',
        border: 'none',
        cursor: 'pointer',
        padding: 0,
      }}
    >
      <img src={feedbackIcon} alt="피드백 보내기" style={{ width: '16px', height: '16px' }} />
      <span
        style={{
          fontSize: '12px',
          fontWeight: 500,
          color: 'var(--color-grayscale-400)',
        }}
      >
        피드백 보내기 &gt;
      </span>
    </button>
  );
}

export default ErrorReportButton;
