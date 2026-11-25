// created by ARES team [2026-03-20]
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Image from '@tiptap/extension-image';
import { useRef, useState } from 'react';
import { uploadBoardImage, BoardImage } from '../../services/board.service';

interface TiptapEditorProps {
  boardTypeName: string;
  onUpdate?: (html: string) => void;
  onImageUpload?: (imageInfo: BoardImage) => void;
}

function ToolbarButton({ onClick, isActive, disabled, title, children }: {
  onClick: () => void;
  isActive?: boolean;
  disabled?: boolean;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={{
        padding: '4px 8px',
        backgroundColor: isActive ? 'var(--color-primary-100)' : 'transparent',
        border: '1px solid',
        borderColor: isActive ? 'var(--color-primary-600)' : 'transparent',
        borderRadius: '4px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontSize: '13px',
        fontWeight: isActive ? 600 : 400,
        color: isActive ? 'var(--color-primary-600)' : 'var(--color-grayscale-900)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: '28px',
        height: '28px',
        transition: 'all 0.15s',
        opacity: disabled ? 0.5 : 1,
      }}
    >
      {children}
    </button>
  );
}

function TiptapEditor({ boardTypeName, onUpdate, onImageUpload }: TiptapEditorProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);

  const editor = useEditor({
    extensions: [
      StarterKit,
      Image.configure({
        inline: false,
        allowBase64: false,
      }),
    ],
    content: '',
    onUpdate: ({ editor }) => {
      onUpdate?.(editor.getHTML());
    },
  });

  if (!editor) return null;

  const handleImageClick = () => {
    if (!isUploading) {
      fileInputRef.current?.click();
    }
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // 같은 파일 재선택 가능하도록 초기화
    e.target.value = '';

    setIsUploading(true);
    try {
      const imageInfo = await uploadBoardImage(file, boardTypeName);

      // 에디터에 이미지 삽입
      editor.chain().focus().setImage({ src: imageInfo.viewUrl }).run();

      // 부모에 메타데이터 전달
      onImageUpload?.(imageInfo);
    } catch {
      // apiClient 인터셉터에서 로깅됨
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div style={{ border: '1px solid var(--color-grayscale-150)', borderRadius: '8px', overflow: 'hidden', display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* 툴바 */}
      <div style={{
        display: 'flex',
        gap: '4px',
        padding: '8px 12px',
        borderBottom: '1px solid var(--color-grayscale-150)',
        backgroundColor: 'var(--color-grayscale-100)',
        alignItems: 'center',
      }}>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleBold().run()}
          isActive={editor.isActive('bold')}
          title="굵게"
        >
          <strong>B</strong>
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleItalic().run()}
          isActive={editor.isActive('italic')}
          title="기울임"
        >
          <em>I</em>
        </ToolbarButton>
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleStrike().run()}
          isActive={editor.isActive('strike')}
          title="취소선"
        >
          <s>S</s>
        </ToolbarButton>

        <div style={{ width: '1px', backgroundColor: 'var(--color-grayscale-150)', margin: '0 4px' }} />

        <ToolbarButton
          onClick={handleImageClick}
          disabled={isUploading}
          title={isUploading ? '업로드 중...' : '이미지 삽입'}
        >
          {isUploading ? (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg"
              style={{ animation: 'spin 1s linear infinite' }}>
              <circle cx="8" cy="8" r="6" stroke="var(--color-primary-600)" strokeWidth="2" strokeDasharray="28" strokeDashoffset="8" strokeLinecap="round" />
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="1.5" y="2.5" width="13" height="11" rx="1.5" stroke="currentColor" />
              <circle cx="5" cy="6" r="1.5" stroke="currentColor" />
              <path d="M1.5 11L5 8L8 11L11 7.5L14.5 11" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </ToolbarButton>

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          style={{ display: 'none' }}
          onChange={handleFileSelect}
        />
      </div>

      {/* 에디터 본문 */}
      <EditorContent
        editor={editor}
        className="tiptap-wrapper"
        style={{ flex: 1, minHeight: 0 }}
      />

      <style>{`
        .tiptap-wrapper {
          display: flex;
          flex-direction: column;
          flex: 1;
          min-height: 0;
        }
        .tiptap {
          flex: 1;
          padding: 12px 16px;
          box-sizing: border-box;
          outline: none;
          font-size: 14px;
          line-height: 1.6;
          color: var(--color-grayscale-900);
        }
        .tiptap p.is-editor-empty:first-child::before {
          content: '내용을 입력해주세요.';
          color: #B0B0B0;
          float: left;
          pointer-events: none;
          height: 0;
        }
        .tiptap img {
          max-width: 100%;
          border-radius: 4px;
          margin: 8px 0;
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

export default TiptapEditor;
