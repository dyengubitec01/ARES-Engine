// created by ARES team [2026-04-09]
import { useState, useEffect } from 'react';
import notificationColorIcon from '../../assets/icons/notification-color.svg';

interface MaintenanceSchedule {
  enabled: boolean;
  title: string;
  dateTime: string;
  reason: string;
}

const BANNER_JSON_PATH = '/maintenance-schedule.json';
const DISMISS_KEY = 'maintenance_banner_dismissed';

let fetched = false;
let cachedSchedule: MaintenanceSchedule | null = null;

function MaintenanceBanner() {
  const [schedule, setSchedule] = useState<MaintenanceSchedule | null>(cachedSchedule);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (fetched) return;
    fetched = true;

    fetch(BANNER_JSON_PATH)
      .then(res => {
        if (!res.ok) throw new Error('not found');
        return res.json();
      })
      .then((data: MaintenanceSchedule) => {
        if (data.enabled && data.title && data.dateTime && data.reason) {
          const dismissedData = localStorage.getItem(DISMISS_KEY);
          if (dismissedData) {
            try {
              const { dateTime } = JSON.parse(dismissedData);
              if (dateTime === data.dateTime) return;
            } catch {
              // 파싱 실패 시 무시
            }
          }
          cachedSchedule = data;
          setSchedule(data);
        }
      })
      .catch(() => {});
  }, []);

  const handleDismiss = () => {
    if (schedule) {
      localStorage.setItem(DISMISS_KEY, JSON.stringify({ dateTime: schedule.dateTime }));
    }
    setDismissed(true);
  };

  if (!schedule || dismissed) return null;

  return (
    <div style={{
      width: '100%',
      padding: '4px 16px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: 'var(--color-primary-600-50, #F2F3FF)',
      flexShrink: 0,
      boxSizing: 'border-box',
      position: 'relative',
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
      }}>
        <img src={notificationColorIcon} alt="" style={{ width: '16px', height: '16px', marginRight: '4px', flexShrink: 0 }} />
        <span style={{
          color: 'var(--color-primary-600, #626BF7)',

          fontSize: '13px',
          fontWeight: 600,
          lineHeight: '20px',
          letterSpacing: '-0.26px',
        }}>
          {schedule.title}
        </span>
        <span style={{ width: '10px', flexShrink: 0 }} />
        <span style={{
          color: 'var(--color-grayscale-600, #757578)',

          fontSize: '13px',
          fontWeight: 600,
          lineHeight: '20px',
          letterSpacing: '-0.26px',
        }}>
          {schedule.dateTime}
        </span>
        <span style={{
          color: 'var(--color-grayscale-600, #757578)',

          fontSize: '13px',
          fontWeight: 400,
          lineHeight: '20px',
          letterSpacing: '-0.26px',
        }}>
          부터 {schedule.reason}으로 서비스 이용이 불가합니다.
        </span>
      </div>
      <button
        onClick={handleDismiss}
        style={{
          position: 'absolute',
          right: '16px',
          top: '50%',
          transform: 'translateY(-50%)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '6px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
        title="닫기"
      >
        <svg width="8" height="8" viewBox="0 0 8 8" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M1 1L7 7M7 1L1 7" stroke="var(--color-grayscale-500)" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      </button>
    </div>
  );
}

export default MaintenanceBanner;
