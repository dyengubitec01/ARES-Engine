// created by ARES team [2026-04-28]

export interface RatingQuestion {
  key: string;
  label: string;
}

export interface TextQuestion {
  key: string;
  label: string;
  required: boolean;
}

export interface RatingStep {
  type: 'rating';
  title: string;
  questions: RatingQuestion[];
}

export interface TextStep {
  type: 'text';
  title: string;
  questions: TextQuestion[];
}

export type Step = RatingStep | TextStep;

export const STEPS: Step[] = [
  {
    type: 'rating',
    title: '로그인',
    questions: [
      { key: 'loginUnderstand', label: '로그인 과정을 이해하기 쉬웠다' },
      { key: 'loginSimple', label: '로그인 과정이 간단했다' },
    ],
  },
  {
    type: 'rating',
    title: '홈',
    questions: [
      { key: 'homeIntuitive', label: '홈 화면이 직관적이었다' },
      { key: 'homeInputPosition', label: '입력창 위치가 적절했다' },
      { key: 'homeNaturalStart', label: '자연스럽게 시작할 수 있었다' },
    ],
  },
  {
    type: 'rating',
    title: '채팅',
    questions: [
      { key: 'chatSpeed', label: 'AI 답변 속도가 만족스러웠다' },
      { key: 'chatEasy', label: '채팅 인터페이스가 사용하기 쉬웠다' },
      { key: 'chatLength', label: '답변 길이가 적절했다' },
      { key: 'chatProcessHelpful', label: 'AI 답변이 업무에 도움이 되었다' },
    ],
  },
  {
    type: 'rating',
    title: '채팅 - 출처 보기',
    questions: [
      { key: 'sourceVisible', label: '출처 문서가 잘 보였다' },
      { key: 'sourceUiEasy', label: '출처 보기 UI가 사용하기 쉬웠다' },
      { key: 'sourceTrust', label: '출처 정보를 신뢰할 수 있었다' },
    ],
  },
  {
    type: 'rating',
    title: '문서함',
    questions: [
      { key: 'docUploadEasy', label: '문서 업로드가 쉬웠다' },
      { key: 'docStatusClear', label: '문서 상태가 명확하게 표시되었다' },
      { key: 'docAiKnowledge', label: 'AI가 문서 내용을 잘 이해하는 것 같았다' },
    ],
  },
  {
    type: 'rating',
    title: '업무 활용도',
    questions: [
      { key: 'workHelpful', label: '업무에 전반적으로 도움이 되었다' },
      { key: 'workBetterThanLlm', label: '일반 LLM보다 더 유용했다' },
    ],
  },
  {
    type: 'text',
    title: '여러분의 목소리',
    questions: [
      { key: 'bestFeature', label: '가장 좋았던 기능', required: true },
      { key: 'worstFeature', label: '가장 아쉬웠던 점', required: true },
      { key: 'freeComment', label: '자유 의견', required: false },
    ],
  },
];

export const RATING_LABELS = ['전혀 아니다', '아니다', '보통', '그렇다', '매우 그렇다'];