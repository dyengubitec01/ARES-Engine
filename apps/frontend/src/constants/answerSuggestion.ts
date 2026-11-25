// created by ARES team [2026-06-01]
// 정답 데이터 신고하기 도메인 상수

export const LLM_SERVICE_NAME = 'ARES';

export const ANSWER_ERROR_TYPES = [
  '현실 왜곡',
  '계산 오류',
  '최신 정보 미반영',
  '답변거부/회피',
  '기타',
] as const;

export type AnswerErrorType = (typeof ANSWER_ERROR_TYPES)[number];

export interface AnswerCase {
  aiServiceName: string;
  errorType: AnswerErrorType;
  inputSentence: string;
  correctContent: string;
  imageObjectKey: string | null;
}

export interface AnswerContent {
  cases: AnswerCase[];
}
