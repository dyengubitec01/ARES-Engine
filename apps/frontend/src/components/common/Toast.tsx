// created by ARES team [2026-04-10]
// refactored: unified Toast component [2026-04-14]

import { useEffect, useState } from 'react';
import { toastSuccessIcon, toastFailedIcon, toastWarningIcon } from '../../assets/icons';

type ToastVariant = 'success' | 'error' | 'warning';

interface ToastItem {
  id: string;
  title?: string;
  message: string;
}

interface ToastProps {
  variant: ToastVariant;
  items: ToastItem[];
  duration?: number;
  onClose?: (id: string) => void;
}

const TOAST_CONFIG: Record<ToastVariant, {
  icon: string;
  progressColor: string;
  gradient: string;
  defaultTitle: string;
  defaultMessage: string;
}> = {
  success: {
    icon: toastSuccessIcon,
    progressColor: 'var(--color-success-300, #6ED4A3)',
    gradient: 'radial-gradient(circle at 28px 50%, #6ED4A340 0%, #6ED4A300 25%)',
    defaultTitle: '',
    defaultMessage: '완료되었습니다.',
  },
  error: {
    icon: toastFailedIcon,
    progressColor: 'var(--color-error-400, #F87070)',
    gradient: 'radial-gradient(circle at 28px 50%, #F0424840 0%, #F0424800 25%)',
    defaultTitle: '지금은 처리할 수 없습니다.',
    defaultMessage: '문제가 발생했습니다.',
  },
  warning: {
    icon: toastWarningIcon,
    progressColor: 'var(--color-warning-400, #FFBF7A)',
    gradient: 'radial-gradient(circle at 28px 50%, #FFD42640 0%, #FFD42600 25%)',
    defaultTitle: '업로드 오류',
    defaultMessage: '문제가 발생했습니다.',
  },
};

const Toast = ({ variant, items, duration = 3000, onClose }: ToastProps): JSX.Element | null => {
  const [visibleIds, setVisibleIds] = useState<Set<string>>(new Set(items.map(i => i.id)));
  const config = TOAST_CONFIG[variant];

  useEffect(() => {
    const newIds = items.filter(i => !visibleIds.has(i.id)).map(i => i.id);
    if (newIds.length > 0) {
      setVisibleIds(prev => {
        const next = new Set(prev);
        newIds.forEach(id => next.add(id));
        return next;
      });
    }
    // items 변경시만 실행 의도 - visibleIds는 setVisibleIds(prev=>) 콜백으로 안전 처리
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items]);

  useEffect(() => {
    const timers = items.map(item =>
      setTimeout(() => {
        setVisibleIds(prev => {
          const next = new Set(prev);
          next.delete(item.id);
          return next;
        });
        onClose?.(item.id);
      }, duration)
    );
    return () => timers.forEach(clearTimeout);
  }, [items, duration, onClose]);

  const visibleItems = items.filter(i => visibleIds.has(i.id));
  if (visibleItems.length === 0) return null;

  return (
    <div style={{
      position: 'fixed',
      top: '20px',
      right: '40px',
      zIndex: 1000,
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
    }}>
      {visibleItems.map((item) => {
        const title = item.title ?? config.defaultTitle;
        const message = item.message || config.defaultMessage;

        return (
          <div key={item.id} style={{
            width: '340px',
            borderRadius: '8px',
            background: `${config.gradient}, var(--color-grayscale-50, #FFF)`,
            boxShadow: '0 16px 24px 0 rgba(0, 0, 0, 0.05), 0 2px 30px 0 rgba(0, 0, 0, 0.05), 0 8px 10px 0 rgba(0, 0, 0, 0.04)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}>
            <div style={{
              padding: '12px 16px',
              display: 'flex',
              flexDirection: 'row',
              alignItems: 'center',
              gap: '10px',
            }}>
              <img src={config.icon} alt="" width={24} height={24} />
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
              }}>
                {title && (
                  <span style={{
                    color: 'var(--color-grayscale-600, #58595D)',

                    fontSize: '13px',
                    fontWeight: '600',
                    lineHeight: '16px',
                    letterSpacing: '-0.26px',
                    
                  }}>
                    {title}
                  </span>
                )}
                <span style={{
                  color: title
                    ? 'var(--color-grayscale-500, #757578)'
                    : 'var(--color-grayscale-600, #58595D)',

                  fontSize: title ? '11px' : '13px',
                  fontWeight: title ? '500' : '600',
                  lineHeight: title ? '14px' : '16px',
                  letterSpacing: title ? undefined : '-0.26px',
                }}>
                  {message}
                </span>
              </div>
            </div>
            <div style={{
              width: '100%',
              height: '4px',
              background: 'transparent',
            }}>
              <div style={{
                width: '100%',
                height: '100%',
                background: config.progressColor,
                borderRadius: '0 0 8px 8px',
                animation: `toastShrink ${duration}ms linear forwards`,
              }} />
            </div>
          </div>
        );
      })}
      <style>{`
        @keyframes toastShrink {
          from { width: 100%; }
          to { width: 0%; }
        }
      `}</style>
    </div>
  );
};

export type { ToastItem, ToastVariant };
export default Toast;
