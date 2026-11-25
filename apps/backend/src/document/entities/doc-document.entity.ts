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
import { AuthUser } from '../../auth/entities/auth-user.entity';
import { DocDocumentContent } from './doc-document-content.entity';
import { DocDocumentFavorite } from './doc-document-favorite.entity';
import { AuthUsersAlarm } from '../../auth/entities/auth-users-alarm.entity';

/**
 * "문서"라는 개념의 최상위 ID를 관리
 */
@Entity('doc_documents')
export class DocDocument {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'text', nullable: true })
  title: string;

  @Column({ name: 'minio_url', type: 'varchar' })
  minioUrl: string;

  @Index('idx_doc_documents_created_by')
  @Column({ name: 'created_by', type: 'uuid' })
  createdBy: string;

  @Index('idx_doc_documents_created_at')
  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => AuthUser, (user) => user.createdDocuments)
  @JoinColumn({ name: 'created_by' })
  createdByUser: AuthUser;

  @OneToMany(() => DocDocumentContent, (content) => content.document)
  contents: DocDocumentContent[];

  @OneToMany(() => DocDocumentFavorite, (fav) => fav.document)
  favorites: DocDocumentFavorite[];

  @OneToMany(() => AuthUsersAlarm, (alarm) => alarm.document)
  alarms: AuthUsersAlarm[];
}
