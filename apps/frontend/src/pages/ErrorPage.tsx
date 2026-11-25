// created by ARES team [2026-03-05]
import { useNavigate } from 'react-router-dom';
import { pageNotFoundIcon } from '../assets/errors';
import { GRADIENT, gradientButtonBase } from '../styles/buttonStyles';

function ErrorPage() {
  const navigate = useNavigate();

  const handleBackToMain = () => {
    navigate('/chat');
  };

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100vh',
      background: 'radial-gradient(138.61% 123.97% at 43.91% 0%, #FFF 28.19%, #F7FBFE 70.67%, #E2F2EE 100%)'
    }}>
      <img 
        src={pageNotFoundIcon} 
        alt="Page Not Found"
        style={{
          width: '710px',
          height: '474px',
          marginBottom: '32px'
        }}
      />
      <h1 style={{
        fontSize: '24px',
        fontWeight: '600',
        color: 'var(--color-grayscale-900)',
        marginBottom: '24px'
      }}>
        잘못된 접근입니다.
      </h1>
      <button
        onClick={handleBackToMain}
        style={{
          ...gradientButtonBase,
          background: GRADIENT.primary,
          padding: '12px 24px',
          fontWeight: '500',
          borderRadius: '32px',
        }}
      >
        메인으로 돌아가기
      </button>
    </div>
  );
}

export default ErrorPage;
