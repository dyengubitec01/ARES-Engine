import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { DocDocumentContent } from './doc-document-content.entity';
import { AuthUser } from '../../auth/entities/auth-user.entity';

@Entity('doc_embed_review')
export class DocEmbedReview {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_doc_embed_review_doc_content_id')
  @Column({ name: 'doc_content_id', type: 'uuid' })
  docContentId: string;

  @Index('idx_doc_embed_review_reviewer_id')
  @Column({ name: 'reviewer_id', type: 'uuid' })
  reviewerId: string;

  @Column({ type: 'varchar', length: 10 })
  action: 'approve' | 'reject';

  @Column({ type: 'varchar', length: 500, nullable: true })
  reason: string | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => DocDocumentContent, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'doc_content_id' })
  content: DocDocumentContent;

  @ManyToOne(() => AuthUser)
  @JoinColumn({ name: 'reviewer_id' })
  reviewer: AuthUser;
}
