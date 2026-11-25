import { formatFileSize, getFileExtensionUpperCase } from '../../lib/fileUtils';
import { deptAddIcon } from '../../assets/admin';

interface DocumentFileCellProps {
  filename: string;
  fileSize: number | null | undefined;
  tags?: { id: string; name: string; color: string }[];
  onAddTagClick?: () => void;
}

function DocumentFileCell({ filename, fileSize, tags, onAddTagClick }: DocumentFileCellProps) {
  const extension = getFileExtensionUpperCase(filename);
  return (
    <>
      <div style={{
        fontSize: '13px',
        fontStyle: 'normal',
        fontWeight: '500',
        color: 'var(--color-grayscale-900)',
        marginBottom: '2px',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
      }}>
        {filename}
      </div>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '12px',
        minWidth: 0,
      }}>
        <span style={{
          color: 'var(--color-grayscale-400, #8E8E8E)',
          fontSize: '11px',
          fontStyle: 'normal',
          fontWeight: 500,
          lineHeight: '16px',
          whiteSpace: 'nowrap',
          flexShrink: 0,
        }}>
          {formatFileSize(fileSize)}{extension && ` | ${extension}`}
        </span>
        {onAddTagClick && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            flexWrap: 'wrap',
            minWidth: 0,
          }}>
            {tags?.map((tag) => (
              <span
                key={tag.id}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '0 6px',
                  borderRadius: '4px',
                  border: '1px solid var(--color-secondary-300)',
                  backgroundColor: 'var(--color-secondary-50)',
                  fontSize: '10px',
                  fontWeight: 500,
                  lineHeight: '14px',
                  color: 'var(--color-grayscale-900)',
                  whiteSpace: 'nowrap',
                  boxSizing: 'border-box',
                }}
              >
                {tag.name}
              </span>
            ))}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onAddTagClick();
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '0 6px',
                borderRadius: '4px',
                border: '1px dashed var(--color-grayscale-200)',
                backgroundColor: 'var(--color-grayscale-50)',
                fontSize: '10px',
                fontWeight: 500,
                lineHeight: '14px',
                color: 'var(--color-grayscale-400)',
                cursor: 'pointer',
                whiteSpace: 'nowrap',
                boxSizing: 'border-box',
                height: '16px',
              }}
            >
              추가
              <img src={deptAddIcon} alt="추가" style={{ width: '8px', height: '8px' }} />
            </button>
          </div>
        )}
      </div>
    </>
  );
}

export default DocumentFileCell;
