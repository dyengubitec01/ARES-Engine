import type { CSSProperties, ReactNode } from 'react';
import Checkbox from '../../components/common/Checkbox';

export interface ApprovalTableColumn<T> {
  key: string;
  label: string;
  headerStyle?: CSSProperties;
  cellStyle?: CSSProperties;
  render: (item: T) => ReactNode;
}

const headerCellStyle: CSSProperties = {
  backgroundColor: 'var(--color-grayscale-150)',
  padding: '10px 20px',
  fontSize: '13px',
  fontWeight: '500',
  color: 'var(--color-grayscale-900)',
  textAlign: 'center',
  whiteSpace: 'nowrap',
};

const bodyCellStyle: CSSProperties = {
  padding: '12px',
  fontSize: '13px',
  color: 'var(--color-grayscale-600)',
  textAlign: 'center',
  borderBottom: '1px solid var(--color-grayscale-150)',
};

interface ApprovalTableShellProps<T> {
  items: T[];
  getItemId: (item: T) => string;
  selectedIds: string[];
  onToggleAll: (checked: boolean) => void;
  onToggleOne: (id: string) => void;
  columns: ApprovalTableColumn<T>[];
}

function ApprovalTableShell<T>({
  items,
  getItemId,
  selectedIds,
  onToggleAll,
  onToggleOne,
  columns,
}: ApprovalTableShellProps<T>) {
  const allSelected = items.length > 0 && items.every(item => selectedIds.includes(getItemId(item)));

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', tableLayout: 'auto', borderCollapse: 'separate', borderSpacing: 0, backgroundColor: 'transparent' }}>
        <thead>
          <tr style={{ height: '36px' }}>
            <th style={{ ...headerCellStyle, width: '1%', whiteSpace: 'nowrap', borderTopLeftRadius: '10px' }}>
              <Checkbox
                checked={allSelected}
                onChange={(e) => onToggleAll(e.target.checked)}
                title="전체 선택"
              />
            </th>
            {columns.map((col, idx) => (
              <th
                key={col.key}
                style={{
                  ...headerCellStyle,
                  ...col.headerStyle,
                  ...(idx === columns.length - 1 ? { borderTopRightRadius: '10px' } : {}),
                }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const id = getItemId(item);
            const isSelected = selectedIds.includes(id);
            return (
              <tr
                key={id}
                style={{
                  backgroundColor: isSelected ? 'var(--color-primary-600-100)' : 'transparent',
                  transition: 'background-color 0.2s',
                }}
              >
                <td style={{ ...bodyCellStyle, width: '1%', whiteSpace: 'nowrap' }}>
                  <Checkbox
                    checked={isSelected}
                    onChange={() => onToggleOne(id)}
                  />
                </td>
                {columns.map((col) => (
                  <td key={col.key} style={{ ...bodyCellStyle, ...col.cellStyle }}>
                    {col.render(item)}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default ApprovalTableShell;