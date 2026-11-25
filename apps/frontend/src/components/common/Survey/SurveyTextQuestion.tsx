// created by ARES team [2026-04-28]
import { TextQuestion } from './surveySteps';

interface SurveyTextQuestionProps {
  question: TextQuestion;
  value: string;
  onChange: (value: string) => void;
}

function SurveyTextQuestion({ question, value, onChange }: SurveyTextQuestionProps) {
  return (
    <div
      style={{
        border: '1px solid var(--color-grayscale-200, #DDD)',
        borderRadius: '8px',
        padding: '16px 20px',
        backgroundColor: 'var(--color-grayscale-50)',
      }}
    >
      <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--color-grayscale-900)', marginBottom: '8px' }}>
        {question.label}
        {question.required ? (
          <span style={{ color: '#EF4444', marginLeft: '4px' }}>*</span>
        ) : (
          <span style={{ color: 'var(--color-grayscale-400)', fontSize: '12px', marginLeft: '6px' }}>(선택)</span>
        )}
      </div>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={question.required ? '내용을 입력해주세요.' : '자유롭게 의견을 남겨주세요.'}
        style={{
          width: '100%',
          minHeight: '72px',
          padding: '10px 14px',
          border: '1px solid var(--color-grayscale-150)',
          borderRadius: '8px',
          fontSize: '13px',
          color: 'var(--color-grayscale-900)',
          outline: 'none',
          resize: 'vertical',
          boxSizing: 'border-box',
          transition: 'border-color 0.2s',
        }}
        onFocus={(e) => { e.currentTarget.style.borderColor = 'var(--color-primary-600)'; }}
        onBlur={(e) => { e.currentTarget.style.borderColor = 'var(--color-grayscale-150)'; }}
      />
    </div>
  );
}

export default SurveyTextQuestion;