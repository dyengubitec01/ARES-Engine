// created by ARES team [2025-12-15]
import { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { getUserProfile, logout as logoutService } from '../../services/auth.service';
import { clearAuthState } from '../../lib/apiClient';
import { createCustomError } from '../../lib/customError';
import { setFaroUser, clearFaroUser } from '../../lib/faro';
import { AUTH_CODES } from '../../constants/customCodes';

interface DeptPermission {
  id: string;
  name: string;
}

interface User {
  userId: string;
  email: string;
  name: string;
  authorities: string[];
  jobTitle?: string;
  department?: string;
  authDeptId: string;
  deptPermissions: DeptPermission[];
}

interface AuthContextValue {
  user: User | null;
  isAuthenticated: boolean;
  isAdmin: boolean;
  isUploader: boolean;
  isEmbedding: boolean;
  isDownload: boolean;
  isSoftDelete: boolean;
  isLoading: boolean;
  fetchUser: () => Promise<void>;
  refreshSession: () => Promise<void>;
  logout: () => Promise<void>;
}

interface AuthProviderProps {
  children: ReactNode;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const isLoggingOut = useRef(false); // 로그아웃 진행 중 플래그

  // 사용자 프로필 조회
  const fetchUser = async (): Promise<void> => {
    // 로그아웃 중이면 API 호출 차단
    if (isLoggingOut.current) {
      return;
    }

    try {
      console.log('[AuthContext] Fetching user profile...');
      const profile = await getUserProfile();
      setUser(profile);
      setFaroUser({
        id: profile.userId,
        email: profile.email,
        attributes: {
          name: profile.name,
          deptId: profile.authDeptId,
          authorities: profile.authorities.join(','),
        },
      });
    } catch (error: unknown) {
      setUser(null);
      clearFaroUser();
      throw error;
    }
  };

  // 세션 갱신
  const refreshSession = async (): Promise<void> => {
    // 로그아웃 중이면 세션 갱신 차단
    if (isLoggingOut.current) {
      return;
    }

    try {
      console.log('[AuthContext] Refreshing session...');
      const profile = await getUserProfile();
      setUser(profile);
    } catch {
      // 세션 갱신 실패 시에도 기존 사용자 정보 유지 (에러를 던지지 않음)
      // 토큰이 만료된 경우에만 로그아웃 처리가 필요하면 apiClient에서 처리됨
    }
  };

  // 로그아웃
  const logout = async (): Promise<void> => {
    // 이미 로그아웃 중이면 중복 실행 방지
    if (isLoggingOut.current) {
      return;
    }

    isLoggingOut.current = true;

    try {
      setUser(null);
      clearFaroUser();
      clearAuthState();

      try {
        await logoutService();
      } catch {
        // 로그아웃 API 실패해도 계속 진행
      }
    } catch {
      // apiClient 인터셉터에서 로깅됨
    } finally {
      window.location.href = '/';
    }
  };

  // 초기화: 페이지 로드 시 사용자 프로필 조회
  useEffect(() => {
    const initAuth = async () => {
      setIsLoading(true);
      
      // OAuth 콜백 페이지에서는 프로필을 조회하지 않음
      if (window.location.pathname === '/auth/callback') {
        setIsLoading(false);
        return;
      }

      try {
        await fetchUser();
      } catch {
        // 인증되지 않은 경우 에러가 발생하지만 정상적인 플로우
        console.log('[AuthContext] User not authenticated');
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
    
    return () => {
      isLoggingOut.current = false;
    };
  }, []);

  const value: AuthContextValue = {
    user,
    isAuthenticated: !!user,
    isAdmin: !!user && user.authorities.includes('admin'),
    isUploader: !!user && user.authorities.includes('uploader'),
    isEmbedding: !!user && user.authorities.includes('embedding'),
    isDownload: !!user && user.authorities.includes('download'),
    isSoftDelete: !!user && user.authorities.includes('soft_delete'),
    isLoading,
    fetchUser,
    refreshSession,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw createCustomError(
      AUTH_CODES.AUTH_PROFILE_FETCH_FAILED,
      'useAuth must be used within an AuthProvider'
    );
  }
  return context;
}
