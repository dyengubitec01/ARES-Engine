import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
  Unique,
} from 'typeorm';
import { DocDocumentContent } from './doc-document-content.entity';
import { AuthUser } from '../../auth/entities/auth-user.entity';

/**
 * 사용자별 RAG 참조 제외 문서 버전 목록
 * 레코드 있음 = OFF(제외), 없음 = ON(참조 가능, 기본값)
 */
@Entity('doc_document_exclude')
@Unique(['userId', 'documentContentId'])
export class DocDocumentExclude {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_doc_document_exclude_content_id')
  @Column({ name: 'document_content_id', type: 'uuid' })
  documentContentId: string;

  @Index('idx_doc_document_exclude_user_id')
  @Column({ name: 'user_id', type: 'uuid' })
  userId: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => DocDocumentContent, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'document_content_id' })
  documentContent: DocDocumentContent;

  @ManyToOne(() => AuthUser, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'user_id' })
  user: AuthUser;
}
