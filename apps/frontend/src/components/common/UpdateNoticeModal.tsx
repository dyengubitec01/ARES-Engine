// created by ARES team [2026-03-27]
import { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { notificationColorIcon } from '../../assets/icons';


interface NoticeItem {
  title: string;
  description: string;
  updatedAt?: string;
  isNew?: boolean;
}

interface NoticeData {
  id: string;
  title?: string;
  items: NoticeItem[];
}

const STORAGE_KEY = 'update_notice_dismissed';

function UpdateNoticeModal() {
  const [isOpen, setIsOpen] = useState(false);
  const [notice, setNotice] = useState<NoticeData | null>(null);
  const [showFade, setShowFade] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const location = useLocation();

  const checkScrollFade = useCallback(() => {
    const el = listRef.current;
    if (!el) { setShowFade(false); return; }
    const hasMoreBelow = el.scrollHeight - el.scrollTop - el.clientHeight > 1;
    setShowFade(hasMoreBelow);
  }, []);

  useEffect(() => {
    fetch('/notice.json')
      .then(res => {
        if (!res.ok) throw new Error('not found');
        return res.json();
      })
      .then((data: NoticeData) => {
        if (!data.id || !data.items?.length) return;

        // "오늘 하루 보지 않기" 체크
        const dismissed = localStorage.getItem(STORAGE_KEY);
        if (dismissed) {
          try {
            const { id, expiry } = JSON.parse(dismissed);
            if (id === data.id && new Date().getTime() < expiry) return;
          } catch {
            // 파싱 실패 시 무시
          }
        }

        setNotice(data);
        setIsOpen(true);
      })
      .catch(() => {
        // notice.json이 없으면 모달 미표시
      });
  }, [location.pathname]);

  const handleClose = () => {
    setIsOpen(false);
  };

  const handleDismissToday = () => {
    if (notice) {
      const now = new Date();
      const endOfDay = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59, 999);
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        id: notice.id,
        expiry: endOfDay.getTime(),
      }));
    }
    setIsOpen(false);
  };

  useEffect(() => {
    if (isOpen) {
      requestAnimationFrame(() => checkScrollFade());
    }
  }, [isOpen, checkScrollFade]);

  if (!isOpen || !notice) return null;

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
      }}
    >
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
        {/* 모달 본체 */}
        <div
          style={{
            position: 'relative',
            backgroundColor: 'var(--color-grayscale-50)',
            borderRadius: '16px',
            boxShadow: 'var(--shadow-modal)',
            width: '450px',
            maxHeight: '600px',
            display: 'flex',
            flexDirection: 'column',
            animation: 'modalFadeIn 0.2s ease-out',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* 헤더 */}
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            padding: '40px 32px 24px',
            gap: '12px',
            flexShrink: 0,
          }}>
            <img src={notificationColorIcon} alt="" style={{ width: '40px', height: '40px' }} />
            <div style={{
              fontSize: '24px',
              fontWeight: 600,
              fontStyle: 'normal',
              color: 'var(--color-grayscale-900)',

            }}>
              {notice.title || '서비스 업데이트 안내'}
            </div>
            <div style={{
              fontSize: '14px',
              fontWeight: 400,
              fontStyle: 'normal',
              color: 'var(--color-grayscale-400)',

              textAlign: 'center',
              lineHeight: '1.5',
            }}>
              사내 LLM 서비스가 업데이트되었습니다.<br />
              이번 업데이트에서 변경된 주요 내용을 확인해 주세요.
            </div>
          </div>

          {/* 항목 리스트 */}
          <div style={{ position: 'relative' }}>
          <div
            ref={listRef}
            onScroll={checkScrollFade}
            className="notice-scroll"
            style={{
              overflow: 'auto',
              padding: '0 32px',
              marginRight: '20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '0',
              maxHeight: '240px',
            }}
          >
            {notice.items.map((item, index) => (
              <div
                key={index}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '12px',
                  padding: '5px 20px',
                  backgroundColor: 'transparent'
                }}
              >
                <svg width="15" height="15" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" style={{ flexShrink: 0, marginTop: '2px' }}>
                  <circle cx="10" cy="10" r="9" stroke="var(--color-primary-600)" strokeWidth="2" fill="#fff" />
                  <path d="M6.5 10L9 12.5L13.5 7.5" stroke="var(--color-primary-600)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <div style={{ flex: 1 }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    marginBottom: '4px',
                  }}>
                    <span style={{
                      fontSize: '14px',
                      fontWeight: 500,
                      fontStyle: 'normal',
                      color: 'var(--color-grayscale-900)',

                    }}>
                      {item.title}
                    </span>
                    {item.isNew && (
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: '999px',
                        backgroundColor: '#E1F4EE',
                        color: '#3E9E7F',
          
                        fontSize: '11px',
                        fontWeight: 500,
                        lineHeight: '16px',
                        
                      }}>
                        NEW
                      </span>
                    )}
                  </div>
                  <div style={{
                    fontSize: '14px',
                    fontWeight: 400,
                    fontStyle: 'normal',
                    color: 'var(--color-grayscale-400)',

                    lineHeight: '1.5',
                  }}>
                    {item.description}
                  </div>
                  {item.updatedAt && (
                    <div style={{
                      color: 'var(--color-grayscale-300)',
        
                      fontSize: '12px',
                      fontWeight: 500,
                      lineHeight: '16px',
                      letterSpacing: '-0.24px',
                      
                      marginTop: '4px',
                    }}>
                      {item.updatedAt}
                    </div>
                  )}
                </div>
              </div>
            ))}
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
            }} />
          )}
          </div>

          {/* 하단 버튼 */}
          <div style={{
            padding: '36px 30px 30px',
            flexShrink: 0,
          }}>
            <button
              onClick={handleClose}
              style={{
                width: '100%',
                height: '48px',
                padding: '11px 20px',
                backgroundColor: 'var(--color-grayscale-50)',
                color: 'var(--color-grayscale-400)',
                border: '1px solid var(--color-grayscale-300)',
                borderRadius: '999px',
                fontSize: '16px',
                fontWeight: 600,
                fontStyle: 'normal',
                lineHeight: '26px',
                letterSpacing: '-0.32px',
                
                cursor: 'pointer',
                transition: 'background-color 0.2s',
  
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
              }}
              onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100)'; }}
              onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'var(--color-grayscale-50)'; }}
            >
              닫기
            </button>
          </div>
        </div>

        {/* 모달 밖 - 오늘 하루 보지 않기 */}
        <button
          onClick={handleDismissToday}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            marginTop: '8px',
            backgroundColor: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: '8px 12px',
            borderRadius: '8px',
            transition: 'background-color 0.2s',
          }}
          onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.1)'; }}
          onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M10.5 3.5L3.5 10.5M3.5 3.5L10.5 10.5" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <span style={{
            fontSize: '13px',
            color: '#fff',
            fontWeight: 400,
          }}>
            오늘 하루 보지 않기
          </span>
        </button>
      </div>

      <style>
        {`
          @keyframes modalFadeIn {
            from { opacity: 0; transform: scale(0.95) translateY(-10px); }
            to { opacity: 1; transform: scale(1) translateY(0); }
          }
          .notice-scroll::-webkit-scrollbar {
            width: 8px;
          }
          .notice-scroll::-webkit-scrollbar-track {
            background: transparent;
          }
          .notice-scroll::-webkit-scrollbar-thumb {
            background: transparent;
            border-radius: 4px;
            min-height: 12px;
          }
          .notice-scroll:hover::-webkit-scrollbar-track {
            background: var(--color-grayscale-150);
            border-radius: 4px;
          }
          .notice-scroll:hover::-webkit-scrollbar-thumb {
            background: var(--color-grayscale-300);
          }
        `}
      </style>
    </div>
  );
}

export default UpdateNoticeModal;
