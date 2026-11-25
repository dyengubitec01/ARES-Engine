// created by ARES team [2025-12-15]
import { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import axios from 'axios';
import { useAuth } from '../features/auth/AuthContext';
import { useChatRooms } from '../features/chat/ChatRoomsContext';
import { useAppSidebar } from '../components/AppSidebar';
import { useModal } from '../contexts/ModalContext';
import PageLayout from '../layouts/PageLayout';
import ChatMessageList from '../features/chat/ChatMessageList';
import ChatInput from '../features/chat/ChatInput';
import { ChatMessage } from '../features/chat/types';
import { logoGif } from '../assets/icons';
import { serviceErrorIcon } from '../assets/errors';
import {
  sendPromptWithSSE,
  SourceDocument,
  getChatMessages,
  isValidUUID,
  getInteractionDocuments,
  sendFeedback
} from '../services/chat.service';
import { createCustomError, getUserFriendlyMessage } from '../lib/customError';
import { CHAT_CODES } from '../constants/customCodes';
import UpdateNoticeModal from '../components/common/UpdateNoticeModal';

function ChatPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const { roomId } = useParams<{ roomId?: string }>();
  const { loadChatRooms } = useChatRooms();
  const { showAlert } = useModal();

  // activeRoomId는 URL 파라미터와 동기화
  const activeRoomId = roomId;
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  
  // SSE 스트리밍 중단을 위한 AbortController
  const abortControllerRef = useRef<AbortController | null>(null);

  // 대화 내역 로드 중단을 위한 AbortController
  const loadHistoryAbortControllerRef = useRef<AbortController | null>(null);

  // AI 응답 실패 인라인 에러 (빈 응답 / SSE 에러)
  const [inlineError, setInlineError] = useState<boolean>(false);
  const inlineErrorTimerRef = useRef<number | null>(null);

  // 메시지 전송 실패 시 입력창 복원 트리거
  const [refillInput, setRefillInput] = useState<{ value: string; key: number } | null>(null);

  const showInlineError = (): void => {
    setInlineError(true);
    if (inlineErrorTimerRef.current !== null) {
      window.clearTimeout(inlineErrorTimerRef.current);
    }
    inlineErrorTimerRef.current = window.setTimeout(() => {
      setInlineError(false);
      inlineErrorTimerRef.current = null;
    }, 4000);
  };

  const clearInlineError = (): void => {
    if (inlineErrorTimerRef.current !== null) {
      window.clearTimeout(inlineErrorTimerRef.current);
      inlineErrorTimerRef.current = null;
    }
    setInlineError(false);
  };
  
  // 새 채팅방 환영 메시지 (사용자 이름 포함)
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  
  // AI 생각 중 상태 (thought) - 누적 배열
  const [thoughtContents, setThoughtContents] = useState<string[]>([]);
  const [thoughtElapsed, setThoughtElapsed] = useState<number | null>(null);
  const thoughtStartRef = useRef<number | null>(null);
  const [streamingMessage, setStreamingMessage] = useState<string>('');
  
  const [, setSources] = useState<SourceDocument[]>([]);

  // user 정보 로드 후 첫 메시지
  useEffect(() => {
    if (user && messages.length === 0) {
      setMessages([
        {
          id: '1',
          role: 'assistant',
          content: `안녕하세요 ${user.name}님,`,
          timestamp: new Date().toISOString(),
          feedback: null
        }
      ]);
    }
    // user 로드 시 환영 메시지 1회 표시 의도 (messages.length === 0 가드로 중복 방지)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  useEffect(() => {
    return () => {
      // 컴포넌트 언마운트 시 모든 진행 중인 요청 취소
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      if (loadHistoryAbortControllerRef.current) {
        loadHistoryAbortControllerRef.current.abort();
      }
      if (inlineErrorTimerRef.current !== null) {
        window.clearTimeout(inlineErrorTimerRef.current);
      }
    };
  }, []);

  // roomId 변경 시 대화 내역 로드
  useEffect(() => {
    const loadChatHistory = async () => {
      // roomId가 없거나 유효하지 않은 경우
      if (!roomId) {
        setMessages([]);
        return;
      }

      if (!isValidUUID(roomId)) {
        console.error('잘못된 채팅방 ID:', roomId);
        await showAlert('잘못된 채팅방', getUserFriendlyMessage(createCustomError(CHAT_CODES.CHAT_INVALID_ROOM_UUID)), '확인');
        navigate('/chat');
        return;
      }
      setMessages([]);
      setIsLoadingHistory(true);

      // 2. 이전 대화 내역 로드 요청이 있다면 취소
      if (loadHistoryAbortControllerRef.current) {
        loadHistoryAbortControllerRef.current.abort();
      }

      // 3. 새로운 AbortController 생성
      const abortController = new AbortController();
      loadHistoryAbortControllerRef.current = abortController;

      // 4. 현재 요청의 roomId를 클로저에 저장 (응답 검증용)
      const requestRoomId = roomId;

      try {
        // 5. API 호출 (AbortSignal 포함)
        const messagesResponse = await getChatMessages(requestRoomId, undefined, abortController.signal);
        
        // 6. 응답 유효성 검사 (Guard Logic)
        // API 응답이 도착한 시점에 여전히 같은 방인지 확인
        if (requestRoomId !== roomId) {
          return;
        }

        // 7. AbortController가 취소되었는지 확인
        if (abortController.signal.aborted) {
          return;
        }

        if (messagesResponse.data?.items && messagesResponse.data.items.length > 0) {
          const loadedMessages: ChatMessage[] = messagesResponse.data.items.map(message => {
            const role = message.type === 'Q' ? 'user' : 'assistant';
            let timestamp: string;
            try {
              timestamp = new Date(message.createdAt).toISOString();
            } catch {
              timestamp = new Date().toISOString();
            }
            
            const feedback = message.feedback === 'Y' ? ('like' as const) : message.feedback === 'N' ? ('dislike' as const) : null;
            
            return {
              id: message.id,
              role,
              content: message.content,
              timestamp,
              feedback
            };
          });
          
          // 8. 최종 검증 후 메시지 설정
          if (requestRoomId === roomId && !abortController.signal.aborted) {
            setMessages(loadedMessages);
            
            // AI 답변 메시지들의 참조 문서 제목 로드 (병렬 처리)
            const aiMessages = loadedMessages.filter(msg => msg.role === 'assistant');
            
            const documentPromises = aiMessages.map(async (aiMessage) => {
              try {
                const docsResponse = await getInteractionDocuments(aiMessage.id);
                
                if (docsResponse.data && docsResponse.data.length > 0) {
                  const referenceTitles = docsResponse.data
                    .map(item => item.docContent?.originalFilename)
                    .filter((title): title is string => !!title)
                    .filter((title, index, self) => self.indexOf(title) === index);
                  
                  const referenceSources = docsResponse.data
                    .map(item => ({
                      doc_title: item.docContent?.originalFilename || '',
                      doc_id: item.docContent?.id || '',
                      location: item.location
                    }))
                    .filter(source => source.doc_title && source.doc_id)
                    .filter((source, index, self) => 
                      self.findIndex(s => s.doc_title === source.doc_title && s.doc_id === source.doc_id) === index
                    );
                  
                  return { 
                    messageId: aiMessage.id, 
                    referenceTitles: referenceTitles.length > 0 ? referenceTitles : undefined,
                    referenceSources: referenceSources.length > 0 ? referenceSources : undefined
                  };
                }
                return null;
              } catch {
                return null;
              }
            });
            
            const results = await Promise.all(documentPromises);
            
            // 9. 참조 문서 업데이트 시에도 roomId 검증
            if (requestRoomId === roomId && !abortController.signal.aborted) {
              setMessages(prevMessages => {
                let updatedMessages = [...prevMessages];
                results.forEach(result => {
                  if (result) {
                    updatedMessages = updatedMessages.map(msg =>
                      msg.id === result.messageId
                        ? { 
                            ...msg, 
                            referenceTitles: result.referenceTitles,
                            referenceSources: result.referenceSources
                          }
                        : msg
                    );
                  }
                });
                return updatedMessages;
              });
            }
          }
        } else {
          // 대화 내역이 없는 경우 환영 메시지 표시
          if (user && requestRoomId === roomId && !abortController.signal.aborted) {
            setMessages([
              {
                id: Date.now().toString(),
                role: 'assistant',
                content: `안녕하세요 ${user.name}님`,
                timestamp: new Date().toISOString(),
                feedback: null
              }
            ]);
          }
        }
      } catch (error: unknown) {
        // Abort 에러는 정상적인 흐름이므로 조용히 처리
        if (error instanceof Error && (error.name === 'AbortError' || error.name === 'CanceledError')) {
          return;
        }

        if (axios.isAxiosError(error)) {
          // 403 에러 - 접근 권한 없음
          if (error.response?.status === 403) {
            navigate('/error', { replace: true });
            return;
          }

          // 404 에러 또는 채팅방이 존재하지 않는 경우
          if (error.response?.status === 404 || error.response?.status === 400) {
            const errorToShow = error.userMessage ? error : createCustomError(CHAT_CODES.CHAT_ROOM_NOT_FOUND);
            await showAlert('채팅방 오류', getUserFriendlyMessage(errorToShow), '확인');
            navigate('/chat');
            return;
          }
        }
        
        // 기타 에러 발생 시 환영 메시지 표시 (여전히 같은 방인 경우에만)
        if (user && requestRoomId === roomId) {
          setMessages([
            {
              id: Date.now().toString(),
              role: 'assistant',
              content: `안녕하세요, ${user.name}님`,
              timestamp: new Date().toISOString(),
              feedback: null
            }
          ]);
        }
      } finally {
        // 10. 로딩 상태 해제 (여전히 같은 방인 경우에만)
        if (requestRoomId === roomId) {
          setIsLoadingHistory(false);
        }
      }
    };

    loadChatHistory();

    // Cleanup 함수: roomId가 변경되면 이전 요청 취소
    return () => {
      if (loadHistoryAbortControllerRef.current) {
        loadHistoryAbortControllerRef.current.abort();
      }
    };
    // roomId/user/navigate 변경시만 실행 의도 (showAlert는 useModal Provider에서 안정적 참조)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [roomId, user, navigate]);

  const handleSendMessage = async (content: string): Promise<void> => {
    if (!user) {
      await showAlert('오류', getUserFriendlyMessage(createCustomError(CHAT_CODES.CHAT_EMPTY_MESSAGE, '사용자 정보를 불러올 수 없습니다.')), '확인');
      return;
    }

    try {
      clearInlineError();

      const userMessage: ChatMessage = {
        id: Date.now().toString(),
        role: 'user',
        content: content,
        timestamp: new Date().toISOString()
      };

      setMessages(prev => [...prev, userMessage]);
      setIsLoading(true);
      setIsThinking(false);
      setThoughtContents([]);
      setThoughtElapsed(null);
      thoughtStartRef.current = null;
      setStreamingMessage('');
      setSources([]);

      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      await sendPromptWithSSE(
        activeRoomId,
        content,
        {
          onConnected: (newSessionId: string) => {
            navigate(`/chat/${newSessionId}`, { replace: true });
            loadChatRooms();
          },

          onThought: (thought: string) => {
            setIsThinking(true);
            if (thoughtStartRef.current === null) {
              thoughtStartRef.current = Date.now();
            }
            setThoughtContents(prev => {
              const updated = [...prev, thought];
              if (updated.length >= 2) {
                setThoughtElapsed(Math.round((Date.now() - thoughtStartRef.current!) / 1000));
              }
              return updated;
            });
          },

          onMessage: (messageContent: string) => {

            setIsThinking(false);

            setStreamingMessage(prev => {
              const updated = prev + messageContent;
              return updated;
            });
          },

          onDone: (sourceDocs: SourceDocument[]) => {
            
            const referenceTitles = sourceDocs
              .map(doc => doc.doc_title)
              .filter((title, index, self) => self.indexOf(title) === index);
            
            const referenceSources = sourceDocs
              .map(doc => ({
                doc_title: doc.doc_title,
                doc_id: doc.doc_id,
                location: doc.location
              }))
              .filter((source, index, self) => 
                self.findIndex(s => s.doc_title === source.doc_title && s.doc_id === source.doc_id) === index
              );
            
            setStreamingMessage(currentStreamingMsg => {
              if (!currentStreamingMsg || currentStreamingMsg.trim().length === 0) {
                console.error('[SSE] Empty response detected - no message content received');
                showInlineError();

                setIsThinking(false);
                setThoughtContents([]);
                setIsLoading(false);

                return '';
              }
              
              const assistantMessage: ChatMessage = {
                id: Date.now().toString(),
                role: 'assistant',
                content: currentStreamingMsg,
                timestamp: new Date().toISOString(),
                feedback: null,
                referenceTitles: referenceTitles.length > 0 ? referenceTitles : undefined,
                referenceSources: referenceSources.length > 0 ? referenceSources : undefined
              };
              
              setMessages(prev => [...prev, assistantMessage]);
              
              return '';
            });
            
            setSources(sourceDocs);
            
            setIsThinking(false);
            setIsLoading(false);
          },

          onError: () => {
            showInlineError();

            setIsThinking(false);
            setStreamingMessage('');
            setThoughtContents([]);
            setIsLoading(false);
          }
        },
        abortController.signal
      );
    } catch {
      setMessages(prev => {
        const lastUserIdx = prev.map(m => m.role).lastIndexOf('user');
        if (lastUserIdx === -1) return prev;
        return prev.map((m, i) =>
          i === lastUserIdx ? { ...m, error: '메시지를 전송하지 못했습니다' } : m
        );
      });
      setRefillInput({ value: content, key: Date.now() });

      setIsThinking(false);
      setStreamingMessage('');
      setThoughtContents([]);
      setIsLoading(false);
    }
  };

  const handleRoomSelect = (roomId: string): void => {
    // 진행 중인 스트리밍 중단
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // 진행 중인 대화 내역 로드 중단
    if (loadHistoryAbortControllerRef.current) {
      loadHistoryAbortControllerRef.current.abort();
    }

    // 상태 초기화
    setIsLoading(false);
    setThoughtContents([]);
    setStreamingMessage('');
    setSources([]);
    navigate(`/chat/${roomId}`);
  };

  const handleNewChat = async (): Promise<void> => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    if (loadHistoryAbortControllerRef.current) {
      loadHistoryAbortControllerRef.current.abort();
    }
    
    setIsLoading(false);
    setThoughtContents([]);
    setStreamingMessage('');
    setSources([]);
    
    if (user) {
      setMessages([
        {
          id: Date.now().toString(),
          role: 'assistant',
          content: `안녕하세요, ${user.name}님`,
          timestamp: new Date().toISOString(),
          feedback: null
        }
      ]);
    }

    navigate('/chat');
  };

  const handleFeedback = async (messageId: string, feedback: 'like' | 'dislike'): Promise<'like' | 'dislike' | null> => {
    const apiFeedback = feedback === 'like' ? 'Y' : 'N';

    const result = await sendFeedback(messageId, apiFeedback);
    const responseFeedback = result.data.feedback === 'Y' ? 'like' as const
      : result.data.feedback === 'N' ? 'dislike' as const
      : null;

    setMessages(prev =>
      prev.map(msg =>
        msg.id === messageId
          ? { ...msg, feedback: responseFeedback }
          : msg
      )
    );

    return responseFeedback;
  };

  // AppSidebar 설정
  const sidebar = useAppSidebar({
    activeRoomId,
    onRoomSelect: handleRoomSelect,
    onNewChat: handleNewChat,
  });

  // 새 채팅 화면 여부 체크
  const isNewChatScreen = activeRoomId && messages.length === 1 && messages[0].role === 'assistant';

  return (
    <PageLayout
      sidebarContent={sidebar.sidebarContent}
      sidebarHeaderActions={sidebar.headerActions}
      sidebarHeaderTrailingActions={sidebar.headerTrailingActions}
      sidebarActions={sidebar.sidebarActions}
    >
      {!activeRoomId ? (
        // 채팅방 선택 안 됨 - 안내 화면
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '40px 20px'
        }}>
          <div style={{
            textAlign: 'center',
            marginBottom: '48px'
          }}>
            <div style={{
              width: '126px',
              height: '126px',
              margin: '0 auto 24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <img 
                src={logoGif} 
                alt="ARES Logo" 
                style={{
                  width: '126px',
                  height: '126px',
                  objectFit: 'contain'
                }}
              />
            </div>
            <h1 style={{
              fontSize: '40px',
              color: 'var(--color-grayscale-900)',
              fontWeight: '700',
              lineHeight: '48px',
              letterSpacing: '-0.8px',
            }}>
              {user ? `안녕하세요 ${user.name}님,` : '안녕하세요'}
            </h1>
            <p style={{
              fontSize: '40px',
              fontWeight: '700',
              lineHeight: '48px',
              letterSpacing: '-0.8px',
              background: 'linear-gradient(127deg, var(--color-primary-600) 4.33%, var(--color-primary-600) 20%, var(--color-primary-600-400) 88%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              margin: '0'
            }}>
              지금 무슨 생각을 하시나요?
            </p>
          </div>

          <div style={{ width: '100%', maxWidth: '640px' }}>
            <ChatInput
              onSendMessage={handleSendMessage}
              disabled={isLoading}
              variant="centered"
              refill={refillInput}
            />
          </div>
        </div>
      ) : isNewChatScreen ? (
        // 새 채팅 화면
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '40px 20px'
        }}>
          {/* 환영 메시지 */}
          <div style={{
            textAlign: 'center',
            marginBottom: '48px'
          }}>
            <div style={{
              width: '80px',
              height: '80px',
              margin: '0 auto 24px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <img 
                src={logoGif} 
                alt="ARES Logo" 
                style={{
                  width: '126px',
                  height: '126px',
                  objectFit: 'contain'
                }}
              />
            </div>
            <h1 style={{
              fontSize: '40px',
              margin: '0',
              color: 'var(--color-grayscale-900)',
              fontWeight: '700',
              lineHeight: '48px',
              letterSpacing: '-0.8px',
            }}>
              {messages[0]?.content || (user ? `안녕하세요 ${user.name}님,` : '안녕하세요')}
            </h1>
            <p style={{
              fontSize: '40px',
              fontWeight: '700',
              lineHeight: '48px',
              letterSpacing: '-0.8px',
              background: 'linear-gradient(127deg, var(--color-primary-600) 4.33%, var(--color-primary-600) 20%, var(--color-primary-600-400) 88%)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text',
              margin: '0'
            }}>
              지금 무슨 생각을 하시나요?
            </p>
          </div>

          <div style={{ width: '100%', maxWidth: '640px' }}>
            <ChatInput
              onSendMessage={handleSendMessage}
              disabled={isLoading}
              variant="centered"
              refill={refillInput}
            />
          </div>
          </div>
      ) : (
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          overflow: 'hidden',
          width: '100%',
          margin: '0 auto'
        }}>
          <div style={{ 
            width: '100%', 
            maxWidth: '792px',
            display: 'flex', 
            flexDirection: 'column', 
            height: '100%' 
            }}>
              <ChatMessageList 
              messages={messages} 
              isLoading={isLoading}
              onFeedback={handleFeedback}
              thoughtContents={thoughtContents}
              thoughtElapsed={thoughtElapsed}
              streamingMessage={streamingMessage}
              isLoadingHistory={isLoadingHistory}
              isThinking={isThinking}
          />
          <div style={{ width: '100%' }}>
            {inlineError && (
              <div style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '16px',
                marginBottom: '40px',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <img src={serviceErrorIcon} alt="" style={{ width: '20px', height: '20px' }} />
                  <span style={{
                    color: 'var(--color-error-500)',
                    fontSize: '14px',
                    fontStyle: 'normal',
                    fontWeight: 500,
                    lineHeight: '20px',
                    letterSpacing: '-0.28px',
                  }}>
                    AI 응답을 생성하지 못했습니다
                  </span>
                </div>
                <div style={{
                  color: 'var(--color-grayscale-400)',
                  textAlign: 'center',
                  fontSize: '14px',
                  fontStyle: 'normal',
                  fontWeight: 500,
                  lineHeight: '20px',
                  letterSpacing: '-0.28px',
                }}>
                  요청 처리 중 오류가 발생했습니다.<br />
                  다시 질문하거나 잠시 후 시도해주세요
                </div>
              </div>
            )}
            <ChatInput onSendMessage={handleSendMessage} disabled={isLoading || isLoadingHistory} refill={refillInput} />
          </div>
            </div>
        </div>
      )}
      <UpdateNoticeModal />
    </PageLayout>
  );
}

export default ChatPage;
