// created by ARES team [2026-01-07]
import { useEffect, useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from './AuthContext';
import AuthLayout from '../../layouts/AuthLayout';
import apiClient from '../../lib/apiClient';
import { createCustomError, getUserFriendlyMessage, isCustomError } from '../../lib/customError';
import { AUTH_CODES, COMMON_CODES } from '../../constants/customCodes';

function LoginCallback() {
  const [searchParams] = useSearchParams();
  const [error, setError] = useState('');
  const { fetchUser } = useAuth();
  const navigate = useNavigate();
  const hasProcessed = useRef(false); // 중복 실행 방지 플래그
  const isMounted = useRef(true); // 마운트 상태 추적

  useEffect(() => {
    // 컴포넌트 마운트 상태 추적
    isMounted.current = true;

    // 이미 처리했으면 무시 (React Strict Mode 대응)
    if (hasProcessed.current) {
      return;
    }

    const handleCallback = async () => {
      // 1. URL에서 code와 state 추출
      const code = searchParams.get('code');
      const state = searchParams.get('state');

      console.log('[LoginCallback] Received params:', {
        hasCode: !!code,
        hasState: !!state,
      });

      if (!code || !state) {
        console.error('[LoginCallback] Missing code or state parameter');
        if (isMounted.current) {
          setError(getUserFriendlyMessage(createCustomError(AUTH_CODES.AUTH_INVALID_OAUTH_PARAMS)));
        }
        return;
      }

      // 처리 시작 표시 (try 블록 진입 전에 설정하여 실패 시에도 재시도 방지)
      hasProcessed.current = true;

      try {
        // 2. 백엔드에 콜백 요청
        await apiClient.get('/auth/callback', {
          params: { code, state },
        });
        // 3. 사용자 프로필 조회
        await fetchUser();
        // 4. 채팅 페이지로 이동 (컴포넌트가 마운트된 경우에만)
        if (isMounted.current) {
          navigate('/chat', { replace: true });
        }
      } catch (err: unknown) {
        // 컴포넌트가 언마운트되었으면 상태 업데이트 하지 않음
        if (!isMounted.current) {
          return;
        }

        // 에러 처리
        if (isCustomError(err)) {
          setError(getUserFriendlyMessage(err));
        } else if (axios.isAxiosError(err)) {
          if (err.userMessage) {
            // apiClient에서 설정한 userMessage 우선 사용
            setError(err.userMessage);
          } else if (err.response?.status === 401) {
            setError(getUserFriendlyMessage(createCustomError(AUTH_CODES.AUTH_FAILED)));
          } else if (err.response?.status === 403) {
            setError(getUserFriendlyMessage(createCustomError(AUTH_CODES.AUTH_ACCESS_DENIED)));
          } else if (err.code === 'ERR_NETWORK') {
            setError(getUserFriendlyMessage(createCustomError(COMMON_CODES.COMMON_NETWORK_ERROR)));
          } else {
            setError(getUserFriendlyMessage(
              createCustomError(
                AUTH_CODES.AUTH_OAUTH_CALLBACK_FAILED,
                err.response?.data?.message
              )
            ));
          }
        } else {
          setError(getUserFriendlyMessage(createCustomError(AUTH_CODES.AUTH_OAUTH_CALLBACK_FAILED)));
        }

        // 3초 후 로그인 페이지로 이동
        setTimeout(() => {
          if (isMounted.current) {
            navigate('/', { replace: true });
          }
        }, 3000);
      }
    };

    handleCallback();

    // Cleanup: 컴포넌트 언마운트 시 플래그 설정
    return () => {
      isMounted.current = false;
    };
    // OAuth 콜백은 마운트 시 1회만 실행되어야 함 (재실행 시 중복 처리 위험)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <AuthLayout>
      <div style={{ textAlign: 'center' }}>
        {error ? (
          <>
            <h2 style={{ marginBottom: '20px', color: 'var(--color-error-500)', fontSize: '20px' }}>
              로그인 실패
            </h2>
            <p style={{ color: 'var(--color-grayscale-600)', marginBottom: '10px' }}>{error}</p>
            <p style={{ fontSize: '14px', color: 'var(--color-grayscale-500)' }}>
              잠시 후 로그인 페이지로 이동합니다...
            </p>
          </>
        ) : (
          <>
            <div
              style={{
                width: '40px',
                height: '40px',
                border: '4px solid #f3f3f3',
                borderTop: '4px solid #0078d4',
                borderRadius: '50%',
                margin: '0 auto 20px',
                animation: 'spin 1s linear infinite',
              }}
            />
            <style>
              {`
                @keyframes spin {
                  0% { transform: rotate(0deg); }
                  100% { transform: rotate(360deg); }
                }
              `}
            </style>
            <h2 style={{ marginBottom: '10px', fontSize: '20px' }}>
              로그인 처리 중...
            </h2>
            <p style={{ color: 'var(--color-grayscale-600)', fontSize: '14px' }}>잠시만 기다려주세요.</p>
          </>
        )}
      </div>
    </AuthLayout>
  );
}

export default LoginCallback;
