// created by ARES team [2026-06-02]
import { useEffect, useState } from 'react';
import {
  ActivityDetail,
  ActivityPeriod,
  ActivityType,
  getActivityDetail,
} from '../../services/admin.service';
import { secondaryButtonStyle, secondaryButtonHoverHandlers } from '../../styles/buttonStyles';

const ACTIVITY_TYPE_LABEL: Record<ActivityType, string> = {
  chat: '채팅',
  upload: '업로드',
  feedback: '오류 제보',
  survey: '설문',
};

const PERIOD_LABEL: Record<ActivityPeriod, string> = {
  intro: '도입기',
  expansion: '확산기',
  default: '일반',
};

interface MonitoringDetailModalProps {
  userId: string | null;
  onClose: () => void;
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function ScoreCard({ title, score, children }: { title: string; score: number; children: React.ReactNode }) {
  return (
    <div style={{
      flex: 1,
      minWidth: '180px',
      padding: '20px',
      borderRadius: '12px',
      backgroundColor: 'var(--color-grayscale-100)',
      border: '1px solid var(--color-grayscale-150)',
    }}>
      <div style={{
        fontSize: '13px',
        fontWeight: '500',
        color: 'var(--color-grayscale-500)',
        marginBottom: '6px',
      }}>
        {title}
      </div>
      <div style={{
        fontSize: '24px',
        fontWeight: '700',
        color: 'var(--color-grayscale-900)',
        marginBottom: '14px',
      }}>
        {score.toLocaleString()}<span style={{ fontSize: '14px', fontWeight: '500', color: 'var(--color-grayscale-500)', marginLeft: '4px' }}>점</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {children}
      </div>
    </div>
  );
}

function ScoreRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'space-between',
      fontSize: '13px',
    }}>
      <span style={{ color: 'var(--color-grayscale-500)' }}>{label}</span>
      <span style={{ color: 'var(--color-grayscale-900)', fontWeight: '500' }}>{value}</span>
    </div>
  );
}

function MonitoringDetailModal({ userId, onClose }: MonitoringDetailModalProps) {
  const [detail, setDetail] = useState<ActivityDetail | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) {
      setDetail(null);
      setError(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        setIsLoading(true);
        setError(null);
        const data = await getActivityDetail(userId);
        if (!cancelled) setDetail(data);
      } catch {
        if (!cancelled) setError('사용자 활동 상세 정보를 불러오는데 실패했습니다.');
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [userId]);

  useEffect(() => {
    if (userId) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => { document.body.style.overflow = 'unset'; };
  }, [userId]);

  if (!userId) return null;

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
        padding: '20px',
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          position: 'relative',
          backgroundColor: 'var(--color-grayscale-50, #FFF)',
          borderRadius: '16px',
          boxShadow: 'var(--shadow-modal)',
          maxWidth: '720px',
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          padding: '40px',
          animation: 'modalFadeIn 0.2s ease-out',
        }}
      >
        {isLoading ? (
          <div style={{ padding: '60px 0', textAlign: 'center', color: 'var(--color-grayscale-500)' }}>
            불러오는 중...
          </div>
        ) : error || !detail ? (
          <>
            <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--color-error-500)' }}>
              {error ?? '데이터가 없습니다.'}
            </div>
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <button
                onClick={onClose}
                style={{ ...secondaryButtonStyle, flex: 'none', minWidth: '160px' }}
                {...secondaryButtonHoverHandlers}
              >
                닫기
              </button>
            </div>
          </>
        ) : (
          <>
            {/* 헤더 */}
            <div style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: '16px',
              marginBottom: '20px',
            }}>
              <div>
                <div style={{
                  fontSize: '22px',
                  fontWeight: '600',
                  color: 'var(--color-grayscale-900)',
                  marginBottom: '4px',
                }}>
                  {detail.name}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--color-grayscale-500)' }}>
                  {[detail.department, detail.jobTitle].filter(Boolean).join(' · ') || '-'}
                </div>
              </div>
              <span style={{
                padding: '6px 14px',
                borderRadius: '999px',
                fontSize: '13px',
                fontWeight: '600',
                backgroundColor: 'var(--color-primary-100)',
                color: 'var(--color-primary-700)',
                whiteSpace: 'nowrap',
              }}>
                Rank #{detail.rank}
              </span>
            </div>

            {/* 종합 점수 */}
            <div style={{
              padding: '20px 24px',
              borderRadius: '12px',
              background: 'linear-gradient(127deg, #F2F3FF 0%, #FAFBFF 100%)',
              border: '1px solid var(--color-primary-200)',
              marginBottom: '20px',
            }}>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <div style={{ fontSize: '13px', color: 'var(--color-grayscale-500)', marginBottom: '4px' }}>
                    종합 점수
                  </div>
                  <div style={{ fontSize: '32px', fontWeight: '700', color: 'var(--color-primary-700)' }}>
                    {detail.totalScore.toLocaleString()}
                    <span style={{ fontSize: '16px', fontWeight: '500', color: 'var(--color-grayscale-500)', marginLeft: '6px' }}>점</span>
                  </div>
                </div>
                {detail.eligible && (
                  <span style={{
                    padding: '6px 14px',
                    borderRadius: '12px',
                    fontSize: '13px',
                    fontWeight: '600',
                    backgroundColor: 'var(--color-success-100)',
                    color: 'var(--color-success-700)',
                  }}>
                    포상 대상 (1,200점 이상)
                  </span>
                )}
              </div>

              <div style={{
                marginTop: '14px',
                display: 'flex',
                gap: '20px',
                fontSize: '13px',
                color: 'var(--color-grayscale-700)',
                flexWrap: 'wrap',
              }}>
                <div>시기: <strong style={{ color: 'var(--color-grayscale-900)' }}>{PERIOD_LABEL[detail.period]}</strong></div>
                <div>부서 배율: <strong style={{ color: 'var(--color-grayscale-900)' }}>×{detail.deptMultiplier.toFixed(1)}</strong></div>
                <div>부서 eligible 비율: <strong style={{ color: 'var(--color-grayscale-900)' }}>{detail.deptEligibleRatio.toFixed(1)}%</strong></div>
              </div>
            </div>

            {/* 3개 점수 카드 */}
            <div style={{
              display: 'flex',
              gap: '12px',
              marginBottom: '20px',
              flexWrap: 'wrap',
            }}>
              <ScoreCard title="Persona (사용성)" score={detail.persona.score}>
                <ScoreRow label="누적 질문" value={detail.persona.questionCount} />
                <ScoreRow label="미접속 일수" value={detail.persona.missedDays} />
                <ScoreRow label="3일 연속" value={`${detail.persona.threeDayStreakCount}회`} />
                <ScoreRow label="5일 연속" value={`${detail.persona.fiveDayStreakCount}회`} />
              </ScoreCard>

              <ScoreCard title="Heritage (지식 자산화)" score={detail.heritage.score}>
                <ScoreRow label="문서 업로드" value={detail.heritage.uploadCount} />
                <ScoreRow label="타인 문서 인용" value={detail.heritage.otherCitationCount} />
                <ScoreRow label="본인 문서 인용" value={detail.heritage.selfCitationCount} />
              </ScoreCard>

              <ScoreCard title="EXpert (서비스 개선)" score={detail.expert.score}>
                <ScoreRow label="오류 제보" value={detail.expert.feedbackCount} />
                <ScoreRow label="정답 데이터" value={detail.expert.answerSuggestionCount} />
                <ScoreRow label="채택 점수" value={detail.expert.adoptionScore} />
              </ScoreCard>
            </div>

            {/* 마지막 활동 */}
            <div style={{
              padding: '16px 20px',
              borderRadius: '12px',
              backgroundColor: 'var(--color-grayscale-100)',
              border: '1px solid var(--color-grayscale-150)',
              marginBottom: '24px',
            }}>
              <div style={{ fontSize: '13px', color: 'var(--color-grayscale-500)', marginBottom: '6px' }}>
                마지막 활동
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                {detail.lastActivityType && (
                  <span style={{
                    padding: '4px 10px',
                    borderRadius: '12px',
                    fontSize: '12px',
                    fontWeight: '500',
                    backgroundColor: 'var(--color-primary-100)',
                    color: 'var(--color-primary-700)',
                  }}>
                    {ACTIVITY_TYPE_LABEL[detail.lastActivityType]}
                  </span>
                )}
                <span style={{ fontSize: '14px', color: 'var(--color-grayscale-900)' }}>
                  {formatDateTime(detail.lastActivityAt)}
                </span>
              </div>
              <div style={{ marginTop: '8px', fontSize: '12px', color: 'var(--color-grayscale-400)' }}>
                데이터 갱신: {formatDateTime(detail.updatedAt)}
              </div>
            </div>

            {/* 닫기 */}
            <div style={{ display: 'flex', justifyContent: 'center' }}>
              <button
                onClick={onClose}
                style={{ ...secondaryButtonStyle, flex: 'none', minWidth: '160px' }}
                {...secondaryButtonHoverHandlers}
              >
                닫기
              </button>
            </div>
          </>
        )}

        <style>
          {`
            @keyframes modalFadeIn {
              from { opacity: 0; transform: scale(0.95) translateY(-10px); }
              to { opacity: 1; transform: scale(1) translateY(0); }
            }
          `}
        </style>
      </div>
    </div>
  );
}

export default MonitoringDetailModal;
