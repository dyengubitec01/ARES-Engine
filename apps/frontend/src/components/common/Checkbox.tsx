// 커스텀 체크박스 컴포넌트

import React from 'react';

interface CheckboxProps {
  checked: boolean;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  disabled?: boolean;
  title?: string;
  size?: number;
}

const Checkbox: React.FC<CheckboxProps> = ({
  checked,
  onChange,
  disabled = false,
  title,
  size = 16,
}) => {
  return (
    <label
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: `${size}px`,
        height: `${size}px`,
        cursor: disabled ? 'not-allowed' : 'pointer',
        position: 'relative',
      }}
      title={title}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        style={{
          position: 'absolute',
          opacity: 0,
          width: 0,
          height: 0,
          margin: 0,
        }}
      />
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: `${size}px`,
          height: `${size}px`,
          borderRadius: '4px',
          border: `1px solid ${checked ? 'var(--color-primary-600)' : '#D0D5DD'}`,
          backgroundColor: 'var(--color-grayscale-50)',
          transition: 'border-color 0.2s',
          flexShrink: 0,
        }}
      >
        {checked && (
          <svg
            width={size - 4}
            height={size - 4}
            viewBox="0 0 12 12"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M2.5 6L5 8.5L9.5 3.5"
              stroke="var(--color-primary-600)"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </span>
    </label>
  );
};

export default Checkbox;
