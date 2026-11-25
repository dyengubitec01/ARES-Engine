// created by ARES team [2025-12-15]
import { useState, useRef, useEffect, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { ChatRoom } from './types';
import ViewMoreIcon from '../../assets/icons/more.svg?react';
import { adminModeIcon } from '../../assets/admin';
import ChatFavSelectIcon from '../../assets/chats/fav-select.svg?react';
import ChatFavIcon from '../../assets/chats/fav.svg?react';
import ChatEditIcon from '../../assets/chats/edit.svg?react';
import ChatDeleteIcon from '../../assets/chats/delete.svg?react';
import ProfileSection from '../../components/common/ProfileSection';
import SidebarShell from '../../components/common/SidebarShell';
import Skeleton from '../../components/common/Skeleton';
import { createCustomError, getUserFriendlyMessage } from '../../lib/customError';
import { CHAT_CODES } from '../../constants/customCodes';
import { useScrollFade } from '../../hooks/useScrollFade';

interface ChatRoomListProps {
  rooms: ChatRoom[];
  activeRoomId?: string;
  onRoomSelect: (roomId: string) => void;
  onNewChat: () => void;
  onToggleFavorite: (roomId: string) => void;
  onLogout: () => void | Promise<void>;
  onRoomRename: (roomId: string, newTitle: string) => Promise<void>;
  onRoomDelete: (roomId: string, currentActiveRoomId?: string) => Promise<void>;
  userName?: string;
  userEmail?: string;
  isAdmin?: boolean;
  onAdminClick?: () => void;
  isCollapsed?: boolean;
  isLoading?: boolean;
}

function ChatRoomList({
  rooms,
  activeRoomId,
  onRoomSelect,
  onToggleFavorite,
  onLogout,
  onRoomRename,
  onRoomDelete,
  userName,
  userEmail,
  isAdmin,
  onAdminClick,
  isCollapsed = false,
  isLoading = false
}: ChatRoomListProps) {
  const [hoveredRoomId, setHoveredRoomId] = useState<string | null>(null);
  const [editingRoomId, setEditingRoomId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState<string>('');
  const [editError, setEditError] = useState<string | null>(null);
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const { ref: scrollContainerRef, showTopFade, showBottomFade, handleScroll } = useScrollFade<HTMLDivElement>();
  const inputRef = useRef<HTMLInputElement>(null);
  const menuRef = useRef<{ [key: string]: HTMLDivElement | null }>({});
  const contextMenuPortalRef = useRef<HTMLDivElement>(null);
  const menuPositionRef = useRef<{ top: number; left: number }>({ top: 0, left: 0 });

  useEffect(() => {
    handleScroll();
    // rooms/isLoading 변경시만 스크롤 처리 의도 (handleScroll은 useScrollFade 내부에서 관리)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rooms, isLoading]);

  // 섹션 헤더 스타일 정의
  const sectionHeaderBaseStyle = {
    fontSize: '12px',
    fontWeight: '500',
    color: 'var(--color-grayscale-400)',
    padding: '0 10px 4px 10px'
  } as const;

  const sectionHeaderWithSpacingStyle = {
    ...sectionHeaderBaseStyle,
    marginTop: '12px'
  } as const;

  // 편집 모드 진입 시 input에 포커스
  useEffect(() => {
    if (editingRoomId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingRoomId]);

  // 채팅방 메뉴 외부 클릭 감지
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent): void => {
      if (menuOpenId) {
        const triggerElement = menuRef.current[menuOpenId];
        const portalElement = contextMenuPortalRef.current;
        const target = event.target as Node;
        if (
          (!triggerElement || !triggerElement.contains(target)) &&
          (!portalElement || !portalElement.contains(target))
        ) {
          setMenuOpenId(null);
        }
      }
    };

    if (menuOpenId) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [menuOpenId]);

  // 윈도우 리사이즈 시 열린 드롭다운 닫기
  useEffect(() => {
    if (!menuOpenId) return;

    const handleResize = () => {
      setMenuOpenId(null);
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [menuOpenId]);

  // 이름 변경 시작
  const handleStartEdit = (roomId: string, currentTitle: string): void => {
    setEditingRoomId(roomId);
    setEditTitle(currentTitle);
    setEditError(null);
    setMenuOpenId(null);
  };

  // 이름 변경 완료
  const handleFinishEdit = async (): Promise<void> => {
    if (!editingRoomId) return;

    const trimmedTitle = editTitle.trim();
    if (trimmedTitle === '') {
      setEditError(getUserFriendlyMessage(createCustomError(CHAT_CODES.CHAT_EMPTY_ROOM_NAME)));
      return;
    }

    setEditError(null);

    // 변경 사항이 없으면 그냥 종료
    const currentRoom = rooms.find(r => r.id === editingRoomId);
    if (currentRoom && currentRoom.title === trimmedTitle) {
      setEditingRoomId(null);
      return;
    }

    try {
      await onRoomRename(editingRoomId, trimmedTitle);
      setEditingRoomId(null);
    } catch {
      setEditError(getUserFriendlyMessage(createCustomError(CHAT_CODES.CHAT_ROOM_RENAME_FAILED)));
    }
  };

  // 편집 취소
  const handleCancelEdit = (): void => {
    setEditingRoomId(null);
    setEditTitle('');
    setEditError(null);
  };

  // 채팅방을 날짜별로 그룹화
  const groupedRooms = useMemo(() => {
    // 한국 시간(KST) 기준
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const weekAgo = new Date(today);
    weekAgo.setDate(weekAgo.getDate() - 7);

    const groups = {
      favorites: [] as ChatRoom[],
      today: [] as ChatRoom[],
      yesterday: [] as ChatRoom[],
      thisWeek: [] as ChatRoom[],
      older: [] as ChatRoom[]
    };

    rooms.forEach(room => {
      // createdAt을 우선 사용하고, 없으면 lastMessageTime, 둘 다 없으면 현재 시간
      const dateString = room.createdAt || room.lastMessageTime || new Date().toISOString();
      
      // UTC 시간을 로컬 시간으로 변환
      const roomDate = new Date(dateString);
      
      // 날짜만 비교하기 위해 시간 정보 제거
      const roomDateOnly = new Date(roomDate.getFullYear(), roomDate.getMonth(), roomDate.getDate());

      if (room.isFavorite) {
        groups.favorites.push(room);
      } else if (roomDateOnly.getTime() === today.getTime()) {
        groups.today.push(room);
      } else if (roomDateOnly.getTime() === yesterday.getTime()) {
        groups.yesterday.push(room);
      } else if (roomDateOnly >= weekAgo) {
        groups.thisWeek.push(room);
      } else {
        groups.older.push(room);
      }
    });

    // 각 그룹 내에서 최신순 정렬
    const sortByTime = (a: ChatRoom, b: ChatRoom) => {
      const timeA = new Date(a.createdAt || a.lastMessageTime || 0).getTime();
      const timeB = new Date(b.createdAt || b.lastMessageTime || 0).getTime();
      return timeB - timeA;
    };

    groups.favorites.sort(sortByTime);
    groups.today.sort(sortByTime);
    groups.yesterday.sort(sortByTime);
    groups.thisWeek.sort(sortByTime);
    groups.older.sort(sortByTime);

    return groups;
  }, [rooms]);

  // 채팅방 아이템 렌더링 함수
  const renderRoomItem = (room: ChatRoom) => (
    <div
      key={room.id}
      onMouseEnter={() => setHoveredRoomId(room.id)}
      onMouseLeave={() => setHoveredRoomId(null)}
      style={{
        padding: '0 10px',
        margin: '6px 0',
        display: 'flex',
        flexDirection: 'column' as const,
        gap: '8px',
        backgroundColor: 'transparent',
        border: 'none',
        transition: 'all 0.2s',
        cursor: editingRoomId === room.id ? 'default' : 'pointer'
      }}
      onClick={() => {
        if (editingRoomId !== room.id) {
          if (editingRoomId) handleCancelEdit();
          onRoomSelect(room.id);
        }
      }}
    >
      {/* 편집 모드: input만 표시 */}
      {editingRoomId === room.id ? (
        <>
          <input
            ref={inputRef}
            type="text"
            value={editTitle}
            onChange={(e) => {
              setEditTitle(e.target.value);
              if (editError) setEditError(null);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleFinishEdit();
              } else if (e.key === 'Escape') {
                handleCancelEdit();
              }
            }}
            onBlur={handleFinishEdit}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: '100%',
              padding: '4px 8px',
              fontSize: '14px',
              fontWeight: 'bold',
              color: 'var(--color-grayscale-900)',
              border: editError ? '1px solid var(--color-error-500)' : '1px solid var(--color-accent-dark)',
              borderRadius: '4px',
              outline: 'none'
            }}
          />
          {editError && (
            <div style={{
              color: 'var(--color-error-500)',
              fontSize: '12px',
              fontWeight: '500',
              paddingLeft: '4px',
            }}>
              {editError}
            </div>
          )}
        </>
      ) : (
        <>
          {/* 채팅방 */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            position: 'relative',
          }}>
            {/* 즐겨찾기 아이콘 - 즐겨찾기된 채팅방만 표시 */}
            {room.isFavorite && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleFavorite(room.id);
                }}
                style={{
                  padding: '0',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.2s',
                  flexShrink: 0
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.transform = 'scale(1.2)';
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.transform = 'scale(1)';
                }}
              >
                {activeRoomId === room.id ? (
                  <ChatFavSelectIcon width={20} height={20} style={{ color: 'var(--icon-active-color)' }} />
                ) : (
                  <ChatFavIcon width={20} height={20} style={{ color: 'var(--icon-color)' }} />
                )}
              </button>
            )}

            {/* 제목 영역 */}
            <div style={{
              flex: 1,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              fontWeight: '500',
              color: activeRoomId === room.id ? 'var(--color-primary-600)' : 'var(--color-grayscale-900)',
              fontSize: '14px'
            }}>
              {room.title || '새로운 대화'}
            </div>

            {/* 메뉴 버튼 */}
              <div
                ref={(el) => menuRef.current[room.id] = el}
                style={{
                  position: 'absolute',
                  right: 0,
                  top: '50%',
                  transform: 'translateY(-50%)',
                  display: (hoveredRoomId === room.id || menuOpenId === room.id) ? 'flex' : 'none',
                  alignItems: 'center',
                  backgroundColor: 'var(--color-grayscale-100)',
                  borderRadius: '4px',
                }}
              >
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (menuOpenId === room.id) {
                      setMenuOpenId(null);
                    } else {
                      const rect = e.currentTarget.getBoundingClientRect();
                      menuPositionRef.current = { top: rect.top, left: rect.right + 4 };
                      setMenuOpenId(room.id);
                    }
                  }}
                  style={{
                    backgroundColor: 'transparent',
                    border: 'none',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.2s'
                  }}
                >
                  <ViewMoreIcon width={20} height={20} style={{ color: activeRoomId === room.id ? 'var(--icon-active-color)' : 'var(--icon-color)' }} />
                </button>

                {/* 드롭다운 메뉴 (Portal) */}
                {menuOpenId === room.id && createPortal(
                  <div ref={contextMenuPortalRef} style={{
                    position: 'fixed',
                    top: `${menuPositionRef.current.top}px`,
                    left: `${menuPositionRef.current.left}px`,
                    backgroundColor: 'var(--menu-bg)',
                    border: '1px solid var(--menu-border)',
                    borderRadius: '8px',
                    boxShadow: '2px 2px 6px 0 rgba(0, 0, 0, 0.05)',
                    zIndex: 10000,
                    minWidth: '120px',
                    padding: '6px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                  }}>
                    {/* 즐겨찾기 / 즐겨찾기 해제 */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onToggleFavorite(room.id);
                        setMenuOpenId(null);
                      }}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        backgroundColor: 'transparent',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',

                        fontSize: '14px',
                        fontWeight: '400',
                        fontStyle: 'normal',
                        lineHeight: '20px',
                        letterSpacing: '-0.28px',
                        
                        color: 'var(--color-grayscale-900, #31343E)',
                        textAlign: 'left',
                        transition: 'all 0.2s',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px'
                      }}
                      onMouseOver={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100)';
                      }}
                      onMouseOut={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      {room.isFavorite ? (
                        <ChatFavSelectIcon width={16} height={16} style={{ color: 'var(--icon-color)' }} />
                      ) : (
                        <ChatFavIcon width={16} height={16} style={{ color: 'var(--icon-color)' }} />
                      )}
                      <span>{room.isFavorite ? '고정 해제' : '고정'}</span>
                    </button>

                    {/* 이름 변경 */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleStartEdit(room.id, room.title);
                      }}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        backgroundColor: 'transparent',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',

                        fontSize: '14px',
                        fontWeight: '400',
                        fontStyle: 'normal',
                        lineHeight: '20px',
                        letterSpacing: '-0.28px',
                        
                        color: 'var(--color-grayscale-900, #31343E)',
                        textAlign: 'left',
                        transition: 'all 0.2s',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px'
                      }}
                      onMouseOver={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100)';
                      }}
                      onMouseOut={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      <ChatEditIcon width={16} height={16} style={{ color: 'var(--icon-color)' }} />
                      <span>이름 변경</span>
                    </button>

                    {/* 삭제하기 */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onRoomDelete(room.id, activeRoomId);
                        setMenuOpenId(null);
                      }}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        backgroundColor: 'transparent',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',

                        fontSize: '14px',
                        fontWeight: '400',
                        fontStyle: 'normal',
                        lineHeight: '20px',
                        letterSpacing: '-0.28px',
                        
                        color: 'var(--color-grayscale-900, #31343E)',
                        textAlign: 'left',
                        transition: 'all 0.2s',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px'
                      }}
                      onMouseOver={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100)';
                      }}
                      onMouseOut={(e) => {
                        e.currentTarget.style.backgroundColor = 'transparent';
                      }}
                    >
                      <ChatDeleteIcon width={16} height={16} style={{ color: 'var(--icon-color)' }} />
                      <span>삭제하기</span>
                    </button>
                  </div>,
                  document.body
                )}
              </div>
          </div>

          {/* lastMessage는 두 번째 줄에 표시 */}
          {room.lastMessage && (
            <div style={{
              fontSize: '12px',
              color: 'var(--color-grayscale-600)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              paddingLeft: '28px'
            }}>
              {room.lastMessage}
            </div>
          )}
        </>
      )}
    </div>
  );

  const profileExtraMenuItems = isAdmin && onAdminClick
    ? [{ label: '관리자 모드', icon: adminModeIcon, onClick: () => onAdminClick(), color: 'var(--color-primary-600, #626BF7)', hoverBg: 'var(--color-primary-100, #F2F3FF)' }]
    : [];

  const profileNode = (
    <ProfileSection
      userName={userName}
      userEmail={userEmail}
      isCollapsed={isCollapsed}
      onLogout={onLogout}
      extraMenuItems={profileExtraMenuItems}
    />
  );

  if (isCollapsed) {
    return (
      <SidebarShell profile={profileNode}>
        <div style={{ flex: 1 }} />
      </SidebarShell>
    );
  }

  return (
    <SidebarShell profile={profileNode}>
      {/* 대화 히스토리 구분선 */}
      <div style={{
        flexShrink: 0,
        padding: '0px 20px 22px 20px',
        backgroundColor: 'var(--color-grayscale-100)',
      }}>
        <div style={{ borderTop: '1px solid var(--color-grayscale-200)' }} />
      </div>

      {/* 채팅방 목록 */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden', minHeight: 0 }}>
        {showTopFade && (
          <div style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            height: '40px',
            background: 'linear-gradient(to bottom, var(--color-grayscale-100), transparent)',
            pointerEvents: 'none',
            zIndex: 1
          }} />
        )}
        {showBottomFade && (
          <div style={{
            position: 'absolute',
            bottom: 0,
            left: 0,
            right: 0,
            height: '40px',
            background: 'linear-gradient(to top, var(--color-grayscale-100), transparent)',
            pointerEvents: 'none',
            zIndex: 1
          }} />
        )}
      <div
        ref={scrollContainerRef}
        onScroll={handleScroll}
        className="hide-scrollbar"
        style={{
        height: '100%',
        overflowY: 'auto',
        padding: '0 20px 20px',
        backgroundColor: 'transparent',
      }}>
        {isLoading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', padding: '12px 0' }}>
            {[...Array(5)].map((_, i) => (
              <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <Skeleton width={`${65 - i * 5}%`} height="14px" borderRadius="4px" />
                <Skeleton width={`${45 - i * 3}%`} height="12px" borderRadius="4px" />
              </div>
            ))}
          </div>
        ) : rooms.length === 0 ? (
          <div style={{
            textAlign: 'center',
            padding: '40px 20px',
            color: 'var(--color-grayscale-500)'
          }}>
            <p>아직 채팅방이 없습니다.</p>
            <p>새 채팅을 시작해보세요!</p>
          </div>
        ) : (
          (() => {
            const hasFavorites = groupedRooms.favorites.length > 0;
            let isFirst = !hasFavorites;
            const getStyle = () => {
              if (isFirst) { isFirst = false; return sectionHeaderBaseStyle; }
              return sectionHeaderWithSpacingStyle;
            };
            return (
              <>
                {/* 즐겨찾기 섹션 */}
                {hasFavorites && (
                  <>
                    <div style={sectionHeaderBaseStyle}>
                      즐겨찾기
                    </div>
                    <div style={{ marginBottom: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {groupedRooms.favorites.map(room => renderRoomItem(room))}
                    </div>
                  </>
                )}

                {/* 오늘 섹션 */}
                {groupedRooms.today.length > 0 && (
                  <>
                    <div style={getStyle()}>
                      오늘
                    </div>
                    <div style={{ marginBottom: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {groupedRooms.today.map(room => renderRoomItem(room))}
                    </div>
                  </>
                )}

                {/* 어제 섹션 */}
                {groupedRooms.yesterday.length > 0 && (
                  <>
                    <div style={getStyle()}>
                      어제
                    </div>
                    <div style={{ marginBottom: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {groupedRooms.yesterday.map(room => renderRoomItem(room))}
                    </div>
                  </>
                )}

                {/* 이번 주 섹션 */}
                {groupedRooms.thisWeek.length > 0 && (
                  <>
                    <div style={getStyle()}>
                      이번 주
                    </div>
                    <div style={{ marginBottom: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {groupedRooms.thisWeek.map(room => renderRoomItem(room))}
                    </div>
                  </>
                )}

                {/* 오래전 섹션 */}
                {groupedRooms.older.length > 0 && (
                  <>
                    <div style={getStyle()}>
                      오래전
                    </div>
                    <div style={{ marginBottom: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {groupedRooms.older.map(room => renderRoomItem(room))}
                    </div>
                  </>
                )}
              </>
            );
          })()
        )}
      </div>
      </div>
    </SidebarShell>
  );
}

export default ChatRoomList;
