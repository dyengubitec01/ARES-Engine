// created by ARES team [2026-06-02]
import { useEffect, useState } from 'react';
import {
  ActivityRankItem,
  ActivityRankingMeta,
  ActivityType,
  getActivityRanking,
  refreshActivity,
} from '../../services/admin.service';
import Pagination from '../../components/common/Pagination';
import TableSkeleton from '../../components/common/TableSkeleton';
import { adminHeaderCellStyle, adminTableStyle, adminTitleStyle, adminCellStyle } from '../../styles/tableStyles';
import { GRADIENT, buildGradientHoverHandlers, gradientButtonBase } from '../../styles/buttonStyles';
import MonitoringDetailModal from './MonitoringDetailModal';

const PAGE_LIMIT = 10;

const ACTIVITY_TYPE_LABEL: Record<ActivityType, string> = {
  chat: '채팅',
  upload: '업로드',
  feedback: '오류 제보',
  survey: '설문',
};

const ACTIVITY_TYPE_STYLE: Record<ActivityType, { bg: string; color: string }> = {
  chat: { bg: 'var(--color-primary-100)', color: 'var(--color-primary-700)' },
  upload: { bg: 'var(--color-secondary-100)', color: 'var(--color-secondary-700)' },
  feedback: { bg: 'var(--color-warning-100)', color: 'var(--color-warning-600)' },
  survey: { bg: 'var(--color-tertiary-100)', color: 'var(--color-tertiary-800)' },
};

// 상위 3위 뱃지 색 (gold / silver / bronze)
const RANK_BADGE: Record<number, { bg: string; color: string; border: string }> = {
  1: { bg: '#FFF6D6', color: '#8A6A00', border: '#E5B800' },
  2: { bg: '#F0F1F4', color: '#5D5E62', border: '#B8BCC4' },
  3: { bg: '#FBE7D6', color: '#8A4A18', border: '#D38A4F' },
};

function formatRefreshedAt(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatLastActivityAt(iso: string | null): string {
  if (!iso) return '-';
  return formatRefreshedAt(iso);
}

function Monitoring() {
  const [items, setItems] = useState<ActivityRankItem[]>([]);
  const [meta, setMeta] = useState<ActivityRankingMeta | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  const fetchRanking = async (page: number) => {
    try {
      setIsLoading(true);
      setError(null);
      const result = await getActivityRanking(page, PAGE_LIMIT);
      setItems(result.items);
      setMeta(result.meta);
    } catch {
      setError('사용자 활동 랭킹을 불러오는데 실패했습니다.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchRanking(1);
  }, []);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    fetchRanking(page);
  };

  const handleRefresh = async () => {
    if (isRefreshing) return;
    try {
      setIsRefreshing(true);
      const { refreshedAt: at } = await refreshActivity();
      setRefreshedAt(at);
      await fetchRanking(currentPage);
    } catch {
      setError('새로고침에 실패했습니다.');
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div style={{ padding: '32px 40px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* 헤더 */}
      <div style={{
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
        marginBottom: '24px',
        gap: '16px',
        flexWrap: 'wrap',
      }}>
        <div>
          <h1 style={{ ...adminTitleStyle, margin: '0 0 8px 0' }}>
            사용자 활동 모니터링
          </h1>
          <div style={{
            fontSize: '13px',
            color: 'var(--color-grayscale-500)',
          }}>
            {refreshedAt
              ? `마지막 갱신: ${formatRefreshedAt(refreshedAt)}`
              : '랭킹은 30분 주기로 자동 갱신됩니다.'}
          </div>
        </div>

        <button
          type="button"
          onClick={handleRefresh}
          disabled={isRefreshing}
          {...buildGradientHoverHandlers(isRefreshing)}
          style={{
            ...gradientButtonBase,
            background: GRADIENT.primarySoft,
            borderRadius: '999px',
            padding: '10px 24px',
            opacity: isRefreshing ? 0.6 : 1,
            cursor: isRefreshing ? 'not-allowed' : 'pointer',
          }}
        >
          {isRefreshing ? '갱신 중...' : '새로고침'}
        </button>
      </div>

      {/* 본문 */}
      {isLoading ? (
        <TableSkeleton />
      ) : error ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-error-500)' }}>
          {error}
        </div>
      ) : items.length === 0 ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--color-grayscale-500)' }}>
          표시할 사용자가 없습니다.
        </div>
      ) : (
        <>
          <div style={{ overflowX: 'auto' }}>
            <table style={adminTableStyle}>
              <thead>
                <tr style={{ height: '36px' }}>
                  <th style={{ ...adminHeaderCellStyle, width: '80px', borderTopLeftRadius: '10px' }}>순위</th>
                  <th style={{ ...adminHeaderCellStyle, textAlign: 'left', width: '220px' }}>이름 / 부서</th>
                  <th style={{ ...adminHeaderCellStyle, width: '100px' }}>직급</th>
                  <th style={{ ...adminHeaderCellStyle, width: '110px' }}>종합 점수</th>
                  <th style={{ ...adminHeaderCellStyle, width: '80px' }}>포상</th>
                  <th style={{ ...adminHeaderCellStyle, width: '80px' }}>질문</th>
                  <th style={{ ...adminHeaderCellStyle, width: '80px' }}>업로드</th>
                  <th style={{ ...adminHeaderCellStyle, width: '90px' }}>타인 인용</th>
                  <th style={{ ...adminHeaderCellStyle, width: '180px', borderTopRightRadius: '10px' }}>마지막 활동</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const rankBadge = RANK_BADGE[item.rank];
                  const activityStyle = item.lastActivityType ? ACTIVITY_TYPE_STYLE[item.lastActivityType] : null;
                  return (
                    <tr
                      key={item.userId}
                      onClick={() => setSelectedUserId(item.userId)}
                      style={{ cursor: 'pointer', transition: 'background-color 0.15s' }}
                      onMouseOver={(e) => { e.currentTarget.style.backgroundColor = 'var(--color-primary-50)'; }}
                      onMouseOut={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
                    >
                      <td style={{ ...adminCellStyle, textAlign: 'center' }}>
                        <span style={{
                          display: 'inline-block',
                          minWidth: '44px',
                          padding: '4px 10px',
                          borderRadius: '999px',
                          fontSize: '12px',
                          fontWeight: '600',
                          backgroundColor: rankBadge?.bg ?? 'var(--color-grayscale-100)',
                          color: rankBadge?.color ?? 'var(--color-grayscale-600)',
                          border: `1px solid ${rankBadge?.border ?? 'var(--color-grayscale-200)'}`,
                        }}>
                          {item.rank}위
                        </span>
                      </td>
                      <td style={adminCellStyle}>
                        <div style={{ color: 'var(--color-grayscale-900)', fontWeight: '500' }}>
                          {item.name}
                        </div>
                        <div style={{ color: 'var(--color-grayscale-500)', fontSize: '12px', marginTop: '2px' }}>
                          {item.department ?? '-'}
                        </div>
                      </td>
                      <td style={{ ...adminCellStyle, textAlign: 'center', color: item.jobTitle ? 'var(--color-grayscale-900)' : 'var(--color-grayscale-500)' }}>
                        {item.jobTitle ?? '-'}
                      </td>
                      <td style={{ ...adminCellStyle, textAlign: 'center', fontWeight: '600', color: 'var(--color-grayscale-900)' }}>
                        {item.totalScore.toLocaleString()}
                      </td>
                      <td style={{ ...adminCellStyle, textAlign: 'center' }}>
                        {item.eligible ? (
                          <span style={{
                            display: 'inline-block',
                            padding: '4px 10px',
                            borderRadius: '12px',
                            fontSize: '12px',
                            fontWeight: '500',
                            backgroundColor: 'var(--color-success-100)',
                            color: 'var(--color-success-700)',
                          }}>
                            포상
                          </span>
                        ) : (
                          <span style={{ color: 'var(--color-grayscale-300)', fontSize: '12px' }}>-</span>
                        )}
                      </td>
                      <td style={{ ...adminCellStyle, textAlign: 'center', color: 'var(--color-grayscale-700)' }}>
                        {item.questionCount.toLocaleString()}
                      </td>
                      <td style={{ ...adminCellStyle, textAlign: 'center', color: 'var(--color-grayscale-700)' }}>
                        {item.uploadCount.toLocaleString()}
                      </td>
                      <td style={{ ...adminCellStyle, textAlign: 'center', color: 'var(--color-grayscale-700)' }}>
                        {item.otherCitationCount.toLocaleString()}
                      </td>
                      <td style={adminCellStyle}>
                        {item.lastActivityType && activityStyle ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{
                              display: 'inline-block',
                              padding: '4px 10px',
                              borderRadius: '12px',
                              fontSize: '12px',
                              fontWeight: '500',
                              backgroundColor: activityStyle.bg,
                              color: activityStyle.color,
                            }}>
                              {ACTIVITY_TYPE_LABEL[item.lastActivityType]}
                            </span>
                            <span style={{ fontSize: '12px', color: 'var(--color-grayscale-500)' }}>
                              {formatLastActivityAt(item.lastActivityAt)}
                            </span>
                          </div>
                        ) : (
                          <span style={{ color: 'var(--color-grayscale-300)', fontSize: '12px' }}>활동 없음</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {meta && meta.total > 0 && (
            <Pagination
              currentPage={currentPage}
              totalItems={meta.total}
              itemsPerPage={meta.limit}
              onPageChange={handlePageChange}
              itemLabel="명"
            />
          )}
        </>
      )}

      <MonitoringDetailModal
        userId={selectedUserId}
        onClose={() => setSelectedUserId(null)}
      />
    </div>
  );
}

export default Monitoring;
