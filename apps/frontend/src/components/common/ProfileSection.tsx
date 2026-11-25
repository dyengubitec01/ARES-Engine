// created by ARES team [2026-03-31]
import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import ProfileIcon from '../../assets/icons/profile.svg?react';
import LogoutIcon from '../../assets/icons/logout.svg?react';
import { lightIcon, darkIcon } from '../../assets/sidebar';
import { useTheme } from '../../contexts/ThemeContext';

export interface ProfileMenuItem {
  label: string;
  icon: string;
  onClick: () => void;
  color?: string;
  hoverBg?: string;
}

interface ProfileSectionProps {
  userName?: string;
  userEmail?: string;
  isCollapsed: boolean;
  onLogout: () => void | Promise<void>;
  extraMenuItems?: ProfileMenuItem[];
}

function ProfileSection({
  userName,
  userEmail,
  isCollapsed,
  onLogout,
  extraMenuItems = [],
}: ProfileSectionProps) {
  const { theme, toggleTheme } = useTheme();
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isThemeHovered, setIsThemeHovered] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const portalRef = useRef<HTMLDivElement>(null);
  const positionRef = useRef<{ top: number; left: number }>({ top: 0, left: 0 });

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent): void => {
      if (
        menuRef.current && !menuRef.current.contains(event.target as Node) &&
        (!portalRef.current || !portalRef.current.contains(event.target as Node))
      ) {
        setIsMenuOpen(false);
      }
    };

    if (isMenuOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isMenuOpen]);

  useEffect(() => {
    const handleResize = (): void => {
      if (isMenuOpen) setIsMenuOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [isMenuOpen]);

  const handleLogout = async (): Promise<void> => {
    setIsMenuOpen(false);
    await onLogout();
  };

  const menuItemStyle = {
    padding: '8px 12px',
    backgroundColor: 'transparent',
    border: 'none',
    cursor: 'pointer',
    fontSize: isCollapsed ? '14px' : '13px',
    fontWeight: isCollapsed ? '400' : '500',
    color: 'var(--color-grayscale-900)',
    textAlign: 'left' as const,
    transition: 'all 0.2s',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    borderRadius: '4px',
  };

  const renderMenuItems = () => (
    <div style={{ padding: '4px', display: 'flex', flexDirection: 'column', gap: '2px' }}>
      <button
        onClick={(e) => { e.stopPropagation(); handleLogout(); }}
        style={menuItemStyle}
        onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100)'; }}
        onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
      >
        <LogoutIcon width={16} height={16} style={{ color: 'var(--icon-color)' }} />
        <span>로그아웃</span>
      </button>
      {extraMenuItems.map((item, index) => (
        <button
          key={index}
          onClick={(e) => { e.stopPropagation(); item.onClick(); }}
          style={{
            ...menuItemStyle,
            color: item.color || 'var(--color-grayscale-900)',
          }}
          onMouseOver={(e) => { e.currentTarget.style.backgroundColor = item.hoverBg || 'var(--color-grayscale-100)'; }}
          onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
        >
          <img src={item.icon} alt={item.label} style={{ width: '16px', height: '16px' }} />
          <span>{item.label}</span>
        </button>
      ))}
    </div>
  );

  const renderThemeToggle = (size: number) => {
    const iconSrc = theme === 'light'
      ? (isThemeHovered ? darkIcon : lightIcon)
      : (isThemeHovered ? lightIcon : darkIcon);

    const hoverBackground = theme === 'light'
      ? 'linear-gradient(90deg, var(--color-grayscale-50, #FFF) 50%, var(--color-grayscale-150, #E6E6E6) 50%)'
      : 'linear-gradient(90deg, var(--color-grayscale-100, #292B2F) 50%, var(--color-grayscale-200, #4B4D50) 50%)';

    return (
      <button
        onClick={(e) => { e.stopPropagation(); toggleTheme(); }}
        onMouseEnter={() => setIsThemeHovered(true)}
        onMouseLeave={() => setIsThemeHovered(false)}
        aria-label={theme === 'light' ? '다크 모드' : '라이트 모드'}
        style={{
          width: `${size}px`,
          height: `${size}px`,
          padding: '10px',
          background: isThemeHovered ? hoverBackground : 'var(--color-grayscale-50)',
          border: '1px solid var(--color-grayscale-200)',
          borderRadius: '999px',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'background 0.2s',
          flexShrink: 0,
        }}
      >
        <img
          src={iconSrc}
          alt=""
          style={{ width: '24px', height: '24px' }}
        />
      </button>
    );
  };

  const renderAvatar = () => (
    <div style={{
      width: '40px',
      height: '40px',
      borderRadius: '50%',
      backgroundColor: '#F6EFB8',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: 'var(--color-grayscale-900, #31343E)',
      fontSize: '14px',
      fontStyle: 'normal',
      fontWeight: '500',
      lineHeight: '16px',
      textAlign: 'center',
      flexShrink: 0
    }}>
      {userName?.charAt(0).toUpperCase() || 'U'}
    </div>
  );

  // ── 접힘 상태 ──
  if (isCollapsed) {
    return (
      <div style={{
        flexShrink: 0,
        padding: '12px 0',
        borderTop: '1px solid var(--color-grayscale-200)',
        backgroundColor: 'var(--color-grayscale-100)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '8px',
        position: 'relative'
      }}>
        {renderThemeToggle(46)}

        <div ref={menuRef} style={{ position: 'relative' }}>
          <div
            onClick={(e) => {
              e.stopPropagation();
              if (!isMenuOpen) {
                const rect = e.currentTarget.getBoundingClientRect();
                positionRef.current = { top: rect.bottom, left: rect.right + 8 };
              }
              setIsMenuOpen(!isMenuOpen);
            }}
            style={{ cursor: 'pointer' }}
          >
            <div style={{
              width: '46px',
              height: '46px',
              borderRadius: '999px',
              border: '1px solid var(--color-grayscale-200)',
              background: 'var(--color-grayscale-50)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              {renderAvatar()}
            </div>
          </div>

          {isMenuOpen && createPortal(
            <div ref={portalRef} style={{
              position: 'fixed',
              top: `${positionRef.current.top}px`,
              left: `${positionRef.current.left}px`,
              transform: 'translateY(-100%)',
              backgroundColor: 'var(--menu-bg)',
              border: '1px solid var(--menu-border)',
              borderRadius: '8px',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
              zIndex: 10000,
              minWidth: '140px'
            }}>
              {renderMenuItems()}
            </div>,
            document.body
          )}
        </div>
      </div>
    );
  }

  // ── 펼침 상태 ──
  return (
    <div style={{
      flexShrink: 0,
      padding: '16px 20px',
      backgroundColor: 'var(--color-grayscale-100)',
      borderTop: '1px solid var(--color-grayscale-200)',
      display: 'flex',
      alignItems: 'center',
      gap: '12px',
      position: 'relative'
    }}>
      <div ref={menuRef} style={{ flex: 1, position: 'relative' }}>
        <button
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          style={{
            width: '100%',
            padding: '4px 16px 4px 4px',
            backgroundColor: 'var(--color-grayscale-50)',
            border: '1px solid var(--color-grayscale-200)',
            borderRadius: '32px',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            transition: 'all 0.2s'
          }}
        >
          {renderAvatar()}

          <div style={{
            flex: 1,
            textAlign: 'left',
            overflow: 'hidden',
            lineHeight: '1.25',
            minWidth: 0
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '16px'
            }}>
              <div style={{
                flex: 1,
                fontSize: '16px',
                fontWeight: '600',
                color: 'var(--color-grayscale-900)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                minWidth: 0
              }}>
                {userName || '사용자'}
              </div>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'transform 0.2s',
                transform: isMenuOpen ? 'rotate(0deg)' : 'rotate(180deg)',
                flexShrink: 0
              }}>
                <ProfileIcon width={16} height={16} style={{ color: '#8E8E8E' }} />
              </div>
            </div>
            <div style={{
              color: 'var(--color-grayscale-400, #8E8E8E)',

              fontSize: '10px',
              fontStyle: 'normal',
              fontWeight: '400',
              lineHeight: '12px',
              letterSpacing: '-0.2px',

              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}>
              {userEmail || ''}
            </div>
          </div>
        </button>

        {isMenuOpen && (
          <div ref={portalRef} style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            right: 0,
            marginBottom: '4px',
            backgroundColor: 'var(--menu-bg)',
            border: '1px solid var(--menu-border)',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
            zIndex: 1000
          }}>
            {renderMenuItems()}
          </div>
        )}
      </div>

      {renderThemeToggle(48)}
    </div>
  );
}

export default ProfileSection;
