// created by ARES team [2026-04-28]

interface SurveyProgressHeaderProps {
  title: string;
  subtitle: string;
  progressPercent: number;
}

function SurveyProgressHeader({ title, subtitle, progressPercent }: SurveyProgressHeaderProps) {
  return (
    <div style={{ padding: '40px 40px 0', flexShrink: 0 }}>
      <div style={{ marginBottom: '4px' }}>
        <span style={{ color: 'var(--color-grayscale-900, #31343E)', textAlign: 'center', fontSize: '24px', fontStyle: 'normal', fontWeight: 600, lineHeight: '28px', letterSpacing: '-0.48px' }}>
          {title}
        </span>
      </div>
      <div style={{ marginBottom: '16px', color: 'var(--color-grayscale-400, #8E8E8E)', fontSize: '14px', fontStyle: 'normal', fontWeight: 400, lineHeight: '20px', letterSpacing: '-0.28px' }}>
        {subtitle}
      </div>
      <div style={{
        width: '100%',
        height: '4px',
        backgroundColor: 'var(--color-grayscale-150)',
        borderRadius: '2px',
        overflow: 'hidden',
      }}>
        <div style={{
          width: `${progressPercent}%`,
          height: '100%',
          backgroundColor: 'var(--color-primary-400, #B4BDFA)',
          borderRadius: '2px',
          transition: 'width 0.3s ease',
        }} />
      </div>
    </div>
  );
}

export default SurveyProgressHeader;