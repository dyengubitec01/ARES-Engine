// created by ARES team [2026-04-15]
// 채팅 피드백 액션용 토스트 (복사, 좋아요, 싫어요)

import { useEffect, useState } from 'react';

interface ActionToastProps {
  message: string;
  visible: boolean;
  duration?: number;
  onClose: () => void;
}

const ActionToast = ({ message, visible, duration = 2000, onClose }: ActionToastProps) => {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!visible) {
      setShow(false);
      return;
    }
    setShow(true);
    const timer = setTimeout(() => {
      setShow(false);
      setTimeout(onClose, 300);
    }, duration);
    return () => clearTimeout(timer);
  }, [visible, duration, onClose]);

  if (!visible) return null;

  return (
    <div style={{
      opacity: show ? 1 : 0,
      transition: 'opacity 0.3s ease',
      padding: '12px 16px',
      borderRadius: '4px',
      background: 'var(--color-grayscale-50, #FFF)',
      color: 'var(--color-grayscale-600, #58595D)',
      fontSize: '13px',
      fontWeight: '600',
      lineHeight: '16px',
      letterSpacing: '-0.26px',
      whiteSpace: 'nowrap',
      width: 'fit-content',
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
    }}>
      {message}
    </div>
  );
};

export default ActionToast;
