import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  OneToMany,
  JoinColumn,
  Index,
} from 'typeorm';
import { ChatSession } from './chat-session.entity';
import { ChatDocumentReference } from './chat-document-reference.entity';

/**
 * 1개 세션 단위 유저의 채팅 내역 (질문/답변)
 * type: 'Q' = 질문, 'A' = 답변
 * feedback: 'Y' = 좋아요, 'N' = 싫어요, null = 미제출 (기본값)
 */
@Entity('chat_interaction')
export class ChatInteraction {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_chat_interaction_type')
  @Column({ type: 'varchar', length: 10, default: 'Q' })
  type: string;

  @Column({ type: 'text' })
  content: string;

  @Column({ name: 'chat_turn', type: 'integer', default: 1 })
  chatTurn: number;

  @Column({ type: 'varchar', length: 10, nullable: true, default: null })
  feedback: string | null;

  @Column({ name: 'input_tokens', type: 'integer', nullable: true })
  inputTokens: number | null;

  @Column({ name: 'output_tokens', type: 'integer', nullable: true })
  outputTokens: number | null;

  @Column({ name: 'self_citation_count', type: 'integer', default: 0 })
  selfCitationCount: number;

  @Column({ name: 'other_citation_count', type: 'integer', default: 0 })
  otherCitationCount: number;

  @Index('idx_chat_interaction_session_id')
  @Column({ name: 'session_id', type: 'uuid' })
  sessionId: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => ChatSession, (session) => session.interactions, {
    onDelete: 'CASCADE',
  })
  @JoinColumn({ name: 'session_id' })
  session: ChatSession;

  @OneToMany(() => ChatDocumentReference, (ref) => ref.interaction)
  documentReferences: ChatDocumentReference[];
}
