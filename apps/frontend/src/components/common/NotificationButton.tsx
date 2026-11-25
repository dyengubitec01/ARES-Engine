// created by ARES team [2026-04-22]
import { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import NotificationIcon from '../../assets/sidebar/notification.svg?react';
import { toastFailedIcon } from '../../assets/icons';
import type { AlarmItem } from '../../services/alarm.service';

interface NotificationButtonProps {
  notificationCount?: number;
  alarmItems?: AlarmItem[];
  alarmError?: string | null;
  clearAlarmError?: () => void;
  onReadAllAlarms?: () => void;
  onReadAlarm?: (alarmId: string) => Promise<void> | void;
  onDeleteAlarm?: (alarmId: string) => void;
  onNotificationClick?: () => void;
}

function NotificationButton({
  notificationCount = 0,
  alarmItems = [],
  alarmError = null,
  clearAlarmError,
  onReadAllAlarms,
  onReadAlarm,
  onDeleteAlarm,
  onNotificationClick,
}: NotificationButtonProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [showFade, setShowFade] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const portalRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const positionRef = useRef<{ top: number; left: number }>({ top: 0, left: 0 });

  const checkScrollFade = useCallback(() => {
    const el = listRef.current;
    if (!el) { setShowFade(false); return; }
    const hasMoreBelow = el.scrollHeight - el.scrollTop - el.clientHeight > 1;
    setShowFade(hasMoreBelow);
  }, []);

  useEffect(() => {
    if (isOpen) {
      requestAnimationFrame(() => checkScrollFade());
    } else {
      clearAlarmError?.();
    }
  }, [alarmItems, isOpen, checkScrollFade, clearAlarmError]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent): void => {
      if (
        buttonRef.current && !buttonRef.current.contains(event.target as Node) &&
        (!portalRef.current || !portalRef.current.contains(event.target as Node))
      ) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen]);

  useEffect(() => {
    const handleResize = (): void => {
      if (isOpen) setIsOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [isOpen]);

  const handleClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    if (!isOpen && buttonRef.current) {
      const rect = buttonRef.current.getBoundingClientRect();
      positionRef.current = { top: rect.bottom + 4, left: rect.left };
    }
    setIsOpen(prev => !prev);
    onNotificationClick?.();
    if (!isOpen) {
      requestAnimationFrame(() => checkScrollFade());
    }
  }, [isOpen, onNotificationClick, checkScrollFade]);

  const formatTime = (dateStr: string): string => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    const diffHour = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);

    if (diffMin < 1) return '방금 전';
    if (diffMin < 60) return `${diffMin}분 전`;
    if (diffHour < 24) return `${diffHour}시간 전`;
    if (diffDay < 7) return `${diffDay}일 전`;
    return `${date.getMonth() + 1}/${date.getDate()}`;
  };

  const renderDropdown = () => (
    <div ref={portalRef} style={{
      position: 'fixed',
      top: `${positionRef.current.top}px`,
      left: `${positionRef.current.left}px`,
      backgroundColor: 'var(--menu-bg)',
      border: '1px solid var(--menu-border)',
      borderRadius: '8px',
      boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
      zIndex: 10000,
      width: '280px',
    }}>
      <div style={{
        maxHeight: '360px',
        display: 'flex',
        flexDirection: 'column',
      }}>
        {alarmError && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 12px 0',
            color: 'var(--color-error-500)',
            fontSize: '13px',
            fontWeight: 500,
            lineHeight: '20px',
            letterSpacing: '-0.26px',
            flexShrink: 0,
          }}>
            <img src={toastFailedIcon} alt="" style={{ width: '14px', height: '14px', flexShrink: 0 }} />
            <span>{alarmError}</span>
          </div>
        )}
        <div style={{
          padding: '8px 12px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          flexShrink: 0,
        }}>
          <button
            onClick={(e) => { e.stopPropagation(); onReadAllAlarms?.(); }}
            style={{
              padding: '4px 8px',
              backgroundColor: 'transparent',
              border: 'none',
              cursor: 'pointer',
              fontSize: '11px',
              fontWeight: '400',
              color: 'var(--color-grayscale-400)',
              transition: 'all 0.2s',
            }}
            onMouseOver={(e) => { e.currentTarget.style.color = 'var(--color-primary-600)'; }}
            onMouseOut={(e) => { e.currentTarget.style.color = 'var(--color-grayscale-400)'; }}
          >
            모두 읽음 처리
          </button>
        </div>

        <div style={{ position: 'relative', flex: 1, minHeight: 0 }}>
          <div
            ref={listRef}
            onScroll={checkScrollFade}
            style={{
              maxHeight: '264px',
              overflowY: 'auto',
              padding: '4px',
            }}
          >
            {alarmItems.length === 0 ? (
              <div style={{
                padding: '24px 12px',
                textAlign: 'center',
                fontSize: '13px',
                color: 'var(--color-grayscale-400)',
              }}>
                알림이 없습니다
              </div>
            ) : (
              alarmItems.map((item) => (
                <div
                  key={item.id}
                  style={{
                    padding: '10px 12px',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    backgroundColor: 'transparent',
                    display: 'flex',
                    alignItems: 'flex-start',
                    gap: '8px',
                  }}
                  onClick={async () => {
                    setIsOpen(false);
                    try {
                      await onReadAlarm?.(item.id);
                    } catch {
                      // 읽음 처리 실패 시 패널 다시 열기 (에러는 alarmError로 표시됨)
                      if (buttonRef.current) {
                        const rect = buttonRef.current.getBoundingClientRect();
                        positionRef.current = { top: rect.bottom + 4, left: rect.left };
                      }
                      setIsOpen(true);
                    }
                  }}
                  onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100)'; }}
                  onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                >
                  <div style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    backgroundColor: item.isRead === 'N' ? 'var(--color-primary-600)' : 'transparent',
                    flexShrink: 0,
                    marginTop: '6px',
                  }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontSize: '13px',
                      fontWeight: item.isRead === 'N' ? '500' : '400',
                      color: 'var(--color-grayscale-900)',
                      lineHeight: '1.4',
                      wordBreak: 'break-word',
                    }}>
                      {item.message}
                    </div>
                    <div style={{
                      fontSize: '11px',
                      color: 'var(--color-grayscale-400)',
                      marginTop: '4px',
                    }}>
                      {formatTime(item.createdAt)}
                    </div>
                  </div>
                  <button
                    onClick={(e) => { e.stopPropagation(); onDeleteAlarm?.(item.id); }}
                    style={{
                      padding: '2px',
                      backgroundColor: 'transparent',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '14px',
                      lineHeight: '1',
                      color: 'var(--color-grayscale-400)',
                      flexShrink: 0,
                      transition: 'color 0.2s',
                    }}
                    onMouseOver={(e) => { e.currentTarget.style.color = 'var(--color-grayscale-900)'; }}
                    onMouseOut={(e) => { e.currentTarget.style.color = 'var(--color-grayscale-400)'; }}
                  >
                    ✕
                  </button>
                </div>
              ))
            )}
          </div>
          {showFade && (
            <div style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              right: 0,
              height: '32px',
              background: 'linear-gradient(transparent, var(--color-grayscale-50))',
              pointerEvents: 'none',
              borderRadius: '0 0 8px 8px',
            }} />
          )}
        </div>
      </div>
    </div>
  );

  return (
    <>
      <button
        ref={buttonRef}
        onClick={handleClick}
        aria-label="알림"
        style={{
          width: '40px',
          height: '40px',
          padding: '10px',
          backgroundColor: 'transparent',
          border: 'none',
          borderRadius: '6px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'background-color 0.2s',
          position: 'relative',
          flexShrink: 0,
        }}
        onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'var(--color-grayscale-150)'; }}
        onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
      >
        <NotificationIcon width={24} height={24} style={{ color: 'var(--color-grayscale-500)' }} />
        {notificationCount > 0 && (
          <span style={{
            position: 'absolute',
            top: '6px',
            right: '6px',
            minWidth: '14px',
            height: '14px',
            padding: '0 3px',
            backgroundColor: 'var(--color-primary-600)',
            borderRadius: '999px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '5.895px',
            fontWeight: '500',
            lineHeight: 'normal',
            letterSpacing: '-0.118px',
            color: 'var(--color-grayscale-100)',
          }}>
            {notificationCount > 99 ? '99+' : notificationCount}
          </span>
        )}
      </button>
      {isOpen && createPortal(renderDropdown(), document.body)}
    </>
  );
}

export default NotificationButton;
