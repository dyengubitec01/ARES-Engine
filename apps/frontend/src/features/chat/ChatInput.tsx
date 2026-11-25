// created by ARES team [2025-12-15]
import { useState, FormEvent, KeyboardEvent, useRef, useEffect } from 'react';
import { chatSendIcon } from '../../assets/chats';

interface ChatInputProps {
  onSendMessage: (message: string) => void;
  disabled?: boolean;
  variant?: 'default' | 'centered';
  refill?: { value: string; key: number } | null;
}

function ChatInput({ onSendMessage, disabled, variant = 'default', refill }: ChatInputProps) {
  const [inputValue, setInputValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const isCentered = variant === 'centered';

  // textarea 높이 자동 조정
  const adjustTextareaHeight = (): void => {
    if (textareaRef.current) {
      textareaRef.current.style.height = '0px';
      textareaRef.current.style.height = textareaRef.current.scrollHeight + 'px';
    }
  };

  // inputValue 변경 시 높이 조정
  useEffect(() => {
    adjustTextareaHeight();
  }, [inputValue]);

  // 컴포넌트 마운트 시 자동 포커스
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.focus();
    }
  }, []);

  // 실패한 메시지 자동 복원 (입력창이 비어있을 때만)
  useEffect(() => {
    if (!refill) return;
    setInputValue(prev => {
      if (prev !== '') return prev;
      requestAnimationFrame(() => {
        if (textareaRef.current) {
          textareaRef.current.focus();
          const len = refill.value.length;
          textareaRef.current.setSelectionRange(len, len);
        }
      });
      return refill.value;
    });
    // refill.key 변경시만 실행 의도 (새 실패 메시지일 때만 복원, value는 key와 함께 갱신됨)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refill?.key]);

  const handleSubmit = (e: FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    if (inputValue.trim() && !disabled) {
      onSendMessage(inputValue.trim());
      setInputValue('');
      // 높이 초기화 및 포커스
      if (textareaRef.current) {
        textareaRef.current.style.height = '48px';
        textareaRef.current.focus();
      }
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>): void => {
    // Shift + Enter: 줄바꿈, Enter만: 전송
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (inputValue.trim() && !disabled) {
        onSendMessage(inputValue.trim());
        setInputValue('');
        // 높이 초기화 및 포커스
        if (textareaRef.current) {
          textareaRef.current.style.height = '48px';
          textareaRef.current.focus();
        }
      }
    }
  };
  return (
    <div style={{
      padding: isCentered ? '0' : '20px 0',
      background: 'transparent',
      display: 'flex',
      justifyContent: 'center',
      width: '100%'
    }}>
      <form 
        onSubmit={handleSubmit}
        style={{
          width: '100%',
          maxWidth: isCentered ? '640px' : '792px',
          display: 'flex',
          justifyContent: 'center'
        }}
      > 
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          border: '1px solid var(--color-grayscale-200)',
          borderRadius: '16px',
          backgroundColor: 'var(--color-grayscale-50)',
          boxShadow: '2px 2px 12px 0 rgba(0, 0, 0, 0.05)',
          transition: 'border-color 0.2s',
          justifyContent: 'center',
          position: 'relative',
          width: '100%',
          margin: '0 auto',
          minHeight: isCentered ? '180px' : '140px'
        }}>
          
          <textarea
            ref={textareaRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="무엇이든 물어보세요 ..."
            rows={1}
            style={{
              width: '100%',
              padding: isCentered ? '24px 30px' : '10px 30px 8px 30px',
              fontSize: '14px',
              border: 'none',
              resize: 'none',
              outline: 'none',
              lineHeight: '20px',
              letterSpacing: '-0.28px',
              minHeight: isCentered ? '94px' : '48px',
              overflow: 'hidden',
              color: 'var(--color-grayscale-900)',
              backgroundColor: 'transparent'
            }}
          />
  
          {/* 전송 버튼 */}
          <div style={{
            display: 'flex',
            justifyContent: 'flex-end',
            alignItems: 'center',
            padding: isCentered ? '24px 30px' : '10px 30px',
          }}>
            <button
              type="submit"
              disabled={!inputValue.trim() || disabled}
              style={{
                padding: '10px 24px',
                backgroundColor: inputValue.trim() && !disabled ? '#626BF7' : '#B4BDFA',
                color: '#FFF',
                border: 'none',
                borderRadius: '50px',
                cursor: inputValue.trim() && !disabled ? 'pointer' : 'not-allowed',
                transition: 'all 0.2s',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <img src={chatSendIcon} alt="전송" style={{width: '32px', height: '16px'}}/>
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}

export default ChatInput;
