import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { DocDocument } from './doc-document.entity';
import { AuthUser } from '../../auth/entities/auth-user.entity';

/**
 * 유저의 문서 즐겨찾기
 */
@Entity('doc_document_favorites')
export class DocDocumentFavorite {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_doc_document_favorites_document_id')
  @Column({ name: 'document_id', type: 'uuid' })
  documentId: string;

  @Index('idx_doc_document_favorites_users_id')
  @Column({ name: 'users_id', type: 'uuid' })
  usersId: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => DocDocument, (doc) => doc.favorites, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'document_id' })
  document: DocDocument;

  @ManyToOne(() => AuthUser, (user) => user.favorites)
  @JoinColumn({ name: 'users_id' })
  user: AuthUser;
}
