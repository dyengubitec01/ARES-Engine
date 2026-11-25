// created by ARES team [2026-04-07]
import { useState, useEffect, createContext, useContext } from 'react';
import { useLocation } from 'react-router-dom';
import { serviceMaintenanceIcon, serviceErrorIcon } from '../../assets/errors';

export interface MaintenanceData {
  enabled: boolean;
  title: string;
  time: string;
  message: string;
  targetPages: string[];
}

// ── Context: 앱 전체에서 1회만 fetch ──
const MaintenanceContext = createContext<MaintenanceData | null>(null);

/** PageLayout 등에서 점검 상태를 읽는 훅 */
// eslint-disable-next-line react-refresh/only-export-components
export function useMaintenance() {
  const maintenance = useContext(MaintenanceContext);
  const location = useLocation();

  const isFullMaintenance = maintenance?.enabled === true
    && (!maintenance.targetPages?.length || maintenance.targetPages.includes('*'));

  const isPageMaintenance = maintenance?.enabled === true
    && !isFullMaintenance
    && maintenance.targetPages.some(page => location.pathname.startsWith(page));

  return { maintenance, isFullMaintenance, isPageMaintenance };
}

/** 점검 화면 UI (전체 화면 / 콘텐츠 영역 겸용) */
export function MaintenanceScreen({ maintenance, fullScreen = false }: { maintenance: MaintenanceData; fullScreen?: boolean }) {
  return (
    <div
      style={{
        ...(fullScreen
          ? { position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 10001 }
          : { flex: 1, width: '100%' }),
        background: 'radial-gradient(138.61% 123.97% at 43.91% 0%, #FFF 28.19%, #F7FBFE 70.67%, #E2F2EE 100%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        overflow: 'auto',
      }}
    >
      <img
        src={serviceMaintenanceIcon}
        style={{
          width: '780px',
          height: '521px',
          aspectRatio: '259/173',
          marginTop: fullScreen ? '106px' : '60px',
          flexShrink: 0,
        }}
      />

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        marginTop: '30px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <img src={serviceErrorIcon} alt="" style={{ width: '20px', height: '20px', flexShrink: 0 }} />
          <span style={{
            color: 'var(--color-error-500)',
            fontSize: '14px',
            fontWeight: 500,
            lineHeight: '20px',
            letterSpacing: '-0.28px',
          }}>
            {maintenance.title}
          </span>
        </div>

        <div style={{
          marginTop: '16px',
          color: 'var(--color-grayscale-600)',
          textAlign: 'center',
          fontSize: '14px',
          fontWeight: 600,
          lineHeight: '20px',
          letterSpacing: '-0.28px',
        }}>
          {maintenance.time}
        </div>

        <div style={{
          marginTop: '10px',
          color: 'var(--color-grayscale-400)',
          textAlign: 'center',
          fontSize: '14px',
          fontWeight: 500,
          lineHeight: '20px',
          letterSpacing: '-0.28px',
          whiteSpace: 'pre-line',
        }}>
          {maintenance.message}
        </div>
      </div>
    </div>
  );
}

/** App.tsx에서 감싸는 전체 점검 오버레이 + Context Provider */
function MaintenanceOverlay({ children }: { children: React.ReactNode }) {
  const [maintenance, setMaintenance] = useState<MaintenanceData | null>(null);
  const location = useLocation();

  useEffect(() => {
    fetch('/maintenance.json')
      .then(res => {
        if (!res.ok) throw new Error('not found');
        return res.json();
      })
      .then((data: MaintenanceData) => {
        setMaintenance(data.enabled ? data : null);
      })
      .catch(() => {
        setMaintenance(null);
      });
  }, [location.pathname]);

  const isFullMaintenance = maintenance?.enabled === true
    && (!maintenance.targetPages?.length || maintenance.targetPages.includes('*'));

  if (isFullMaintenance && maintenance) {
    return <MaintenanceScreen maintenance={maintenance} fullScreen={true} />;
  }

  return (
    <MaintenanceContext.Provider value={maintenance}>
      {children}
    </MaintenanceContext.Provider>
  );
}

export default MaintenanceOverlay;
