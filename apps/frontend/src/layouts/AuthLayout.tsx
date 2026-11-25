// created by ARES team [2025-12-15]
import { ReactNode } from 'react';

interface AuthLayoutProps {
  children: ReactNode;
}

function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100vh',
      overflow: 'hidden'
    }}>
      <main style={{
        flex: 1,
        display: 'flex',
        width: '100%'
      }}>
        {children}
      </main>
    </div>
  );
}

export default AuthLayout;
