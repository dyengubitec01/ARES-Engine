import { chatIcon } from '../../assets/chats';
import { GRADIENT, GRADIENT_ACTIVE_SHADOW, gradientButtonBase } from '../../styles/buttonStyles';

interface NewChatButtonProps {
  isCollapsed: boolean;
  onClick: (e: React.MouseEvent<HTMLButtonElement>) => void;
  expandedWidth?: string;
}

function NewChatButton({ isCollapsed, onClick, expandedWidth = '100%' }: NewChatButtonProps) {
  return (
    <button
      onClick={onClick}
      style={{
        ...gradientButtonBase,
        background: GRADIENT.primarySoft,
        width: isCollapsed ? '72px' : expandedWidth,
        height: isCollapsed ? '48px' : 'auto',
        padding: isCollapsed ? '11px 24px' : '12px',
        borderRadius: '50px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: isCollapsed ? '0' : '8px',
        flexShrink: 0
      }}
      onMouseOver={(e) => {
        e.currentTarget.style.background = GRADIENT.primaryHover;
      }}
      onMouseOut={(e) => {
        e.currentTarget.style.background = GRADIENT.primarySoft;
        e.currentTarget.style.boxShadow = 'none';
      }}
      onMouseDown={(e) => {
        e.currentTarget.style.background = GRADIENT.primaryActive;
        e.currentTarget.style.boxShadow = GRADIENT_ACTIVE_SHADOW;
      }}
      onMouseUp={(e) => {
        e.currentTarget.style.background = GRADIENT.primaryHover;
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <img src={chatIcon} alt="New Chat" style={{ width: '24px', height: '24px' }} />
      {!isCollapsed && (
        <span style={{ fontSize: '16px', fontWeight: '600' }}>New Chat</span>
      )}
    </button>
  );
}

export default NewChatButton;
