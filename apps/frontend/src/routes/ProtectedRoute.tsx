// created by ARES team [2025-12-15]
import { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../features/auth/AuthContext';
import Skeleton from '../components/common/Skeleton';

interface ProtectedRouteProps {
  children: ReactNode;
  requiredRoles?: string[];
}

function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user } = useAuth();

  // 로딩 중일 때는 전체 화면 스켈레톤 표시
  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        height: '100vh',
        backgroundColor: 'var(--color-grayscale-100)',
        overflow: 'hidden'
      }}>
        {/* 사이드바 스켈레톤 */}
        <div style={{
          width: 'var(--sidebar-width)',
          backgroundColor: 'var(--color-grayscale-100)',
          borderRight: '1px solid var(--color-grayscale-150)',
          display: 'flex',
          flexDirection: 'column',
          padding: '12px',
          gap: '16px',
          flexShrink: 0
        }}>
          {/* 사이드바 헤더 */}
          <Skeleton width="60%" height="32px" borderRadius="8px" />
          <Skeleton width="100%" height="40px" borderRadius="8px" />
          {/* 채팅방 목록 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '8px' }}>
            {[...Array(6)].map((_, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <Skeleton width={`${70 - i * 5}%`} height="14px" borderRadius="4px" />
                <Skeleton width={`${50 - i * 3}%`} height="12px" borderRadius="4px" />
              </div>
            ))}
          </div>
          {/* 하단 프로필 영역 */}
          <div style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Skeleton width="36px" height="36px" borderRadius="50%" />
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <Skeleton width="80px" height="14px" borderRadius="4px" />
              <Skeleton width="120px" height="12px" borderRadius="4px" />
            </div>
          </div>
        </div>

        {/* 메인 콘텐츠 스켈레톤 */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--main-gradient)',
          padding: '24px 40px'
        }}>
          {/* 헤더 영역 */}
          <Skeleton width="200px" height="24px" borderRadius="6px" />
          {/* 콘텐츠 영역 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '32px' }}>
            <Skeleton width="100%" height="36px" borderRadius="8px" />
            <Skeleton width="100%" height="300px" borderRadius="8px" />
          </div>
        </div>
      </div>
    );
  }

  // 인증되지 않은 경우 로그인 페이지로 리다이렉트
  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  // 권한 체크: requiredRoles가 있는 경우 사용자 권한 확인
  if (requiredRoles && requiredRoles.length > 0 && user) {
    const hasRequiredRole = requiredRoles.some(role => 
      user.authorities.includes(role)
    );

    if (!hasRequiredRole) {
      // 권한이 없으면 에러 페이지로 리다이렉트
      return <Navigate to="/error" replace />;
    }
  }

  return <>{children}</>;
}

export default ProtectedRoute;


