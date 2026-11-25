import { BoardPostDetail, BoardPostDetailImage } from '../../../services/board.service';
import { formatDate } from '../../../lib/fileUtils';
import { useAuth } from '../../../features/auth/AuthContext';
import {
  GRADIENT,
  gradientButtonBase,
  secondaryButtonStyle,
  secondaryButtonHoverHandlers,
  buildGradientHoverHandlers,
} from '../../../styles/buttonStyles';
import { COMMENT_MAX_LENGTH } from './useBoard';
import { AnswerCase, AnswerContent } from '../../../constants/answerSuggestion';

interface BoardDetailViewProps {
  postDetail: BoardPostDetail | null;
  isLoading: boolean;
  error: string | null;
  suggestionBoardTypeId: string;
  answerSuggestionBoardTypeId: string;
  onBackToList: () => void;
  onClose: () => void;
  commentContent: string;
  setCommentContent: (v: string) => void;
  isSubmittingComment: boolean;
  commentError: string | null;
  setCommentError: (v: string | null) => void;
  onSubmitComment: () => void;
}

function parseAnswerContent(content: string): AnswerContent | null {
  try {
    const parsed = JSON.parse(content);
    if (parsed && Array.isArray(parsed.cases)) return parsed as AnswerContent;
    return null;
  } catch {
    return null;
  }
}

function findImageForCase(
  caseObj: AnswerCase,
  images: BoardPostDetailImage[]
): BoardPostDetailImage | null {
  if (!caseObj.imageObjectKey) return null;
  return images.find((img) => img.objectKey === caseObj.imageObjectKey) ?? null;
}

function BoardDetailView({
  postDetail,
  isLoading,
  error,
  suggestionBoardTypeId,
  answerSuggestionBoardTypeId,
  onBackToList,
  onClose,
  commentContent,
  setCommentContent,
  isSubmittingComment,
  commentError,
  setCommentError,
  onSubmitComment,
}: BoardDetailViewProps) {
  const isSuggestion = postDetail?.boardTypeId === suggestionBoardTypeId;
  const isAnswerData = postDetail?.boardTypeId === answerSuggestionBoardTypeId;
  const headerTitle = isSuggestion
    ? '서비스 제안 상세'
    : isAnswerData
      ? '답변 오류 상세'
      : '기능 오류 상세';
  const { isAdmin } = useAuth();

  const renderAnswerCases = (content: string, images: BoardPostDetailImage[]) => {
    const parsed = parseAnswerContent(content);
    if (!parsed || parsed.cases.length === 0) {
      return (
        <div style={{ ...loadingStateStyle, color: 'var(--color-error-500)' }}>
          신고 내용을 불러올 수 없습니다.
        </div>
      );
    }
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {parsed.cases.map((caseObj, idx) => {
          const matchedImage = findImageForCase(caseObj, images);
          return (
            <div
              key={idx}
              style={{
                borderRadius: '12px',
                border: '1px solid var(--color-grayscale-200, #DDD)',
                background: 'var(--color-grayscale-50, #FFF)',
                padding: '16px 18px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <CaseField label="AI 서비스" value={caseObj.aiServiceName} />
              <CaseField label="오류 유형" value={caseObj.errorType} valueAsBadge />
              <CaseField label="입력 문장" value={caseObj.inputSentence} multiline />
              <CaseField label="올바른 내용" value={caseObj.correctContent} />
              {matchedImage && (
                <div>
                  <div style={caseFieldLabelStyle}>첨부 이미지</div>
                  <a
                    href={matchedImage.viewUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ display: 'block' }}
                  >
                    <img
                      src={matchedImage.viewUrl}
                      alt={matchedImage.originalFilename}
                      style={{
                        maxWidth: '100%',
                        height: 'auto',
                        borderRadius: '8px',
                        border: '1px solid var(--color-grayscale-200, #DDD)',
                        display: 'block',
                      }}
                    />
                  </a>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  const renderBody = () => {
    if (isLoading) {
      return (
        <div style={loadingStateStyle}>불러오는 중...</div>
      );
    }

    if (error) {
      return (
        <div style={{ ...loadingStateStyle, color: 'var(--color-error-500)' }}>{error}</div>
      );
    }

    if (!postDetail) {
      return null;
    }

    const sortedImages = [...postDetail.images].sort((a, b) => a.sortOrder - b.sortOrder);

    return (
      <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: '24px', paddingRight: '4px' }}>
        {/* 헤더: 제목 + 작성자/날짜 */}
        <div>
          <div style={{
            color: 'var(--color-grayscale-900, #31343E)',
            fontSize: '20px',
            fontWeight: 600,
            lineHeight: '28px',
            letterSpacing: '-0.4px',
            wordBreak: 'break-word',
          }}>
            {postDetail.title}
          </div>
          <div style={{
            marginTop: '8px',
            color: 'var(--color-grayscale-400, #8E8E8E)',
            fontSize: '12px',
            fontWeight: 400,
            lineHeight: '18px',
          }}>
            {postDetail.userName} · {formatDate(postDetail.createdAt, '.')}
          </div>
        </div>

        {isAnswerData ? (
          renderAnswerCases(postDetail.content, postDetail.images)
        ) : (
          <>
            {/* 본문 */}
            <div
              className="error-report-detail-content"
              style={{
                color: 'var(--color-grayscale-800, #4A4A4A)',
                fontSize: '14px',
                fontWeight: 400,
                lineHeight: '22px',
                letterSpacing: '-0.28px',
                wordBreak: 'break-word',
                whiteSpace: 'pre-wrap',
              }}
              dangerouslySetInnerHTML={{ __html: postDetail.content }}
            />

            {/* 이미지 갤러리 */}
            {sortedImages.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {sortedImages.map((img) => (
                  <a
                    key={img.id}
                    href={img.viewUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ display: 'block' }}
                  >
                    <img
                      src={img.viewUrl}
                      alt={img.originalFilename}
                      style={{
                        maxWidth: '100%',
                        height: 'auto',
                        borderRadius: '8px',
                        border: '1px solid var(--color-grayscale-200, #DDD)',
                        display: 'block',
                      }}
                    />
                  </a>
                ))}
              </div>
            )}
          </>
        )}

        {/* 구분선 */}
        <div style={{ height: '1px', backgroundColor: 'var(--color-grayscale-200, #DDD)' }} />

        {/* 답변 영역 */}
        {postDetail.reply ? (
          <div style={{
            padding: '16px 18px',
            borderRadius: '12px',
            backgroundColor: 'var(--color-grayscale-100, #F5F5F5)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px',
              color: 'var(--color-grayscale-500, #757578)',
            }}>
              <span style={{
                padding: '2px 8px',
                borderRadius: '999px',
                backgroundColor: 'var(--color-primary-600, #626BF7)',
                color: '#fff',
                fontWeight: 500,
                fontSize: '11px',
                lineHeight: '16px',
              }}>
                답변
              </span>
              <span style={{ fontWeight: 500, color: 'var(--color-grayscale-700, #5A5A5A)' }}>
                {postDetail.reply.userName}
              </span>
              <span>·</span>
              <span>{formatDate(postDetail.reply.createdAt, '.')}</span>
            </div>
            <div style={{
              color: 'var(--color-grayscale-800, #4A4A4A)',
              fontSize: '14px',
              lineHeight: '22px',
              letterSpacing: '-0.28px',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {postDetail.reply.content}
            </div>
          </div>
        ) : isAdmin ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <div style={{
              fontSize: '13px',
              fontWeight: 500,
              color: 'var(--color-grayscale-700, #5A5A5A)',
            }}>
              답변 작성 (Admin)
            </div>
            <textarea
              value={commentContent}
              onChange={(e) => {
                if (commentError) setCommentError(null);
                setCommentContent(e.target.value.slice(0, COMMENT_MAX_LENGTH));
              }}
              placeholder="답변 내용을 입력하세요"
              disabled={isSubmittingComment}
              style={{
                width: '100%',
                minHeight: '110px',
                padding: '12px 14px',
                borderRadius: '12px',
                border: '1px solid var(--color-grayscale-200, #DDD)',
                backgroundColor: 'var(--color-grayscale-50, #FFF)',
                fontSize: '14px',
                lineHeight: '22px',
                color: 'var(--color-grayscale-900, #31343E)',
                resize: 'vertical',
                outline: 'none',
                fontFamily: 'inherit',
                boxSizing: 'border-box',
              }}
            />
            <div style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: '12px',
              color: 'var(--color-grayscale-400, #8E8E8E)',
            }}>
              <span style={{ color: commentError ? 'var(--color-error-500)' : 'inherit' }}>
                {commentError ?? ' '}
              </span>
              <span>{commentContent.length} / {COMMENT_MAX_LENGTH}</span>
            </div>
            <button
              onClick={onSubmitComment}
              disabled={isSubmittingComment || !commentContent.trim()}
              style={{
                ...gradientButtonBase,
                background: GRADIENT.primarySoft,
                padding: '10px 20px',
                borderRadius: '999px',
                alignSelf: 'flex-end',
                opacity: isSubmittingComment || !commentContent.trim() ? 0.5 : 1,
                cursor: isSubmittingComment || !commentContent.trim() ? 'not-allowed' : 'pointer',
              }}
              {...buildGradientHoverHandlers(isSubmittingComment || !commentContent.trim())}
            >
              {isSubmittingComment ? '등록 중...' : '답변 등록'}
            </button>
          </div>
        ) : (
          <div style={{
            padding: '16px 18px',
            borderRadius: '12px',
            backgroundColor: 'var(--color-grayscale-100, #F5F5F5)',
            color: 'var(--color-grayscale-400, #8E8E8E)',
            fontSize: '13px',
            textAlign: 'center',
          }}>
            아직 답변이 등록되지 않았습니다.
          </div>
        )}
      </div>
    );
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '40px 40px 0', overflow: 'hidden' }}>
        <div style={{
          color: 'var(--color-grayscale-900, #31343E)',
          fontSize: '24px',
          fontWeight: 600,
          lineHeight: '28px',
          letterSpacing: '-0.48px',
          marginBottom: '24px',
          flexShrink: 0,
        }}>
          {headerTitle}
        </div>

        {renderBody()}
      </div>

      <div style={{
        display: 'flex',
        gap: '16px',
        padding: '24px 40px 40px',
        flexShrink: 0,
      }}>
        <button
          onClick={onBackToList}
          style={secondaryButtonStyle}
          {...secondaryButtonHoverHandlers}
        >
          목록으로
        </button>
        <button
          onClick={onClose}
          style={{ ...secondaryButtonStyle, flex: 1 }}
          {...secondaryButtonHoverHandlers}
        >
          닫기
        </button>
      </div>

      <style>{`
        .error-report-detail-content img {
          max-width: 100%;
          height: auto;
          border-radius: 8px;
          margin: 8px 0;
        }
        .error-report-detail-content p {
          margin: 0 0 8px;
        }
        .error-report-detail-content a {
          color: var(--color-primary-600, #626BF7);
          text-decoration: underline;
        }
      `}</style>
    </div>
  );
}

const loadingStateStyle = {
  flex: 1,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  color: 'var(--color-grayscale-400)',
  fontSize: '13px',
} as const;

const caseFieldLabelStyle = {
  fontSize: '12px',
  fontWeight: 500,
  color: 'var(--color-grayscale-400, #8E8E8E)',
  marginBottom: '4px',
  letterSpacing: '-0.24px',
} as const;

const caseFieldValueStyle = {
  fontSize: '14px',
  fontWeight: 400,
  color: 'var(--color-grayscale-900, #31343E)',
  lineHeight: '22px',
  letterSpacing: '-0.28px',
  wordBreak: 'break-word' as const,
};

function CaseField({
  label,
  value,
  multiline,
  valueAsBadge,
}: {
  label: string;
  value: string;
  multiline?: boolean;
  valueAsBadge?: boolean;
}) {
  return (
    <div>
      <div style={caseFieldLabelStyle}>{label}</div>
      {valueAsBadge ? (
        <span
          style={{
            display: 'inline-block',
            padding: '4px 10px',
            borderRadius: '999px',
            backgroundColor: 'var(--color-primary-100, #F2F3FF)',
            color: 'var(--color-primary-600, #626BF7)',
            fontSize: '12px',
            fontWeight: 500,
            lineHeight: '18px',
            letterSpacing: '-0.24px',
          }}
        >
          {value}
        </span>
      ) : (
        <div
          style={{
            ...caseFieldValueStyle,
            whiteSpace: multiline ? ('pre-wrap' as const) : ('normal' as const),
          }}
        >
          {value}
        </div>
      )}
    </div>
  );
}

export default BoardDetailView;
