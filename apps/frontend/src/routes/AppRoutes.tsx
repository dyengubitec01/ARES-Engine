// created by ARES team [2025-12-15]
import { Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from '../features/auth/LoginPage';
import LoginCallback from '../features/auth/LoginCallback';
import ChatPage from '../pages/ChatPage';
import MyDocumentsPage from '../pages/MyDocumentsPage';
import DocumentApprovalPage from '../pages/DocumentApprovalPage';
import AdminMainPage from '../pages/AdminMainPage';
import MonitoringPage from '../pages/MonitoringPage';
import ErrorPage from '../pages/ErrorPage';
import ProtectedRoute from './ProtectedRoute';
import { useAuth } from '../features/auth/AuthContext';

function AppRoutes() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      {/* 로그인 페이지 - 이미 로그인되어 있으면 채팅 페이지로 리다이렉트 */}
      <Route 
        path="/" 
        element={
          isAuthenticated ? <Navigate to="/chat" replace /> : <LoginPage />
        } 
      />

      {/* OAuth 콜백 페이지 */}
      <Route path="/auth/callback" element={<LoginCallback />} />

      {/* 채팅 페이지 */}
      <Route
        path="/chat"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/chat/:roomId"
        element={
          <ProtectedRoute>
            <ChatPage />
          </ProtectedRoute>
        }
      />

      {/* 내 문서 페이지 (로그인 사용자만) */}
      <Route
        path="/documents"
        element={
          <ProtectedRoute>
            <MyDocumentsPage />
          </ProtectedRoute>
        }
      />

      {/* 문서 승인 관리 페이지 */}
      {/* 승인 절차 임시 중단으로 admin만 접근 허용 (복원 시 ['admin', 'embedding']로 원복) */}
      <Route
        path="/documents/approval"
        element={
          <ProtectedRoute requiredRoles={['admin']}>
            <DocumentApprovalPage />
          </ProtectedRoute>
        }
      />

      {/* 시스템 관리자 페이지 (system 권한 필수) */}
      <Route
        path="/admin"
        element={
          <ProtectedRoute requiredRoles={['admin']}>
            <AdminMainPage />
          </ProtectedRoute>
        }
      />

      {/* 사용자 활동 모니터링 페이지 (링크 접속 전용, admin 권한 필수) */}
      <Route
        path="/admin/monitoring"
        element={
          <ProtectedRoute requiredRoles={['admin']}>
            <MonitoringPage />
          </ProtectedRoute>
        }
      />

      {/* 에러 페이지 (접근 권한 없음) */}
      <Route
        path="/error"
        element={
          <ProtectedRoute>
            <ErrorPage />
          </ProtectedRoute>
        }
      />

      {/* 404 페이지 */}
      <Route
        path="*"
        element={
          <div style={{ 
            display: 'flex', 
            flexDirection: 'column',
            justifyContent: 'center', 
            alignItems: 'center', 
            height: '100vh' 
          }}>
            <h1>404 - 페이지를 찾을 수 없습니다</h1>
            <p>요청하신 페이지가 존재하지 않습니다.</p>
          </div>
        }
      />
    </Routes>
  );
}

export default AppRoutes;


