interface ActionButton {
  label: string;
  onClick: () => void;
  width?: string;
}

interface SelectionActionBarProps {
  selectedCount: number;
  actions: ActionButton[];
  onClear: () => void;
}

function SelectionActionBar({ selectedCount, actions, onClear }: SelectionActionBarProps) {
  return (
    <div style={{
      height: '60px',
      borderRadius: '999px',
      background: '#FFFFFF',
      boxShadow: '2px 2px 20px 0 rgba(0, 0, 0, 0.08)',
      display: 'flex',
      alignItems: 'center',
      padding: '0 20px',
      gap: '16px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '16px',
          height: '16px',
          borderRadius: '4px',
          border: '1px solid #626BF7',
          backgroundColor: '#FFFFFF',
          flexShrink: 0,
        }}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2.5 6L5 8.5L9.5 3.5" stroke="#626BF7" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
        <span style={{
          color: '#292B2F',
          fontSize: '14px',
          fontWeight: '500',
          lineHeight: '20px',
          letterSpacing: '-0.28px',
          whiteSpace: 'nowrap',
        }}>
          {selectedCount}개 선택됨
        </span>
      </div>

      <div style={{ width: '1px', height: '24px', background: '#E6E6E6' }} />

      {actions.map((action, idx) => (
        <button
          key={idx}
          onClick={action.onClick}
          style={{
            height: '32px',
            borderRadius: '8px',
            border: 'none',
            background: '#626BF7',
            color: '#FFF',
            fontSize: '14px',
            fontWeight: '600',
            lineHeight: '20px',
            letterSpacing: '-0.28px',
            cursor: 'pointer',
            transition: 'opacity 0.2s',
            whiteSpace: 'nowrap',
            ...(action.width ? { width: action.width } : { padding: '0 12px' }),
          }}
          onMouseOver={(e) => { e.currentTarget.style.opacity = '0.85'; }}
          onMouseOut={(e) => { e.currentTarget.style.opacity = '1'; }}
        >
          {action.label}
        </button>
      ))}

      <div style={{ width: '1px', height: '24px', background: '#E6E6E6' }} />

      <button
        onClick={onClear}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: '#8E8E8E',
          fontSize: '14px',
          fontWeight: '500',
          lineHeight: '20px',
          letterSpacing: '-0.28px',
          whiteSpace: 'nowrap',
          padding: 0,
        }}
      >
        선택 해제
      </button>
    </div>
  );
}

export default SelectionActionBar;
