// created by ARES team [2026-03-17]
import { useEffect, type ReactNode } from 'react';
import { GRADIENT } from '../../styles/buttonStyles';

interface CustomModalProps {
  isOpen: boolean;
  type: 'alert' | 'confirm';
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel?: () => void;
  confirmText?: string;
  cancelText?: string;
  confirmColor?: string;
  width?: string;
  titleIcon?: string;
  titleGap?: string;
  children?: ReactNode;
  confirmDisabled?: boolean;
}

function CustomModal({
  isOpen,
  type,
  title,
  message,
  onConfirm,
  onCancel,
  confirmText = '삭제',
  cancelText = '아니오',
  confirmColor = GRADIENT.primarySoft,
  width,
  titleIcon,
  titleGap,
  children,
  confirmDisabled = false,
}: CustomModalProps) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleOverlayClick = () => {
    // 모달 바깥 클릭 시 닫히지 않도록 처리
  };

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
        padding: '20px'
      }}
      onClick={handleOverlayClick}
    >
      <div
        style={{
          position: 'relative',
          backgroundColor: 'var(--color-grayscale-50, #FFF)',
          borderRadius: '16px',
          boxShadow: 'var(--shadow-modal)',
          maxWidth: width || '450px',
          width: '100%',
          padding: '40px',
          animation: 'modalFadeIn 0.2s ease-out'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* 제목 */}
        <div
          style={{
            fontSize: '24px',
            fontWeight: '600',
            color: 'var(--color-grayscale-900)',
            marginBottom: titleGap || '10px',
            textAlign: 'center',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '8px',
          }}
        >
          {titleIcon && <img src={titleIcon} alt="" style={{ width: '28px', height: '28px' }} />}
          {title}
        </div>

        {/* 메시지 */}
        <div
          style={{
            fontSize: '16px',
            fontWeight: '400',
            color: 'var(--color-grayscale-400)',
            lineHeight: '1.6',
            textAlign: 'center',
            marginBottom: children ? '20px' : '36px',
            whiteSpace: 'pre-wrap',
          }}
        >
          {message}
        </div>

        {/* 커스텀 콘텐츠 */}
        {children && (
          <div style={{ marginBottom: '24px' }}>
            {children}
          </div>
        )}

        {/* 버튼 영역 */}
        <div
          style={{
            display: 'flex',
            gap: '8px',
            justifyContent: 'center'
          }}
        >
          {type === 'confirm' && onCancel && (
            <button
              onClick={onCancel}
              style={{
                flex: 1,
                height: '48px',
                padding: '0 24px',
                backgroundColor: 'var(--color-grayscale-50, #FFF)',
                color: 'var(--color-grayscale-400, #8E8E8E)',
                border: '1px solid var(--color-grayscale-200, #B9B9B9)',
                borderRadius: '999px',

                fontSize: '16px',
                fontWeight: '600',
                lineHeight: '26px',
                letterSpacing: '-0.32px',
                
                cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseOver={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100)';
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-grayscale-50, #FFF)';
              }}
            >
              {cancelText}
            </button>
          )}

          <button
            onClick={onConfirm}
            disabled={confirmDisabled}
            style={{
              flex: 1,
              height: '48px',
              padding: '11px 20px',
              background: confirmColor,
              color: '#FFF',
              border: 'none',
              borderRadius: '999px',
              fontSize: '16px',
              fontWeight: '600',
              lineHeight: '26px',
              letterSpacing: '-0.32px',
              
              cursor: confirmDisabled ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s',
              opacity: confirmDisabled ? 0.5 : 1,
            }}
            onMouseOver={(e) => {
              if (!confirmDisabled) e.currentTarget.style.opacity = '0.9';
            }}
            onMouseOut={(e) => {
              if (!confirmDisabled) e.currentTarget.style.opacity = '1';
            }}
          >
            {confirmText}
          </button>
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

export default CustomModal;
