// created by ARES team [2026-02-23]
import { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChatRoom } from './types';
import { useModal } from '../../contexts/ModalContext';
import {
  getChatSessions,
  toggleChatSessionFavorite,
  updateChatSessionTitle,
  deleteChatSession
} from '../../services/chat.service';
import { createCustomError, getUserFriendlyMessage } from '../../lib/customError';
import { CHAT_CODES } from '../../constants/customCodes';
import type { ToastItem } from '../../components/common/Toast';

interface ChatRoomsContextType {
  rooms: ChatRoom[];
  filteredRooms: ChatRoom[];
  isLoading: boolean;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  loadChatRooms: () => Promise<void>;
  toggleFavorite: (roomId: string) => Promise<void>;
  renameRoom: (roomId: string, newTitle: string) => Promise<void>;
  deleteRoom: (roomId: string, currentActiveRoomId?: string) => Promise<void>;
  errorToasts: ToastItem[];
  clearErrorToast: (id: string) => void;
}

const ChatRoomsContext = createContext<ChatRoomsContextType | undefined>(undefined);

export function ChatRoomsProvider({ children }: { children: ReactNode }) {
  const [rooms, setRooms] = useState<ChatRoom[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [errorToasts, setErrorToasts] = useState<ToastItem[]>([]);
  const { showConfirm } = useModal();
  const navigate = useNavigate();

  const clearErrorToast = useCallback((id: string) => {
    setErrorToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  // 필터링된 채팅방 목록 (제목 검색어 적용)
  const filteredRooms = searchQuery.trim() === ''
    ? rooms
    : rooms.filter(room =>
        room.title.toLowerCase().includes(searchQuery.trim().toLowerCase())
      );

  // 채팅방 목록 로드
  const loadChatRooms = useCallback(async () => {
    try {
      setIsLoading(true);
      const response = await getChatSessions();
      
      const mappedRooms: ChatRoom[] = response.data.items.map(session => ({
        id: session.id,
        title: session.title || '새로운 대화',
        lastMessage: undefined,
        lastMessageTime: session.createdAt,
        unreadCount: 0,
        isFavorite: session.favorites === 'Y'
      }));
      
      // 시간순 정렬
      mappedRooms.sort((a, b) => {
        const timeA = new Date(a.lastMessageTime || 0).getTime();
        const timeB = new Date(b.lastMessageTime || 0).getTime();
        return timeB - timeA;
      });
      
      setRooms(mappedRooms);
    } catch {
      // apiClient 인터셉터에서 로깅됨
    } finally {
      setIsLoading(false);
    }
  }, []);

  // 초기 로드
  useEffect(() => {
    loadChatRooms();
  }, [loadChatRooms]);

  // 즐겨찾기 토글
  const toggleFavorite = useCallback(async (roomId: string) => {
    const previousRooms = [...rooms];
    
    try {
      // 낙관적 업데이트
      setRooms(prev => 
        prev.map(room => 
          room.id === roomId 
            ? { ...room, isFavorite: !room.isFavorite }
            : room
        )
      );

      const response = await toggleChatSessionFavorite(roomId);
      
      // 서버 응답으로 최종 업데이트
      setRooms(prev =>
        prev.map(room =>
          room.id === roomId
            ? { ...room, isFavorite: response.data.favorites === 'Y' }
            : room
        )
      );
    } catch {
      setErrorToasts(prev => [...prev, { id: Date.now().toString(), title: '즐겨찾기 실패', message: getUserFriendlyMessage(createCustomError(CHAT_CODES.CHAT_FAVORITE_TOGGLE_FAILED)) }]);
      // 롤백
      setRooms(previousRooms);
    }
  }, [rooms]);

  // 채팅방 이름 변경
  const renameRoom = useCallback(async (roomId: string, newTitle: string) => {
    const previousRooms = [...rooms];
    
    try {
      // 낙관적 업데이트
      setRooms(prev =>
        prev.map(room =>
          room.id === roomId
            ? { ...room, title: newTitle }
            : room
        )
      );

      await updateChatSessionTitle(roomId, newTitle);

      // 목록 재로드
      await loadChatRooms();
    } catch (error) {
      // 롤백
      setRooms(previousRooms);
      throw error;
    }
  }, [rooms, loadChatRooms]);

  // 채팅방 삭제
  const deleteRoom = useCallback(async (roomId: string, currentActiveRoomId?: string) => {
    showConfirm(
      '채팅을 삭제하시겠습니까?',
      '삭제된 채팅은 복구할 수 없습니다.',
      async () => {
        const previousRooms = [...rooms];

        try {
          // 낙관적 업데이트
          setRooms(prev => prev.filter(room => room.id !== roomId));

          await deleteChatSession(roomId);
          
          // 현재 보고 있는 채팅방을 삭제한 경우 /chat으로 리다이렉트
          if (currentActiveRoomId && currentActiveRoomId === roomId) {
            navigate('/chat');
          }
          
          // 목록 재로드
          await loadChatRooms();
        } catch (error) {
          setErrorToasts(prev => [...prev, { id: Date.now().toString(), title: '삭제 실패', message: getUserFriendlyMessage(createCustomError(CHAT_CODES.CHAT_ROOM_DELETE_FAILED)) }]);
          // 롤백
          setRooms(previousRooms);
          throw error;
        }
      },
      '삭제',
      '취소',
      'var(--color-error-500)'
    );
  }, [rooms, loadChatRooms, showConfirm, navigate]);

  const value: ChatRoomsContextType = {
    rooms,
    filteredRooms,
    isLoading,
    searchQuery,
    setSearchQuery,
    loadChatRooms,
    toggleFavorite,
    renameRoom,
    deleteRoom,
    errorToasts,
    clearErrorToast,
  };

  return (
    <ChatRoomsContext.Provider value={value}>
      {children}
    </ChatRoomsContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useChatRooms() {
  const context = useContext(ChatRoomsContext);
  if (context === undefined) {
    throw createCustomError(
      CHAT_CODES.CHAT_ROOM_LIST_LOAD_FAILED,
      'useChatRooms must be used within a ChatRoomsProvider'
    );
  }
  return context;
}
