// created by ARES team [2025-12-15]
import { useState } from 'react';
import axios from 'axios';
import AuthLayout from '../../layouts/AuthLayout';
import { getLoginUrl } from '../../services/auth.service';
import { getUserFriendlyMessage, isCustomError } from '../../lib/customError';
import { createCustomError } from '../../lib/customError';
import { COMMON_CODES, AUTH_CODES } from '../../constants/customCodes';
import { loginImage } from '../../assets/icons';
import { GRADIENT, GRADIENT_ACTIVE_SHADOW, gradientButtonBase } from '../../styles/buttonStyles';

function LoginPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // Microsoft 로그인 처리
  const handleMicrosoftLogin = async (): Promise<void> => {
    setError('');
    setIsLoading(true);

    try {
      console.log('[LoginPage] Requesting login URL from backend');
      const { url, state } = await getLoginUrl();
      
      console.log('[LoginPage] Login URL received:', { 
        hasUrl: !!url, 
        hasState: !!state 
      });

      console.log('[LoginPage] Redirecting to Azure AD');
      window.location.href = url;
    } catch (err: unknown) {
      if (isCustomError(err)) {
        setError(getUserFriendlyMessage(err));
      } else if (axios.isAxiosError(err)) {
        if (err.userMessage) {
          // apiClient에서 설정한 userMessage가 있는 경우
          setError(err.userMessage);
        } else if (err.code === 'ERR_NETWORK') {
          setError(getUserFriendlyMessage(createCustomError(COMMON_CODES.COMMON_NETWORK_ERROR)));
        } else if (err.code === 'ECONNABORTED') {
          setError(getUserFriendlyMessage(createCustomError(COMMON_CODES.COMMON_TIMEOUT_ERROR)));
        } else {
          setError(getUserFriendlyMessage(
            createCustomError(
              AUTH_CODES.AUTH_LOGIN_URL_FETCH_FAILED,
              err.response?.data?.message || undefined
            )
          ));
        }
      } else {
        setError(getUserFriendlyMessage(createCustomError(AUTH_CODES.AUTH_LOGIN_URL_FETCH_FAILED)));
      }

      setIsLoading(false);
    }
  };

  return (
    <AuthLayout>
      <div style={{
        display: 'flex',
        width: '100%',
        height: '100vh',
        overflow: 'hidden',
        zIndex: 1,
      }}>

        {/* 비주얼 브랜딩 영역 */}
        <div style={{
          width: '847px',
          maxWidth: '847px',
          flexShrink: 0,
          flexGrow: 0,
          backgroundImage: `url(${loginImage})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          margin: '20px',
          borderRadius: '24px',
          padding: '70px 50px',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'flex-end',
          color: 'white',
          position: 'relative'
        }}>
          <div style={{ position: 'relative', zIndex: 2 }}>
            <h1 style={{
              color: 'var(--color-grayscale-50)',
              fontSize: '60px',
              fontWeight: '700',
              lineHeight: '72px',
              letterSpacing: '-1.2px',
              margin: '0 0 56px 0',
            }}>
              환영합니다.<br />
              대영의 새로운<br />
              AI 서비스.
            </h1>
            <p style={{
              color: 'var(--color-grayscale-50)',
              fontSize: '28px',
              fontWeight: '500',
              lineHeight: '34px',
              letterSpacing: '-0.56px',
            }}>
              사내 문서를 기반으로<br />
              대영AI와 함께 업무를 수행하세요.
            </p>
          </div>
        </div>

        {/* 로그인 액션 영역 */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          padding: '0 60px',
          position: 'relative',
          backgroundColor: 'transparent'
        }}>
          <div style={{ textAlign: 'center', width: '100%' }}>
            {/* 로그인 버튼 */}
            <button
              onClick={handleMicrosoftLogin}
              disabled={isLoading}
              style={{
                ...gradientButtonBase,
                background: GRADIENT.primarySoft,
                width: '289px',
                height: '56px',
                padding: '15px 40px',
                borderRadius: '999px',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                color: 'var(--color-grayscale-50)',
                textAlign: 'center',
                fontSize: '18px',
                fontStyle: 'normal',
                fontWeight: '600',
                lineHeight: '26px',
                letterSpacing: '-0.36px',
                  transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
              }}
              onMouseOver={(e) => {
                if (!isLoading) {
                  e.currentTarget.style.background = GRADIENT.primaryHover;
                }
              }}
              onMouseOut={(e) => {
                if (!isLoading) {
                  e.currentTarget.style.background = GRADIENT.primarySoft;
                  e.currentTarget.style.boxShadow = 'none';
                }
              }}
              onMouseDown={(e) => {
                if (!isLoading) {
                  e.currentTarget.style.background = GRADIENT.primaryActive;
                  e.currentTarget.style.boxShadow = GRADIENT_ACTIVE_SHADOW;
                }
              }}
              onMouseUp={(e) => {
                if (!isLoading) {
                  e.currentTarget.style.background = GRADIENT.primaryHover;
                  e.currentTarget.style.boxShadow = 'none';
                }
              }}
            >
              {isLoading ? (
                <div style={{
                  width: '24px',
                  height: '24px',
                  border: '3px solid rgba(255, 255, 255, 0.3)',
                  borderTop: '3px solid white',
                  borderRadius: '50%',
                  animation: 'login-spin 0.8s linear infinite',
                  margin: '0 auto'
                }} />
              ) : '사내 계정으로 로그인'}
            </button>

            {/* 에러 메시지 표시 */}
            {error && (
              <div style={{
                padding: '12px',
                marginBottom: '20px',
                backgroundColor: 'transparent',
                color: 'var(--color-error-500)',
                fontSize: '14px',
                fontStyle: 'normal',
                fontWeight: '500'
              }}>
                {error}
              </div>
            )}

            <p style={{
              marginTop: '16px',
              fontSize: '14px',
              color: 'var(--color-grayscale-600)',
              fontWeight: '400',
            }}>
              사내 그룹웨어 계정으로 자동 인증됩니다
            </p>
          </div>

          {/* 저작권 표시 */}
          <div style={{
            position: 'absolute',
            bottom: '40px',
            width: 'calc(100% - 120px)',
            textAlign: 'center',
            fontWeight: '500',
            fontSize: '11px',
            color: 'var(--color-grayscale-400)'
          }}>
            © 2026 Daeyoung Ubitech Lab
          </div>
        </div>
      </div>
    </AuthLayout>
  );
}

export default LoginPage;
