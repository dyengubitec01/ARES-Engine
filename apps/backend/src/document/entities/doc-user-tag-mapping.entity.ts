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
import { AuthUser } from '../../auth/entities/auth-user.entity';
import { DocDocument } from './doc-document.entity';
import { DocUserTag } from './doc-user-tag.entity';

@Entity('doc_user_tag_mappings')
@Unique('UQ_doc_user_tag_mappings_user_tag_doc', [
  'userId',
  'tagId',
  'documentId',
])
export class DocUserTagMapping {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_doc_user_tag_mappings_user_id')
  @Column({ name: 'user_id', type: 'uuid' })
  userId: string;

  @Index('idx_doc_user_tag_mappings_tag_id')
  @Column({ name: 'tag_id', type: 'uuid' })
  tagId: string;

  @Index('idx_doc_user_tag_mappings_document_id')
  @Column({ name: 'document_id', type: 'uuid' })
  documentId: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @ManyToOne(() => AuthUser, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'user_id' })
  user: AuthUser;

  @ManyToOne(() => DocUserTag, (t) => t.mappings, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'tag_id' })
  tag: DocUserTag;

  @ManyToOne(() => DocDocument, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'document_id' })
  document: DocDocument;
}
