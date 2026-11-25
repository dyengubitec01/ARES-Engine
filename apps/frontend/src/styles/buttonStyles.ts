// created by ARES team [2026-03-31]
import type { MouseEvent } from 'react';

// 그라데이션 버튼은 테마 전환과 무관하게 동일한 보라색 계열을 유지한다 (라이트/다크 동일).
export const GRADIENT = {
  primary:
    'linear-gradient(127deg, #B4BDFA 0%, #626BF7 57.21%, #424CD3 95.67%)',
  primarySoft:
    'linear-gradient(127deg, #B4BDFA 0%, #626BF7 57.21%, #626BF7 95.67%)',
  primaryHover:
    'linear-gradient(127deg, #FFFFFF 0%, #626BF7 57.21%, #404AE6 100%)',
  primaryActive:
    'linear-gradient(127deg, #FFFFFF 0%, #626BF7 57.21%, #404AE6 100%)',
} as const;

export const GRADIENT_ACTIVE_SHADOW = '0 2px 4px 0 rgba(0, 0, 0, 0.08), 0 4px 8px 0 rgba(0, 0, 0, 0.12)';

export const gradientButtonBase = {
  border: 'none',
  cursor: 'pointer',
  fontWeight: '600',
  fontSize: '16px',
  color: 'white',
  transition: 'all 0.2s',
} as const;

// 회색 보더의 보조 버튼(닫기, 이전, 목록으로 돌아가기 등)
export const secondaryButtonStyle = {
  flex: 1,
  padding: '10px 28px',
  backgroundColor: 'var(--color-grayscale-50)',
  color: 'var(--color-grayscale-400, #8E8E8E)',
  border: '1px solid var(--color-grayscale-300)',
  borderRadius: '999px',
  fontSize: '16px',
  fontStyle: 'normal' as const,
  fontWeight: 600,
  lineHeight: '26px',
  letterSpacing: '-0.32px',
  cursor: 'pointer',
  transition: 'background-color 0.2s',
};

export const secondaryButtonHoverHandlers = {
  onMouseOver: (e: MouseEvent<HTMLButtonElement>) => {
    e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100)';
  },
  onMouseOut: (e: MouseEvent<HTMLButtonElement>) => {
    e.currentTarget.style.backgroundColor = 'var(--color-grayscale-50)';
  },
};

// 그라디언트 버튼용 호버 핸들러 묶음 - disabled 인자에 따라 효과 적용 여부 결정
export const buildGradientHoverHandlers = (disabled: boolean) => ({
  onMouseOver: (e: MouseEvent<HTMLButtonElement>) => {
    if (!disabled) e.currentTarget.style.background = GRADIENT.primaryHover;
  },
  onMouseOut: (e: MouseEvent<HTMLButtonElement>) => {
    e.currentTarget.style.background = GRADIENT.primarySoft;
    e.currentTarget.style.boxShadow = 'none';
  },
  onMouseDown: (e: MouseEvent<HTMLButtonElement>) => {
    if (!disabled) {
      e.currentTarget.style.background = GRADIENT.primaryActive;
      e.currentTarget.style.boxShadow = GRADIENT_ACTIVE_SHADOW;
    }
  },
  onMouseUp: (e: MouseEvent<HTMLButtonElement>) => {
    if (!disabled) {
      e.currentTarget.style.background = GRADIENT.primaryHover;
      e.currentTarget.style.boxShadow = 'none';
    }
  },
});
