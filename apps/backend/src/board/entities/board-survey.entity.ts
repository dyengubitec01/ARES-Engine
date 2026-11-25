import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  Index,
} from 'typeorm';

@Entity('board_surveys')
export class BoardSurvey {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_board_surveys_user_id')
  @Column({ name: 'user_id', type: 'uuid' })
  userId: string;

  // 로그인/회원가입 경험
  @Column({ name: 'login_understand', type: 'smallint' })
  loginUnderstand: number;

  @Column({ name: 'login_simple', type: 'smallint' })
  loginSimple: number;

  // 홈 화면 경험
  @Column({ name: 'home_intuitive', type: 'smallint' })
  homeIntuitive: number;

  @Column({ name: 'home_input_position', type: 'smallint' })
  homeInputPosition: number;

  @Column({ name: 'home_natural_start', type: 'smallint' })
  homeNaturalStart: number;

  // 채팅 및 AI 답변 품질
  @Column({ name: 'chat_speed', type: 'smallint' })
  chatSpeed: number;

  @Column({ name: 'chat_easy', type: 'smallint' })
  chatEasy: number;

  @Column({ name: 'chat_length', type: 'smallint' })
  chatLength: number;

  @Column({ name: 'chat_process_helpful', type: 'smallint' })
  chatProcessHelpful: number;

  // 출처 보기 기능
  @Column({ name: 'source_visible', type: 'smallint' })
  sourceVisible: number;

  @Column({ name: 'source_ui_easy', type: 'smallint' })
  sourceUiEasy: number;

  @Column({ name: 'source_trust', type: 'smallint' })
  sourceTrust: number;

  // 문서함 기능
  @Column({ name: 'doc_upload_easy', type: 'smallint' })
  docUploadEasy: number;

  @Column({ name: 'doc_status_clear', type: 'smallint' })
  docStatusClear: number;

  @Column({ name: 'doc_ai_knowledge', type: 'smallint' })
  docAiKnowledge: number;

  // 업무 활용도
  @Column({ name: 'work_helpful', type: 'smallint' })
  workHelpful: number;

  @Column({ name: 'work_better_than_llm', type: 'smallint' })
  workBetterThanLlm: number;

  // 주관식
  @Column({ name: 'best_feature', type: 'text' })
  bestFeature: string;

  @Column({ name: 'worst_feature', type: 'text' })
  worstFeature: string;

  @Column({ name: 'free_comment', type: 'text', nullable: true })
  freeComment: string | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;
}
