// created by ARES team [2025-12-15]
import { ReactNode, useState } from 'react';
import { useLocation } from 'react-router-dom';
import FoldIcon from '../assets/sidebar/fold.svg?react';
import ErrorReportButton from '../components/common/ErrorReportButton';
import MaintenanceBanner from '../components/common/MaintenanceBanner';
import { useMaintenance, MaintenanceScreen } from '../components/common/MaintenanceOverlay';

interface PageLayoutProps {
  sidebarContent: (isCollapsed: boolean) => ReactNode;
  children: ReactNode;
  sidebarActions?: (isCollapsed: boolean, expandSidebar?: () => void) => ReactNode;
  sidebarHeaderActions?: (isCollapsed: boolean) => ReactNode;
  sidebarHeaderTrailingActions?: (isCollapsed: boolean) => ReactNode;
  showSidebarToggle?: boolean;
}

function PageLayout({ sidebarContent, children, sidebarActions, sidebarHeaderActions, sidebarHeaderTrailingActions, showSidebarToggle = true }: PageLayoutProps) {
  const location = useLocation();
  const { maintenance, isPageMaintenance } = useMaintenance();
  const isAdminPage = location.pathname.startsWith('/admin');
  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    return localStorage.getItem('sidebar_collapsed') === 'true';
  });

  const toggleCollapsed = (): void => {
    setIsCollapsed(prev => {
      const next = !prev;
      localStorage.setItem('sidebar_collapsed', String(next));
      return next;
    });
  };

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      backgroundColor: 'var(--color-grayscale-100)',
      overflow: 'hidden'
    }}>
      {/* 사이드바 */}
      <aside style={{
        width: isCollapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)',
        backgroundColor: 'var(--color-grayscale-100)',
        borderRight: '1px solid var(--color-grayscale-150)',
        display: 'flex',
        flexDirection: 'column',
        boxShadow: '2px 0 10px 0 rgba(0, 0, 0, 0.08)',
        overflow: 'hidden',
        transition: 'width 0.3s ease',
        flexShrink: 0,
        minHeight: 0,
        height: '100vh'
      }}>
        {/* 사이드바 헤더 */}
        <div style={{
          flexShrink: 0,
          padding: '22px 20px',
          backgroundColor: 'var(--color-grayscale-100)'
        }}>
          {/* 타이틀 + 접기 버튼 행 */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: isCollapsed ? 'center' : 'space-between',
            marginBottom: isCollapsed ? '16px' : '20px',
            minHeight: '32px'
          }}>
            {/* 타이틀 (펼친 상태에서만 표시) */}
            {!isCollapsed && sidebarHeaderActions && (
              <div style={{ flex: 1, overflow: 'hidden', alignSelf: 'flex-start' }}>
                {sidebarHeaderActions(isCollapsed)}
              </div>
            )}

            {/* 트레일링 액션 (알림 등) + 접기/펼치기 버튼 */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              marginRight: isCollapsed ? '0' : '-4px',
              marginTop: isCollapsed ? '0' : '-4px',
              flexShrink: 0,
            }}>
              {sidebarHeaderTrailingActions && sidebarHeaderTrailingActions(isCollapsed)}
              {showSidebarToggle && (
                <button
                  onClick={toggleCollapsed}
                  style={{
                    backgroundColor: 'transparent',
                    border: 'none',
                    borderRadius: '6px',
                    padding: '8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'background-color 0.2s',
                    flexShrink: 0
                  }}
                  onMouseOver={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--color-grayscale-150)';
                  }}
                  onMouseOut={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  <FoldIcon width={24} height={24} style={{ color: 'var(--color-grayscale-500)' }} />
                </button>
              )}
            </div>
          </div>

          {/* 새 채팅, 내 문서 버튼 영역 */}
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: isCollapsed ? '20px' : '8px'
          }}>
            {sidebarActions && sidebarActions(isCollapsed, () => {
              if (isCollapsed) {
                setIsCollapsed(false);
                localStorage.setItem('sidebar_collapsed', 'false');
              }
            })}
          </div>
        </div>

        {/* 사이드바 콘텐츠 */}
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
          {sidebarContent(isCollapsed)}
        </div>
      </aside>

      {/* 메인 영역 */}
      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--main-gradient)',
        overflow: 'hidden'
      }}>
        {/* 메인 콘텐츠 */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'auto'
        }}>
          {isPageMaintenance && maintenance ? (
            <MaintenanceScreen maintenance={maintenance} />
          ) : (
            <>
              <div style={{ padding: '18px var(--content-padding) 3px', display: 'flex', justifyContent: 'flex-start' }}>
                <ErrorReportButton />
              </div>
              {children}
            </>
          )}
        </div>
        {!isAdminPage && <MaintenanceBanner />}
      </main>
    </div>
  );
}

export default PageLayout;
