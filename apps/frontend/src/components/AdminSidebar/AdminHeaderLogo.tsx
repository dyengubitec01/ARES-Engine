// created by ARES team [2026-04-28]
import { adminModeIcon } from '../../assets/admin';

function AdminHeaderLogo() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        cursor: 'default'
      }}
    >
      <img src={adminModeIcon} alt="관리자 모드" style={{ width: '12px', height: '12px' }} />
      <span style={{
        fontSize: '13px',
        fontWeight: '500',
        color: 'var(--color-primary-600)'
      }}>
        관리자 모드
      </span>
    </div>
  );
}

export default AdminHeaderLogo;