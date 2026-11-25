// created by ARES team [2026-04-28]
import { BoardPost } from '../../../services/board.service';
import { formatDate } from '../../../lib/fileUtils';
import {
  GRADIENT,
  gradientButtonBase,
  secondaryButtonStyle,
  secondaryButtonHoverHandlers,
  buildGradientHoverHandlers,
} from '../../../styles/buttonStyles';
import Pagination from '../Pagination';
import SurveyForm from '../SurveyForm';
import BoardTabs from './BoardTabs';
import { BoardTab, ITEMS_PER_PAGE, ReportSubCategory } from './useBoard';

interface BoardListViewProps {
  activeTab: BoardTab;
  setActiveTab: (tab: BoardTab) => void;
  reportSubCategory: ReportSubCategory;
  setReportSubCategory: (sub: ReportSubCategory) => void;
  posts: BoardPost[];
  totalItems: number;
  isLoading: boolean;
  currentPage: number;
  onPageChange: (page: number) => void;
  onClose: () => void;
  onGoToWrite: () => void;
  onGoToDetail: (postId: string) => void;
}

function BoardListView({
  activeTab,
  setActiveTab,
  reportSubCategory,
  setReportSubCategory,
  posts,
  totalItems,
  isLoading,
  currentPage,
  onPageChange,
  onClose,
  onGoToWrite,
  onGoToDetail,
}: BoardListViewProps) {
  const handleTabChange = (tab: BoardTab) => {
    setActiveTab(tab);
    if (tab !== 'error') {
      setReportSubCategory('general');
    }
    onPageChange(1);
  };

  const handleSubCategoryChange = (sub: ReportSubCategory) => {
    setReportSubCategory(sub);
    onPageChange(1);
  };

  const isAnswerData = activeTab === 'error' && reportSubCategory === 'answerData';

  return (
    <>
      <BoardTabs activeTab={activeTab} onTabChange={handleTabChange} />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        {activeTab === 'usability' ? (
          <SurveyForm onClose={onClose} />
        ) : (
          <>
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '40px 40px 0', overflow: 'hidden' }}>
              <div style={{ color: 'var(--color-grayscale-900, #31343E)', fontSize: '24px', fontStyle: 'normal', fontWeight: 600, lineHeight: '28px', letterSpacing: '-0.48px', marginBottom: '16px' }}>
                {activeTab === 'suggestion'
                  ? '서비스 제안 목록'
                  : isAnswerData
                    ? '답변 오류 목록'
                    : '기능 오류 목록'}
              </div>

              {activeTab === 'error' && (
                <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexShrink: 0 }}>
                  {(['general', 'answerData'] as const).map((sub) => {
                    const active = reportSubCategory === sub;
                    const label = sub === 'general' ? '기능 오류' : '답변 오류';
                    return (
                      <button
                        key={sub}
                        type="button"
                        onClick={() => handleSubCategoryChange(sub)}
                        style={{
                          padding: '6px 14px',
                          borderRadius: '999px',
                          border: active ? '1px solid var(--color-primary-600, #626BF7)' : '1px solid var(--color-grayscale-200, #DDD)',
                          backgroundColor: active ? 'var(--color-primary-100, #F2F3FF)' : 'transparent',
                          color: active ? 'var(--color-primary-600, #626BF7)' : 'var(--color-grayscale-500, #757578)',
                          fontSize: '13px',
                          fontWeight: active ? 600 : 400,
                          lineHeight: '20px',
                          letterSpacing: '-0.26px',
                          cursor: 'pointer',
                          transition: 'background-color 0.15s, color 0.15s, border-color 0.15s',
                        }}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              )}

              {isLoading ? (
                <div style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--color-grayscale-400)',
                  fontSize: '13px',
                }}>
                  불러오는 중...
                </div>
              ) : posts.length === 0 ? (
                <div style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--color-grayscale-400)',
                  fontSize: '13px',
                }}>
                  {activeTab === 'suggestion'
                    ? '제안 내역이 없습니다.'
                    : isAnswerData
                      ? '답변 오류 내역이 없습니다.'
                      : '기능 오류 내역이 없습니다.'}
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {posts.map((post, index) => (
                    <div
                      key={post.id}
                      onClick={() => onGoToDetail(post.id)}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        padding: '6px 12px',
                        gap: '16px',
                        borderRadius: '8px',
                        border: '1px solid var(--color-grayscale-200, #DDD)',
                        cursor: 'pointer',
                        transition: 'background-color 0.15s',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.backgroundColor = 'var(--color-grayscale-100, #F5F5F5)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.backgroundColor = '';
                      }}
                    >
                      <span style={{
                        display: 'flex', width: '38px', height: '38px', padding: '10px', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', gap: '10px', flexShrink: 0,
                        borderRadius: '4px', background: 'var(--color-primary-100, #F2F3FF)', color: 'var(--color-primary-600, #626BF7)',
                        textAlign: 'center', fontSize: '11px', fontStyle: 'normal', fontWeight: 400, lineHeight: '16px',
                      }}>
                        {totalItems - ((currentPage - 1) * ITEMS_PER_PAGE + index)}
                      </span>
                      <div style={{ flex: 1, overflow: 'hidden' }}>
                        <div style={{
                          overflow: 'hidden', color: 'var(--color-grayscale-900, #31343E)', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          fontSize: '14px', fontStyle: 'normal', fontWeight: 500, lineHeight: '20px', letterSpacing: '-0.28px',
                        }}>
                          {post.title}
                        </div>
                        <div style={{
                          color: 'var(--color-grayscale-400, #8E8E8E)', fontSize: '11px', fontStyle: 'normal', fontWeight: 400, lineHeight: '16px',
                        }}>
                          {formatDate(post.createdAt, '.')}
                        </div>
                      </div>
                      <span style={{
                        flexShrink: 0,
                        padding: '4px 10px',
                        borderRadius: '999px',
                        fontSize: '11px',
                        fontWeight: 500,
                        lineHeight: '16px',
                        letterSpacing: '-0.22px',
                        backgroundColor: post.isReplied ? 'var(--color-grayscale-100, #F5F5F5)' : 'var(--color-primary-100, #F2F3FF)',
                        color: post.isReplied ? 'var(--color-grayscale-500, #757578)' : 'var(--color-primary-600, #626BF7)',
                      }}>
                        {post.isReplied ? '답변완료' : '미답변'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <div style={{ flexShrink: 0, marginTop: 'auto', marginBottom: '20px' }}>
                <Pagination
                  currentPage={currentPage}
                  totalItems={totalItems}
                  itemsPerPage={ITEMS_PER_PAGE}
                  onPageChange={onPageChange}
                />
              </div>
            </div>

            <div style={{
              display: 'flex',
              gap: '16px',
              padding: '0 40px 40px',
              flexShrink: 0,
            }}>
              <button
                onClick={onClose}
                style={secondaryButtonStyle}
                {...secondaryButtonHoverHandlers}
              >
                닫기
              </button>

              <button
                onClick={onGoToWrite}
                style={{
                  ...gradientButtonBase,
                  background: GRADIENT.primarySoft,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  padding: '10px 28px',
                  width: '406px',
                  borderRadius: '999px',
                  transition: 'opacity 0.2s',
                  flexShrink: 0,
                }}
                {...buildGradientHoverHandlers(false)}
              >
                {activeTab === 'suggestion' ? '제안하기' : '신고하기'}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}

export default BoardListView;