// created by ARES team [2026-06-15]
import { useRef, useState } from 'react';
import SearchIcon from '../../assets/icons/search.svg?react';

interface DocumentSearchInputProps {
  onValueChange: (value: string) => void;
}

function DocumentSearchInput({ onValueChange }: DocumentSearchInputProps) {
  const [localValue, setLocalValue] = useState('');
  const isComposingRef = useRef(false);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        width: '260px',
        padding: '8px 12px',
        borderRadius: '8px',
        border: '1px solid var(--color-grayscale-200)',
        background: 'var(--color-grayscale-50)',
        marginRight: '8px',
        boxSizing: 'border-box',
      }}
    >
      <SearchIcon
        width={20}
        height={20}
        style={{ flexShrink: 0, color: 'var(--color-grayscale-400)' }}
      />
      <input
        type="text"
        value={localValue}
        onChange={(e) => {
          setLocalValue(e.target.value);
          if (!isComposingRef.current) {
            onValueChange(e.target.value);
          }
        }}
        onCompositionStart={() => {
          isComposingRef.current = true;
        }}
        onCompositionEnd={(e) => {
          isComposingRef.current = false;
          onValueChange((e.target as HTMLInputElement).value);
        }}
        maxLength={100}
        placeholder="문서 파일명 검색"
        style={{
          flex: 1,
          minWidth: 0,
          border: 'none',
          outline: 'none',
          background: 'transparent',
          padding: 0,
          color: 'var(--color-grayscale-900)',
          fontFamily: 'Pretendard',
          fontSize: '14px',
          fontStyle: 'normal',
          fontWeight: 400,
          lineHeight: 'normal',
        }}
      />
    </div>
  );
}

export default DocumentSearchInput;
