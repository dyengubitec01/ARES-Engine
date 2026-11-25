// created by ARES team [2026-03-20]
import { toastFailedIcon } from '../../assets/icons';
import {
  GRADIENT,
  GRADIENT_ACTIVE_SHADOW,
  gradientButtonBase,
  secondaryButtonStyle,
  secondaryButtonHoverHandlers,
} from '../../styles/buttonStyles';
import { useScrollFade } from '../../hooks/useScrollFade';
import { useSurveyForm } from './Survey/useSurveyForm';
import SurveyDoneView from './Survey/SurveyDoneView';
import SurveyProgressHeader from './Survey/SurveyProgressHeader';
import SurveyRatingQuestion from './Survey/SurveyRatingQuestion';
import SurveyTextQuestion from './Survey/SurveyTextQuestion';

interface SurveyFormProps {
  onClose: () => void;
}

function SurveyForm({ onClose }: SurveyFormProps) {
  const survey = useSurveyForm();
  const { ref: scrollContainerRef, showTopFade, showBottomFade, handleScroll } = useScrollFade<HTMLDivElement>(10, { eager: true });

  if (survey.isDone) {
    return <SurveyDoneView onClose={onClose} onRestart={survey.handleRestart} />;
  }

  const isDisabled = !survey.isStepComplete() || survey.isSubmitting;
  const subtitle = survey.step.type === 'text'
    ? '대영유비텍의 AI 서비스가 더 좋아지도록 여러분의 목소리를 들려주세요.'
    : `${survey.step.title}에서의 경험을 솔직하게 평가해주세요.`;

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <SurveyProgressHeader
        title={survey.step.title}
        subtitle={subtitle}
        progressPercent={survey.progressPercent}
      />

      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minHeight: 0 }}>
        {showTopFade && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '48px',
            background: 'linear-gradient(to bottom, var(--color-scroll-fade), transparent)',
            pointerEvents: 'none',
            zIndex: 1,
          }} />
        )}
        {showBottomFade && (
          <div style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: '48px',
            background: 'linear-gradient(to top, var(--color-scroll-fade), transparent)',
            pointerEvents: 'none',
            zIndex: 1,
          }} />
        )}
        <div ref={scrollContainerRef} onScroll={handleScroll} style={{ height: '100%', overflow: 'auto', padding: '36px 40px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {survey.step.type === 'rating' && survey.step.questions.map((q) => (
            <SurveyRatingQuestion
              key={q.key}
              question={q}
              value={survey.answers[q.key] as number | undefined}
              onChange={(v) => survey.handleRatingChange(q.key, v)}
            />
          ))}

          {survey.step.type === 'text' && survey.step.questions.map((q) => (
            <SurveyTextQuestion
              key={q.key}
              question={q}
              value={(survey.answers[q.key] as string) || ''}
              onChange={(v) => survey.handleTextChange(q.key, v)}
            />
          ))}
        </div>
      </div>

      {survey.submitError && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          margin: '0 32px 12px',
          color: 'var(--color-error-500)',
          fontSize: '13px',
          fontWeight: 500,
          lineHeight: '20px',
          letterSpacing: '-0.26px',
          flexShrink: 0,
        }}>
          <img src={toastFailedIcon} alt="" style={{ width: '14px', height: '14px', flexShrink: 0 }} />
          <span>{survey.submitError}</span>
        </div>
      )}

      <div style={{
        display: 'flex',
        gap: '16px',
        padding: '0 40px 40px',
        flexShrink: 0,
      }}>
        <button
          onClick={survey.currentStep === 0 ? onClose : survey.handlePrev}
          style={secondaryButtonStyle}
          {...secondaryButtonHoverHandlers}
        >
          {survey.currentStep === 0 ? '취소' : '이전'}
        </button>

        <button
          onClick={survey.isLastStep ? survey.handleSubmit : survey.handleNext}
          disabled={isDisabled}
          style={{
            ...gradientButtonBase,
            background: GRADIENT.primarySoft,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            padding: '10px 28px',
            width: '406px',
            borderRadius: '999px',
            cursor: isDisabled ? 'not-allowed' : 'pointer',
            opacity: isDisabled ? 0.5 : 1,
            transition: 'opacity 0.2s, background 0.2s',
            flexShrink: 0,
          }}
          onMouseOver={(e) => { if (!isDisabled) e.currentTarget.style.background = GRADIENT.primaryHover; }}
          onMouseOut={(e) => { e.currentTarget.style.background = isDisabled ? GRADIENT.primarySoft : GRADIENT.primarySoft; e.currentTarget.style.boxShadow = 'none'; }}
          onMouseDown={(e) => { if (!isDisabled) { e.currentTarget.style.background = GRADIENT.primaryActive; e.currentTarget.style.boxShadow = GRADIENT_ACTIVE_SHADOW; } }}
          onMouseUp={(e) => { if (!isDisabled) { e.currentTarget.style.background = GRADIENT.primaryHover; e.currentTarget.style.boxShadow = 'none'; } }}
        >
          {survey.isSubmitting ? (
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg"
              style={{ animation: 'spin 1s linear infinite' }}>
              <circle cx="9" cy="9" r="7" stroke="#fff" strokeWidth="2" strokeDasharray="32" strokeDashoffset="10" strokeLinecap="round" />
            </svg>
          ) : survey.isLastStep ? '제출하기' : '다음'}
        </button>
      </div>
    </div>
  );
}

export default SurveyForm;