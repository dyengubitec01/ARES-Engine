import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { ObjectKind } from '../../common/enums';
import { DocDocumentContent } from '../../document/entities/doc-document-content.entity';
import { AuthUser } from '../../auth/entities/auth-user.entity';

/**
 * MinIO에 저장된 파일들에 대한 메타데이터를 RDB에서 관리하는 테이블
 */
@Entity('storage_object_files')
export class StorageObjectFile {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_storage_object_files_doc_content_id')
  @Column({ name: 'doc_content_id', type: 'uuid' })
  docContentId: string;

  @Index('idx_storage_object_files_kind')
  @Column({
    type: 'enum',
    enum: ObjectKind,
    enumName: 'object_kind',
  })
  kind: ObjectKind;

  @Index('idx_storage_object_files_bucket')
  @Column({ type: 'varchar', length: 63 })
  bucket: string;

  @Column({ name: 'object_key', type: 'text' })
  objectKey: string;

  @Column({ type: 'varchar', length: 64, nullable: true })
  etag: string;

  @Column({ type: 'char', length: 64, nullable: true })
  sha256: string;

  @Column({ name: 'size_bytes', type: 'bigint' })
  sizeBytes: number;

  @Column({ type: 'jsonb', default: {} })
  metadata: object;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @Column({ name: 'created_by', type: 'uuid', nullable: true })
  createdBy: string;

  // Relations
  @ManyToOne(() => DocDocumentContent, (content) => content.storageFiles, {
    onDelete: 'CASCADE',
  })
  @JoinColumn({ name: 'doc_content_id' })
  docContent: DocDocumentContent;

  @ManyToOne(() => AuthUser, (user) => user.storageFiles)
  @JoinColumn({ name: 'created_by' })
  createdByUser: AuthUser;
}
