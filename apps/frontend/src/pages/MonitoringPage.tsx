// created by ARES team [2026-06-02]
import Monitoring from '../features/admin/Monitoring';

function MonitoringPage() {
  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: 'var(--color-grayscale-100)',
      display: 'flex',
      flexDirection: 'column',
    }}>
      <main style={{
        flex: 1,
        background: 'var(--main-gradient)',
        overflow: 'auto',
      }}>
        <Monitoring />
      </main>
    </div>
  );
}

export default MonitoringPage;
