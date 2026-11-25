import { useState, useEffect } from 'react';
import apiClient from '../../lib/apiClient';
import dashboardArrow from '../../assets/docs/dashboard.svg';
import uploadedIcon from '../../assets/docs/uploaded.svg';
import pendingIcon from '../../assets/docs/pending.svg';
import completedIcon from '../../assets/docs/completed.svg';
import usedIcon from '../../assets/docs/used.svg';

interface DashboardItem {
  label: string;
  count: number;
}

interface DocumentSummaryResponse {
  success: boolean;
  code: string;
  message: string;
  data: {
    uploaded: number;
    completed: number;
    enabled: number;
    pendingApproval: number;
  };
}

const CARD_STYLES = [
  { border: '1px solid var(--color-primary-200)', countColor: 'var(--color-primary-500)', icon: uploadedIcon },
  { border: '1px solid var(--color-tertiary-300)', countColor: 'var(--color-tertiary-700)', icon: pendingIcon },
  { border: '1px solid var(--color-secondary-400)', countColor: 'var(--color-secondary-700)', icon: completedIcon },
  { border: '1px solid var(--color-primary-400)', countColor: 'var(--color-primary-800)', icon: usedIcon },
];

interface DocumentStatusDashboardProps {
  refreshKey?: number;
}

function DocumentStatusDashboard({ refreshKey }: DocumentStatusDashboardProps) {
  const [items, setItems] = useState<DashboardItem[]>([
    { label: '업로드 완료', count: 0 },
    { label: '지식 추가 대기', count: 0 },
    { label: '지식 추가 완료', count: 0 },
    { label: '지식 활용 중', count: 0 },
  ]);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        const response = await apiClient.get<DocumentSummaryResponse>('/documents/summary');
        const data = response.data?.data;
        if (data) {
          setItems([
            { label: '업로드 완료', count: data.uploaded },
            { label: '지식 추가 대기', count: data.pendingApproval },
            { label: '지식 추가 완료', count: data.completed },
            { label: '지식 활용 중', count: data.enabled },
          ]);
        }
      } catch {
        // 실패 시 기본값(0) 유지
      }
    };
    fetchSummary();
  }, [refreshKey]);
  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      width: '100%',
      gap: '10px',
    }}>
      {items.map((item, index) => {
        const cardStyle = CARD_STYLES[index] || CARD_STYLES[0];
        return (
          <div key={item.label} style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            flex: 1,
            minWidth: 0,
          }}>
            <div style={{
              flex: 1,
              minWidth: 0,
              height: '82px',
              boxSizing: 'border-box' as const,
              padding: '10px 20px 12px 20px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              borderRadius: '8px',
              border: cardStyle.border,
              background: 'var(--color-grayscale-50)',
              boxShadow: '2px 2px 6px 0 rgba(0, 0, 0, 0.05)',
            }}>
              <span style={{
                color: 'var(--color-grayscale-400)',
                fontSize: '13px',
                fontWeight: '600',
                lineHeight: '20px',
                letterSpacing: '-0.26px',
                
                whiteSpace: 'nowrap',
              }}>
                {item.label}
              </span>
              <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
                <img src={cardStyle.icon} alt="" style={{ width: '32px', height: '32px' }} />
                <span style={{
                  color: cardStyle.countColor,
                  fontSize: '24px',
                  fontWeight: '600',
                  lineHeight: '28px',
                  letterSpacing: '-0.48px',
                  
                }}>
                  {item.count}
                </span>
              </div>
            </div>
            {index < items.length - 1 && (
              <img src={dashboardArrow} alt="" style={{ width: '16px', height: '16px', flexShrink: 0 }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default DocumentStatusDashboard;
