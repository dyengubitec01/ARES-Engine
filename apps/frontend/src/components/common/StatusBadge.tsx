// created by ARES team [2026-03-25]
import { useState, useRef, useEffect } from 'react';

const TOOLTIP_BG = 'var(--color-grayscale-700)';
const TOOLTIP_COLOR = 'var(--color-primary-600-50, #FAFBFF)';

interface StatusBadgeProps {
  label: string;
  bg: string;
  color: string;
  border?: string;
  borderRadius?: string;
  icon?: string;
  iconFilter?: string;
  tooltip?: string;
  hoverLabel?: string;
  hoverBg?: string;
  hoverColor?: string;
  hoverBorder?: string;
  onHoverAction?: () => void;
}

function StatusBadge({
  label, bg, color, border, borderRadius = '999px',
  icon, iconFilter, tooltip,
  hoverLabel, hoverBg, hoverColor, hoverBorder, onHoverAction,
}: StatusBadgeProps) {
  const [isHovered, setIsHovered] = useState(false);
  const badgeRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLSpanElement>(null);
  const [tooltipPos, setTooltipPos] = useState<{ top: number; left: number; above: boolean } | null>(null);

  const showButton = isHovered && hoverLabel;

  useEffect(() => {
    if (!isHovered || !tooltip || !badgeRef.current) {
      setTooltipPos(null);
      return;
    }
    const rect = badgeRef.current.getBoundingClientRect();

    // 스크롤 가능한 부모 컨테이너의 하단을 기준으로 판단
    let scrollParent = badgeRef.current.parentElement;
    while (scrollParent) {
      const style = getComputedStyle(scrollParent);
      if (style.overflowY === 'auto' || style.overflowY === 'scroll') break;
      scrollParent = scrollParent.parentElement;
    }
    const bottomBoundary = scrollParent
      ? scrollParent.getBoundingClientRect().bottom
      : window.innerHeight;
    const spaceBelow = bottomBoundary - rect.bottom;
    const above = spaceBelow < 60;
    setTooltipPos({
      top: above ? rect.top : rect.bottom + 8,
      left: rect.left,
      above,
    });
  }, [isHovered, tooltip]);

  return (
    <span
      ref={badgeRef}
      style={{
        width: '65px',
        height: '24px',
        padding: '0',
        backgroundColor: showButton ? (hoverBg || bg) : bg,
        color: showButton ? (hoverColor || color) : color,
        borderRadius,
        fontSize: '11px',
        fontWeight: '500',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '4px',
        boxSizing: 'border-box' as const,
        border: showButton ? (hoverBorder || border || 'none') : (border || 'none'),
        whiteSpace: 'nowrap',
        position: 'relative',
        cursor: (tooltip || hoverLabel) ? 'pointer' : 'default',
        transition: 'background-color 0.2s, color 0.2s, border 0.2s',
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => { if (showButton && onHoverAction) onHoverAction(); }}
    >
      {icon && !showButton && <img src={icon} alt="" style={{ width: '14px', height: '14px', ...(iconFilter ? { filter: iconFilter } : {}) }} />}
      {showButton ? hoverLabel : label}
      {tooltip && isHovered && tooltipPos && (
        <span
          ref={tooltipRef}
          style={{
            position: 'fixed',
            top: tooltipPos.above ? undefined : `${tooltipPos.top}px`,
            bottom: tooltipPos.above ? `${window.innerHeight - tooltipPos.top + 8}px` : undefined,
            left: `${tooltipPos.left}px`,
            display: 'flex',
            padding: '8px 12px',
            justifyContent: 'center',
            alignItems: 'center',
            borderRadius: '8px',
            background: TOOLTIP_BG,
            color: TOOLTIP_COLOR,
            fontSize: '13px',
            fontWeight: '500',
            lineHeight: '20px',
            letterSpacing: '-0.26px',
            
            whiteSpace: 'nowrap',
            zIndex: 10000,
            pointerEvents: 'none',
          }}>
          {tooltip}
          {/* 화살표 */}
          <span style={{
            position: 'absolute',
            left: '16px',
            width: 0,
            height: 0,
            borderLeft: '6px solid transparent',
            borderRight: '6px solid transparent',
            ...(tooltipPos.above
              ? { top: '100%', borderTop: `6px solid ${TOOLTIP_BG}` }
              : { bottom: '100%', borderBottom: `6px solid ${TOOLTIP_BG}` }),
          }} />
        </span>
      )}
    </span>
  );
}

export default StatusBadge;
