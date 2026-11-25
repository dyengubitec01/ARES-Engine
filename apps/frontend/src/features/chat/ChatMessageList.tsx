// created by ARES team [2025-12-15]
import { useRef, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Components } from 'react-markdown';
import remarkBreaks from 'remark-breaks';
import remarkGfm from 'remark-gfm';
import { ChatMessage } from './types';
import { feedbackGoodIcon, feedbackBadIcon, thought1Icon, thought2Icon, thought3Icon, thought4Icon } from '../../assets/chats';
import { copyIcon } from '../../assets/icons';
import Skeleton from '../../components/common/Skeleton';
import ActionToast from '../../components/common/ActionToast';
import Toast from '../../components/common/Toast';
import type { ToastItem } from '../../components/common/Toast';
import { downloadDocument } from '../../services/chat.service';
import { useScrollFade } from '../../hooks/useScrollFade';

// ReactMarkdown 공통 컴포넌트 설정
const MARKDOWN_COMPONENTS: Components = {
  p: ({ node, children, ...props }) => {
    // 빈 단락 감지: 순수 텍스트 또는 서식 요소(strong, em 등)가 있으면 내용 있음으로 판단
    const hasContent = node?.children?.some((child: { type?: string; value?: string }) =>
      child.type === 'element' || (child.type === 'text' && child.value?.trim() !== '')
    );
    if (!hasContent) return <div style={{ height: '8px' }} />;
    return <div {...props}>{children}</div>;
  },
  ul: ({ node: _node, ...props }) => <ul style={{ margin: '2px 0', paddingLeft: '20px', lineHeight: '25px' }} {...props} />,
  ol: ({ node: _node, ...props }) => <ol style={{ margin: '2px 0', paddingLeft: '20px', lineHeight: '25px' }} {...props} />,
  li: ({ node: _node, ...props }) => <li style={{ margin: '0 0 6px 0', padding: '0' }} {...props} />,
  strong: ({ node: _node, ...props }) => <strong {...props} />,
  em: ({ node: _node, ...props }) => <em {...props} />,
  code: ({ node: _node, ...props }) => <code style={{ backgroundColor: 'rgba(0,0,0,0.1)', padding: '2px 4px', borderRadius: '3px' }} {...props} />,
  pre: ({ node: _node, ...props }) => <pre style={{ backgroundColor: 'rgba(0,0,0,0.05)', padding: '8px', borderRadius: '4px', overflowX: 'auto', margin: '8px 0' }} {...props} />,
  table: ({ node: _node, ...props }) => <table style={{ borderCollapse: 'collapse', width: '100%', margin: '8px 0', fontSize: '13px' }} {...props} />,
  thead: ({ node: _node, ...props }) => <thead style={{ backgroundColor: 'rgba(0,0,0,0.04)' }} {...props} />,
  th: ({ node: _node, ...props }) => <th style={{ border: '1px solid rgba(0,0,0,0.12)', padding: '6px 10px', textAlign: 'left', fontWeight: 600 }} {...props} />,
  td: ({ node: _node, ...props }) => <td style={{ border: '1px solid rgba(0,0,0,0.12)', padding: '6px 10px' }} {...props} />,
};

// AI 어시스턴트 메시지 버블 스타일 (스트리밍 & 최종 메시지 공통)
const ASSISTANT_MESSAGE_BUBBLE_STYLE: React.CSSProperties = {
  padding: '0 16px',
  borderRadius: '16px',
  backgroundColor: 'transparent',
  color: 'var(--color-grayscale-900)',
  border: 'none',
  wordBreak: 'break-word'
};

// 메시지 텍스트 컨테이너 스타일 (스트리밍 & 최종 메시지 공통)
const MESSAGE_TEXT_STYLE: React.CSSProperties = {
  fontSize: '14px',
  lineHeight: '25px'
};

// FeedbackBtn 컴포넌트
interface FeedbackButtonProps {
  isActive: boolean;
  onClick: () => void;
  icon: string;
}

function FeedbackButton({ isActive, onClick, icon }: FeedbackButtonProps) {
  const [isHovered, setIsHovered] = useState<boolean>(false);

  return (
    <button
      onClick={onClick}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      style={{
        backgroundColor: 'transparent',
        border: 'none',
        borderRadius: '6px',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
        transition: 'all 0.2s'
      }}
    >
      <img
        src={icon}
        style={{
          width: '16px',
          height: '16px',
          filter: isActive ? 'brightness(0.3)' : (isHovered ? 'brightness(0.5)' : 'none'),
          transition: 'filter 0.2s'
        }}
      />
    </button>
  );
}

// 참조 문서 아이템 컴포넌트 (다운로드 가능)
interface DownloadableReferenceItemProps {
  docTitle: string;
  docId: string;
  location?: string;
  onDownloadError: () => void;
}

function DownloadableReferenceItem({ docTitle, docId, onDownloadError }: DownloadableReferenceItemProps) {
  const [isHovered, setIsHovered] = useState(false);

  const handleDownload = async () => {
    try {
      await downloadDocument(docId, docTitle);
    } catch {
      onDownloadError();
    }
  };

  return (
    <div
      style={{
        marginLeft: '8px',
        marginBottom: '2px',
        display: 'flex',
        alignItems: 'center',
        gap: '4px'
      }}
    >
      <span
        style={{
          cursor: 'pointer',
          textDecoration: isHovered ? 'underline' : 'none'
        }}
        onClick={handleDownload}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        - {docTitle}
      </span>
      {/* TODO: 페이지 표시 기능 구현 후 주석 해제 */}
      {/* {location && (
        <span style={{ color: 'var(--color-grayscale-400)' }}>
          | {location}
        </span>
      )} */}
    </div>
  );
}

// 날짜 포맷팅 함수
const formatMessageDate = (timestamp: string): string => {
  try {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      const now = new Date();
      return `${now.getFullYear()}년 ${now.getMonth() + 1}월 ${now.getDate()}일`;
    }
    return `${date.getFullYear()}년 ${date.getMonth() + 1}월 ${date.getDate()}일`;
  } catch {
    const now = new Date();
    return `${now.getFullYear()}년 ${now.getMonth() + 1}월 ${now.getDate()}일`;
  }
};

// 두 날짜가 같은 날인지 비교
const isSameDay = (date1: string, date2: string): boolean => {
  try {
    const d1 = new Date(date1);
    const d2 = new Date(date2);
    if (isNaN(d1.getTime()) || isNaN(d2.getTime())) return false;
    return (
      d1.getFullYear() === d2.getFullYear() &&
      d1.getMonth() === d2.getMonth() &&
      d1.getDate() === d2.getDate()
    );
  } catch {
    return false;
  }
};

interface ChatMessageListProps {
  messages: ChatMessage[];
  isLoading?: boolean;
  onFeedback?: (messageId: string, feedback: 'like' | 'dislike') => Promise<'like' | 'dislike' | null>;
  thoughtContents?: string[];
  thoughtElapsed?: number | null;
  streamingMessage?: string;
  isLoadingHistory?: boolean;
  isThinking?: boolean;
}

function ChatMessageList({ messages, isLoading, onFeedback, thoughtContents, thoughtElapsed, streamingMessage, isLoadingHistory, isThinking }: ChatMessageListProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messageTextRefs = useRef<Map<string, HTMLDivElement>>(new Map());
  const { ref: scrollContainerRef, showTopFade, showBottomFade, handleScroll } = useScrollFade<HTMLDivElement>();
  const [actionToast, setActionToast] = useState<{ visible: boolean; message: string; messageId: string }>({ visible: false, message: '', messageId: '' });
  const [errorToasts, setErrorToasts] = useState<ToastItem[]>([]);

  const handleDownloadError = () => {
    setErrorToasts(prev => [...prev, { id: Date.now().toString(), title: '다운로드 실패', message: '잠시 후 다시 시도해주세요.' }]);
  };

  const showActionToast = (message: string, messageId: string) => {
    setActionToast({ visible: false, message: '', messageId: '' });
    requestAnimationFrame(() => {
      setActionToast({ visible: true, message, messageId });
      requestAnimationFrame(() => {
        const el = scrollContainerRef.current;
        if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
      });
    });
  };

  useEffect(() => {
    handleScroll();
    // 메시지/로딩 상태 변경시만 스크롤 처리 의도 (handleScroll은 useScrollFade 내부에서 관리)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, isLoading, thoughtContents, streamingMessage, isLoadingHistory, isThinking]);

  // 메시지 변경 시 자동 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, thoughtContents, streamingMessage, isLoadingHistory, isThinking]);

  const maskImage = showTopFade && showBottomFade
    ? 'linear-gradient(to bottom, transparent, black 40px, black calc(100% - 40px), transparent)'
    : showTopFade
    ? 'linear-gradient(to bottom, transparent, black 40px)'
    : showBottomFade
    ? 'linear-gradient(to bottom, black calc(100% - 40px), transparent)'
    : undefined;

  return (
    <div style={{ flex: 1, overflow: 'hidden' }}>
    {errorToasts.length > 0 && <Toast variant="error" items={errorToasts} onClose={(id: string) => setErrorToasts(prev => prev.filter(t => t.id !== id))} />}
    <div
      ref={scrollContainerRef}
      onScroll={handleScroll}
      className="hide-scrollbar"
      style={{
      height: '100%',
      overflowY: 'auto',
      maskImage,
      WebkitMaskImage: maskImage,
      padding: 0,
      display: 'flex',
      flexDirection: 'column',
      gap: '28px',
      background: 'transparent',
      width: '100%'
    }}>
      {/* 대화 내역 로딩 중 - 스켈레톤 UI */}
      {isLoadingHistory && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', padding: '20px 0' }}>
          {/* 사용자 메시지 스켈레톤 */}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Skeleton width="45%" height="48px" borderRadius="16px" />
          </div>
          {/* AI 응답 스켈레톤 */}
          <div style={{ display: 'flex', justifyContent: 'flex-start', flexDirection: 'column', gap: '8px' }}>
            <Skeleton width="70%" height="16px" borderRadius="4px" />
            <Skeleton width="60%" height="16px" borderRadius="4px" />
            <Skeleton width="50%" height="16px" borderRadius="4px" />
          </div>
          {/* 사용자 메시지 스켈레톤 */}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Skeleton width="35%" height="48px" borderRadius="16px" />
          </div>
          {/* AI 응답 스켈레톤 */}
          <div style={{ display: 'flex', justifyContent: 'flex-start', flexDirection: 'column', gap: '8px' }}>
            <Skeleton width="65%" height="16px" borderRadius="4px" />
            <Skeleton width="55%" height="16px" borderRadius="4px" />
          </div>
        </div>
      )}

      {/* 빈 대화 내역 안내 */}
      {!isLoadingHistory && messages.length === 0 && (
        <div style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          padding: '40px 20px',
          color: 'var(--color-grayscale-900)',
          fontSize: '14px'
        }}>
          이전 대화가 없습니다. 새로운 메시지를 보내보세요!
        </div>
      )}

      {/* 메시지 목록 */}
      {!isLoadingHistory && messages.map((message, index) => {
        const prevMessage = index > 0 ? messages[index - 1] : null;
        const showDateDivider = !prevMessage || !isSameDay(message.timestamp, prevMessage.timestamp);
        // 마지막 user 메시지 바로 뒤에 thought 표시
        const isLastUserMessage = message.role === 'user' && (index === messages.length - 1 || messages[index + 1]?.role === 'assistant' && index + 1 === messages.length - 1);
        const shouldShowThought = isLastUserMessage && thoughtContents && thoughtContents.length > 0;

        return (
          <div key={message.id}>
            {/* 날짜 구분선 */}
            {showDateDivider && (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                margin: index === 0 ? '0 0 20px 0' : '20px 0',
                gap: '12px'
              }}>
                <div style={{
                  flex: 1,
                  height: '1px',
                  backgroundColor: 'var(--color-grayscale-150)'
                }} />
                <span style={{
                  fontSize: '12px',
                  color: '#9CA3AF',
                  fontWeight: '500',
                  whiteSpace: 'nowrap'
                }}>
                  {formatMessageDate(message.timestamp)}
                </span>
                <div style={{
                  flex: 1,
                  height: '1px',
                  backgroundColor: 'var(--color-grayscale-150)'
                }} />
              </div>
            )}

            {/* 메시지 */}
            <div
              style={{
                display: 'flex',
                justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
                alignItems: 'flex-start',
                gap: '10px'
              }}
            >
              {/* 메시지 버블 및 피드백 */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', ...(message.role === 'user' ? { maxWidth: '70%' } : { width: '100%' }) }}>
                {/* 메시지 버블 */}
                <div
                  style={
                    message.role === 'user'
                      ? {
                          padding: '16px',
                          borderRadius: '16px',
                          backgroundColor: 'var(--color-grayscale-100)',
                          color: 'var(--color-grayscale-900)',
                          border: 'none',
                          wordBreak: 'break-word'
                        }
                      : ASSISTANT_MESSAGE_BUBBLE_STYLE
                  }
                >
                  <div
                    ref={(el) => { if (el) messageTextRefs.current.set(message.id, el); }}
                    className="markdown-content"
                    style={MESSAGE_TEXT_STYLE}
                  >
                    <ReactMarkdown
                      components={MARKDOWN_COMPONENTS}
                      remarkPlugins={[remarkBreaks, [remarkGfm, { singleTilde: false, strikethrough: false }]]}
                    >
                      {message.content}
                    </ReactMarkdown>
                  </div>
                </div>

                {/* 사용자 메시지 전송 실패 에러 */}
                {message.role === 'user' && message.error && (
                  <div style={{
                    color: 'var(--color-error-500)',
                    fontSize: '12px',
                    fontStyle: 'normal',
                    fontWeight: 500,
                    lineHeight: '16px',
                    letterSpacing: '-0.24px',
                    textAlign: 'left',
                    marginTop: '-4px',
                  }}>
                    {message.error}
                  </div>
                )}

                {/* 참조 문서 표시 (AI 답변일 때만) */}
                {message.role === 'assistant' && message.referenceTitles && message.referenceTitles.length > 0 && (
                  <div style={{
                    fontSize: '11px',
                    color: 'var(--color-grayscale-400)',
                    paddingLeft: '4px',
                    marginTop: '-4px'
                  }}>
                    <div style={{ fontWeight: '600', marginBottom: '4px' }}>
                      [참조 문서]
                    </div>
                    {/* referenceSources가 있는 경우 (다운로드 가능 + 페이지 정보 포함) */}
                    {message.referenceSources ? (
                      message.referenceSources.map((source, idx) => (
                        <DownloadableReferenceItem
                          key={idx}
                          docTitle={source.doc_title}
                          docId={source.doc_id}
                          location={source.location}
                          onDownloadError={handleDownloadError}
                        />
                      ))
                    ) : (
                      /* referenceSources가 없는 경우 (다운로드 불가능, 제목만) */
                      message.referenceTitles.map((title, idx) => (
                        <div key={idx} style={{ marginLeft: '8px', marginBottom: '2px' }}>
                          - {title}
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* 복사 & 답변 피드백 */}
                {message.role === 'assistant' && onFeedback && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                      <FeedbackButton
                        isActive={false}
                        onClick={() => {
                          const el = messageTextRefs.current.get(message.id);
                          navigator.clipboard.writeText(el?.innerText ?? message.content);
                          showActionToast('클립보드에 복사됨', message.id);
                        }}
                        icon={copyIcon}
                      />
                      <FeedbackButton
                        isActive={message.feedback === 'like'}
                        onClick={async () => {
                          try {
                            const result = await onFeedback(message.id, 'like');
                            if (result !== null) {
                              showActionToast('감사합니다. 제공해주신 의견은 대영유비텍 LLM을 개선하는 데 도움이 됩니다.', message.id);
                            }
                          } catch {
                            showActionToast('피드백 전송에 실패했습니다. 잠시 후 다시 시도해주세요.', message.id);
                          }
                        }}
                        icon={feedbackGoodIcon}
                      />
                      <FeedbackButton
                        isActive={message.feedback === 'dislike'}
                        onClick={async () => {
                          try {
                            const result = await onFeedback(message.id, 'dislike');
                            if (result !== null) {
                              showActionToast('감사합니다. 제공해주신 의견은 대영유비텍 LLM을 개선하는 데 도움이 됩니다.', message.id);
                            }
                          } catch {
                            showActionToast('피드백 전송에 실패했습니다. 잠시 후 다시 시도해주세요.', message.id);
                          }
                        }}
                        icon={feedbackBadIcon}
                      />
                    </div>
                    {actionToast.visible && actionToast.messageId === message.id && (
                      <ActionToast
                        message={actionToast.message}
                        visible={true}
                        onClose={() => setActionToast({ visible: false, message: '', messageId: '' })}
                      />
                    )}
                  </div>
                )}
              </div>
            </div>

          {/* AI 생각 중 상태 (thought) - 마지막 user 메시지 바로 뒤에 표시 */}
          {shouldShowThought && (
            <div style={{
              marginTop: '28px',
              borderRadius: '4px',
              border: '1px solid var(--color-grayscale-150)',
              background: 'var(--color-grayscale-50)',
              display: 'flex',
              flexDirection: 'column'
            }}>
              {/* 고정 문구 헤더 */}
              <div style={{
                padding: '12px 16px',
                background: 'var(--color-grayscale-100)',
                borderRadius: '4px 4px 0 0',
                color: 'var(--color-grayscale-500)',
                fontSize: '12px',
                fontStyle: 'normal',
                fontWeight: 500,
                lineHeight: '16px',
                letterSpacing: '-0.24px',
              }}>
                {isThinking ? '생각하고 있습니다...' : thoughtElapsed !== null ? `${thoughtElapsed}초 동안 생각했습니다` : '생각했습니다'}
              </div>
              {/* 구분선 */}
              <div style={{ height: '1px', backgroundColor: 'var(--color-grayscale-150)' }} />
              {/* thought 목록 */}
              <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column' }}>
              {thoughtContents!.map((thought, thoughtIndex) => {
                const thoughtIcons = [thought1Icon, thought2Icon, thought3Icon, thought4Icon];
                const isLastThought = thoughtIndex === thoughtContents!.length - 1;
                return (
                  <div key={thoughtIndex}>
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px'
                    }}>
                      {thoughtIndex < thoughtIcons.length && (
                        <img src={thoughtIcons[thoughtIndex]} alt="" style={{ width: '16px', height: '16px', flexShrink: 0 }} />
                      )}
                      <span style={{
                        color: 'var(--color-grayscale-400)',
                        fontSize: '11px',
                        fontStyle: 'normal',
                        fontWeight: 400,
                        lineHeight: '16px',
                      }}>
                        {thought}
                      </span>
                    </div>
                    {!isLastThought && (
                      <div style={{ width: '16px', display: 'flex', justifyContent: 'center', padding: '4px 0' }}>
                        <div style={{ width: '1px', height: '14px', backgroundColor: 'var(--color-grayscale-150)' }} />
                      </div>
                    )}
                  </div>
                );
              })}
              </div>
            </div>
          )}
        </div>
        );
      })}

          {/* AI 답변 스트리밍 중 - streamingMessage가 있을 때 표시 */}
          {streamingMessage && (
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px'
            }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxWidth: '100%' }}>
                <div style={ASSISTANT_MESSAGE_BUBBLE_STYLE}>
                  <div className="markdown-content" style={MESSAGE_TEXT_STYLE}>
                    <ReactMarkdown
                      components={MARKDOWN_COMPONENTS}
                      remarkPlugins={[remarkBreaks, [remarkGfm, { singleTilde: false, strikethrough: false }]]}
                    >
                      {streamingMessage}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 로딩 인디케이터 (스트리밍 시작 전) */}
          {isLoading && !isThinking && (!thoughtContents || thoughtContents.length === 0) && !streamingMessage && (
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '10px'
            }}>
              <div style={{
                padding: '12px 16px',
                backgroundColor: 'transparent',
                border: 'none',
              }}>
                <div style={{ display: 'flex', gap: '5px', alignItems: 'center' }}>
                  <span style={{  fontSize: '11px', color: 'var(--color-grayscale-400)' }}>더 좋은 응답을 위해 생각하는 중</span>
                  <span className="loading-dots">...</span>
                </div>
              </div>
            </div>
          )}

      <div ref={messagesEndRef} />
    </div>
    </div>
  );
}

export default ChatMessageList;
