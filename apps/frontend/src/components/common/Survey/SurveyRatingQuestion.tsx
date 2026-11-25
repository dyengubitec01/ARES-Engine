// created by ARES team [2026-04-28]
import { RatingQuestion, RATING_LABELS } from './surveySteps';

interface SurveyRatingQuestionProps {
  question: RatingQuestion;
  value: number | undefined;
  onChange: (value: number) => void;
}

function SurveyRatingQuestion({ question, value, onChange }: SurveyRatingQuestionProps) {
  return (
    <div
      style={{
        border: '1px solid var(--color-grayscale-200, #DDD)',
        borderRadius: '8px',
        padding: '16px 20px',
        backgroundColor: 'var(--color-grayscale-50)',
      }}
    >
      <div style={{ fontSize: '14px', fontStyle: 'normal', fontWeight: 500, color: 'var(--color-grayscale-900)', marginBottom: '12px' }}>
        {question.label}
      </div>
      <div style={{ display: 'flex', gap: '0', justifyContent: 'space-between' }}>
        {RATING_LABELS.map((label, idx) => {
          const optionValue = idx + 1;
          const isSelected = value === optionValue;
          return (
            <label
              key={optionValue}
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
                flex: 1,
              }}
            >
              <input
                type="radio"
                name={question.key}
                value={optionValue}
                checked={isSelected}
                onChange={() => onChange(optionValue)}
                style={{ display: 'none' }}
              />
              <div style={{
                width: '20px',
                height: '20px',
                borderRadius: '50%',
                border: isSelected ? '2px solid var(--color-primary-600)' : '2px solid var(--color-grayscale-300)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'border-color 0.2s',
              }}>
                {isSelected && (
                  <div style={{
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--color-primary-600)',
                  }} />
                )}
              </div>
              <span style={{
                fontSize: '11px',
                color: isSelected ? 'var(--color-primary-600)' : 'var(--color-grayscale-400)',
                fontWeight: isSelected ? 600 : 400,
                whiteSpace: 'nowrap',
                transition: 'color 0.2s',
              }}>
                {label}
              </span>
            </label>
          );
        })}
      </div>
    </div>
  );
}

export default SurveyRatingQuestion;