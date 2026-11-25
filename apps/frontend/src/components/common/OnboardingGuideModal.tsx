// created by ARES team [2026-05-27]
import { useState, useEffect } from 'react';
import { useAuth } from '../../features/auth/AuthContext';

const STORAGE_KEY = 'onboarding_guide_dismissed_v1';

interface OnboardingStep {
  mediaSrc: string;
  title: string;
  description: string;
  caution?: string;
}

const COMMON_STEPS_BEFORE: OnboardingStep[] = [
  // STEP-1
  {
    mediaSrc: '/onboarding/step1.gif',
    title: '문서함에 업무 문서를 관리하세요',
    description: '업로드한 문서를 한곳에서 확인하고\n필요한 문서는 AI 지식으로 추가 요청할 수 있어요.',
  },
  // STEP-2
  {
    mediaSrc: '/onboarding/step2.gif',
    title: '문서를 업로드해 보세요',
    description: 'AI가 참고할 수 있는 업무 문서를 문서함에 직접 업로드할 수 있어요. 파일명 규칙에 맞추면 검색 정확도가 높아져요.',
    caution: '권장 파일명 : (구분)_사업명_수행일.확장자 형식 권장\n※ 같은 파일의 경우 중복으로 처리되어 등록 불가',
  },
  // STEP-3
  {
    mediaSrc: '/onboarding/step3.gif',
    title: 'AI 지식으로 추가 요청하세요',
    description: '업로드한 문서를 선택한 뒤 요청하면,\n승인 후 AI 답변에 활용될 수 있어요.',
    caution: '승인 완료 전까지는 문서가 답변에 반영되지 않아요.',
  },
  // STEP-4
  {
    mediaSrc: '/onboarding/step4.gif',
    title: '문서 처리 상태를 확인하세요',
    description: '업로드, 처리 중, 완료, 오류 상태를\n문서 목록에서 바로 확인할 수 있어요.',
    caution: '오류 문서는 사유 확인 후 재요청 또는 오류신고 할 수 있어요.',
  },
  // STEP-5
  {
    mediaSrc: '/onboarding/step5.gif',
    title: '답변에 활용할 문서를 선택하세요',
    description: 'AI 지식으로 추가된 문서는 활용 여부를 켜고 끌 수 있어요.\nOFF 설정 시 해당 문서는 AI 검색 대상에서 제외돼요.',
    caution: '오래된 자료나 수정 중인 문서를 OFF로 두면,\nAI가 잘못된 정보로 답변하는 것을 막을 수 있어요.',
  },
];

// STEP-6 고급 사용자 전용
const ADVANCED_ONLY_STEP: OnboardingStep = {
  mediaSrc: '/onboarding/step6.gif',
  title: 'AI 지식 추가 요청을 승인하세요',
  description: '승인권자는 요청된 문서를 확인하고,\n개별 승인·일괄 승인·반려할 수 있어요.',
  caution: '승인권자에게만 노출되는 추가 안내입니다.',
};

const COMMON_STEP_LAST: OnboardingStep = {
  mediaSrc: '/onboarding/step7.svg',
  title: '이제 문서함을 자유롭게 이용해보세요',
  description: '오류/개선 사항이 있다면\n좌측 상단의 [피드백 보내기]로 알려주세요.',
  caution: '가이드는 [문서 보관함] → [도움말]에서 다시 볼 수 있습니다.',
};

interface OnboardingGuideModalProps {
  isOpen?: boolean;
  onClose?: () => void;
}

function OnboardingGuideModal({ isOpen: controlledOpen, onClose }: OnboardingGuideModalProps = {}) {
  const { isAdmin, isEmbedding } = useAuth();
  const isAdvancedUser = isAdmin || isEmbedding;

  const steps = isAdvancedUser
    ? [...COMMON_STEPS_BEFORE, ADVANCED_ONLY_STEP, COMMON_STEP_LAST]
    : [...COMMON_STEPS_BEFORE, COMMON_STEP_LAST];

  const [autoOpen, setAutoOpen] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);

  const isOpen = controlledOpen ?? autoOpen;

  const totalSteps = steps.length;
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === totalSteps - 1;
  const step = steps[currentStep];

  useEffect(() => {
    if (localStorage.getItem(STORAGE_KEY) === 'true') return;
    setAutoOpen(true);
  }, []);

  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
      setCurrentStep(0);
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  const close = () => {
    setAutoOpen(false);
    onClose?.();
  };

  const handleNext = () => {
    if (isLastStep) {
      localStorage.setItem(STORAGE_KEY, 'true');
      close();
    } else {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handlePrev = () => {
    setCurrentStep((prev) => Math.max(0, prev - 1));
  };

  const handleSkip = () => {
    close();
  };

  const handleDismissForever = () => {
    localStorage.setItem(STORAGE_KEY, 'true');
    close();
  };

  const handleDotClick = (index: number) => {
    setCurrentStep(index);
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
        padding: '20px',
      }}
    >
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          width: '500px',
          height: '600px',
          padding: '38px 36px 32px 36px',
          gap: '24px',
          borderRadius: '28px',
          background: 'var(--color-grayscale-50)',
          boxShadow: '0 20px 44px 0 rgba(0, 0, 0, 0.18)',
          animation: 'modalFadeIn 0.2s ease-out',
          boxSizing: 'border-box',
        }}
      >
        {/* 이미지 */}
        <div
          style={{
            alignSelf: 'stretch',
            flexShrink: 0,
            height: '220px',
            aspectRatio: '107 / 55',
            borderRadius: '24px',
            background: 'var(--color-grayscale-100)',
            overflow: 'hidden',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <img
            src={step.mediaSrc}
            alt=""
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'cover',
              display: 'block',
            }}
            onError={(e) => {
              (e.currentTarget as HTMLImageElement).style.display = 'none';
            }}
          />
        </div>

        {/* 제목 */}
        <div
          style={{
            alignSelf: 'stretch',
            color: 'var(--color-grayscale-900)',
            fontSize: '28px',
            fontStyle: 'normal',
            fontWeight: 700,
            lineHeight: '34px',
            letterSpacing: '-0.56px',
            textAlign: 'left',
          }}
        >
          {step.title}
        </div>

        {/* 내용 + 주의사항 (gap 10px) */}
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'stretch',
            gap: '10px',
            alignSelf: 'stretch',
            marginTop: '-8px',
          }}
        >
          <div
            style={{
              color: 'var(--color-grayscale-600)',
              fontSize: '18px',
              fontStyle: 'normal',
              fontWeight: 400,
              lineHeight: '26px',
              letterSpacing: '-0.36px',
              textAlign: 'left',
              whiteSpace: 'pre-line',
            }}
          >
            {step.description}
          </div>
          {step.caution && (
            <div
              style={{
                minHeight: '40px',
                color: 'var(--color-primary-600)',
                fontSize: '14px',
                fontStyle: 'normal',
                fontWeight: 500,
                lineHeight: '20px',
                letterSpacing: '-0.28px',
                textAlign: 'left',
                whiteSpace: 'pre-line',
              }}
            >
              {step.caution}
            </div>
          )}
        </div>

        {/* 구분선 (step 2부터) */}
        {!isFirstStep && (
          <div
            style={{
              alignSelf: 'stretch',
              flexShrink: 0,
              height: '1px',
              background: 'var(--color-grayscale-150)',
              marginTop: 'auto',
            }}
          />
        )}

        {/* 점 + Skip — 점은 모달 가운데, Skip은 점에서 우측 136px */}
        <div
          style={{
            position: 'relative',
            alignSelf: 'stretch',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            marginTop: isFirstStep ? 'auto' : 0,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {steps.map((_, i) => (
              <button
                key={i}
                type="button"
                onClick={() => handleDotClick(i)}
                aria-label={`${i + 1}번째 스텝으로 이동`}
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  border: 'none',
                  padding: 0,
                  background:
                    i === currentStep
                      ? 'var(--color-primary-500)'
                      : 'var(--color-grayscale-150)',
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
              />
            ))}
          </div>
          <button
            type="button"
            onClick={handleSkip}
            style={{
              position: 'absolute',
              top: '50%',
              right: 0,
              transform: 'translateY(-50%)',
              display: 'flex',
              padding: '2px 10px',
              justifyContent: 'center',
              alignItems: 'center',
              background: 'transparent',
              border: 'none',
              color: 'var(--color-grayscale-300)',
              fontSize: '13px',
              fontStyle: 'normal',
              fontWeight: 500,
              lineHeight: '20px',
              letterSpacing: '-0.26px',
              cursor: 'pointer',
            }}
          >
            Skip
          </button>
        </div>

        {/* 다시 보지 않기 + 이전/다음 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            alignSelf: 'stretch',
          }}
        >
          <button
            type="button"
            onClick={handleDismissForever}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--color-grayscale-300)',
              fontSize: '16px',
              fontStyle: 'normal',
              fontWeight: 600,
              lineHeight: '26px',
              letterSpacing: '-0.32px',
              cursor: 'pointer',
              padding: 0,
            }}
          >
            다시 보지 않기
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
            {!isFirstStep && (
              <button
                type="button"
                onClick={handlePrev}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: 'var(--color-grayscale-400)',
                  fontSize: '16px',
                  fontStyle: 'normal',
                  fontWeight: 600,
                  lineHeight: '26px',
                  letterSpacing: '-0.32px',
                  cursor: 'pointer',
                  padding: 0,
                }}
              >
                이전
              </button>
            )}
            <button
              type="button"
              onClick={handleNext}
              style={{
                display: 'flex',
                width: '126px',
                padding: '11px 12px',
                justifyContent: 'center',
                alignItems: 'center',
                gap: '10px',
                background: 'var(--color-primary-600)',
                color: '#FFF',
                border: 'none',
                borderRadius: '999px',
                fontSize: '16px',
                fontStyle: 'normal',
                fontWeight: 600,
                lineHeight: '26px',
                letterSpacing: '-0.32px',
                cursor: 'pointer',
              }}
            >
              {isLastStep ? '시작하기' : '다음'}
            </button>
          </div>
        </div>
      </div>

      <style>
        {`
          @keyframes modalFadeIn {
            from {
              opacity: 0;
              transform: scale(0.95) translateY(-10px);
            }
            to {
              opacity: 1;
              transform: scale(1) translateY(0);
            }
          }
        `}
      </style>
    </div>
  );
}

export default OnboardingGuideModal;
