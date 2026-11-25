// created by ARES team [2025-12-15]
import { ReactNode } from 'react';

interface ChatLayoutProps {
  sidebar: ReactNode;
  children: ReactNode;
}

function ChatLayout({ sidebar, children }: ChatLayoutProps) {
  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      background: 'radial-gradient(138.61% 123.97% at 43.91% 0%, #FFF 28.19%, #F7FBFE 70.67%, #E2F2EE 100%)',
      overflow: 'hidden'
    }}>
      {/* 사이드바 - 채팅방 목록 */}
      <aside style={{
        width: '296px',
        backgroundColor: 'var(--color-grayscale-100)',
        boxShadow: '2px 0 10px 0 rgba(0, 0, 0, 0.08)',
        borderRight: 'none',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 1
      }}>
        {sidebar}
      </aside>

      {/* 메인 채팅 영역 */}
      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        background: 'radial-gradient(138.61% 123.97% at 43.91% 0%, #FFF 28.19%, #F7FBFE 70.67%, #E2F2EE 100%)'
      }}>
        {children}
      </main>
    </div>
  );
}

export default ChatLayout;
