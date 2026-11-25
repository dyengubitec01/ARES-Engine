/**
 * 사용성 설문 질문 매핑
 * DB 컬럼명 → 한글 질문 원문
 */
export const SURVEY_QUESTIONS = {
  // 로그인/회원가입 경험
  loginUnderstand:
    '로그인 화면에서 해당 서비스가 무엇인지 이해할 수 있었습니까?',
  loginSimple: '회원가입/로그인 과정은 빠르고 간결했습니까?',

  // 홈 화면 경험
  homeIntuitive: '첫 화면에서 무엇을 해야 하는지 바로 이해할 수 있었습니까?',
  homeInputPosition: '질문 입력창 위치와 크기는 적절했습니까?',
  homeNaturalStart: 'AI에게 질문을 시작하는 과정이 자연스러웠습니까?',

  // 채팅 및 AI 답변 품질
  chatSpeed: 'AI 답변 생성 속도는 적절했습니까?',
  chatEasy: 'AI 답변은 이해하기 쉬웠습니까?',
  chatLength: '답변 길이는 적절했습니까?',
  chatProcessHelpful:
    'AI가 답변 생성 과정을 보여주는 기능은 도움이 되었습니까?',

  // 출처 보기 기능
  sourceVisible: 'AI 답변에 출처가 제공된다는 것을 쉽게 인지할 수 있었습니까?',
  sourceUiEasy: '출처 패널 UI는 이해하기 쉬웠습니까?',
  sourceTrust: '출처 정보는 AI 답변을 신뢰하는 데 도움이 되었습니까?',

  // 문서함 기능
  docUploadEasy: '문서 업로드 과정은 이해하기 쉬웠습니까?',
  docStatusClear:
    '문서 상태(업로드중/승인대기/오류/사용가능)를 이해하기 쉬웠습니까?',
  docAiKnowledge: '"AI 지식 추가" 기능의 목적을 이해할 수 있었습니까?',

  // 업무 활용도
  workHelpful: '이 AI 서비스는 실제 업무에 도움이 될 것 같습니까?',
  workBetterThanLlm: '기존 AI LLM 서비스보다 업무 효율이 높아질 것 같습니까?',

  // 주관식
  bestFeature: '가장 좋았던 기능은 무엇인가요?',
  worstFeature: '사용하면서 가장 불편했던 점은 무엇인가요?',
  freeComment: '기타 자유 의견 및 개선 아이디어',
} as const;

/**
 * 설문 섹션 정의
 */
export const SURVEY_SECTIONS = {
  login: {
    title: '로그인/회원가입 경험',
    fields: ['loginUnderstand', 'loginSimple'],
  },
  home: {
    title: '홈 화면 경험',
    fields: ['homeIntuitive', 'homeInputPosition', 'homeNaturalStart'],
  },
  chat: {
    title: '채팅 및 AI 답변 품질',
    fields: ['chatSpeed', 'chatEasy', 'chatLength', 'chatProcessHelpful'],
  },
  source: {
    title: '채팅 - 출처 보기 기능',
    fields: ['sourceVisible', 'sourceUiEasy', 'sourceTrust'],
  },
  document: {
    title: '문서함 기능',
    fields: ['docUploadEasy', 'docStatusClear', 'docAiKnowledge'],
  },
  work: {
    title: '업무 활용도',
    fields: ['workHelpful', 'workBetterThanLlm'],
  },
  freeText: {
    title: '주관식',
    fields: ['bestFeature', 'worstFeature', 'freeComment'],
  },
} as const;

/** 점수형 필드 목록 (1~5) */
export const SURVEY_SCORE_FIELDS = [
  'loginUnderstand',
  'loginSimple',
  'homeIntuitive',
  'homeInputPosition',
  'homeNaturalStart',
  'chatSpeed',
  'chatEasy',
  'chatLength',
  'chatProcessHelpful',
  'sourceVisible',
  'sourceUiEasy',
  'sourceTrust',
  'docUploadEasy',
  'docStatusClear',
  'docAiKnowledge',
  'workHelpful',
  'workBetterThanLlm',
] as const;
