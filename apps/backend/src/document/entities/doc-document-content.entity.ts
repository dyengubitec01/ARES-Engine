import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  OneToMany,
  JoinColumn,
  Index,
} from 'typeorm';
import { DocStatus } from '../../common/enums';
import { DocDocument } from './doc-document.entity';
import { RagEmbeddingJob } from '../../rag/entities/rag-embedding-job.entity';
import { RagStatusEvent } from '../../rag/entities/rag-status-event.entity';
import { RagChunk } from '../../rag/entities/rag-chunk.entity';
import { RagEmbeddingsIndex } from '../../rag/entities/rag-embeddings-index.entity';
import { RagUpsertHistory } from '../../rag/entities/rag-upsert-history.entity';
import { RagProcessingStats } from '../../rag/entities/rag-processing-stats.entity';
import { StorageObjectFile } from '../../storage/entities/storage-object-file.entity';
import { ChatDocumentReference } from '../../chat/entities/chat-document-reference.entity';
import { DocDocumentExclude } from './doc-document-exclude.entity';

/**
 * 각 문서의 버전별 정보와 처리 상태를 관리
 */
@Entity('doc_document_content')
export class DocDocumentContent {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_doc_document_content_document_id')
  @Column({ name: 'document_id', type: 'uuid' })
  documentId: string;

  @Column({ name: 'version_no', type: 'integer' })
  versionNo: number;

  @Column({ name: 'original_filename', type: 'text' })
  originalFilename: string;

  @Index('idx_doc_document_content_uploader_id')
  @Column({ name: 'uploader_id', type: 'uuid' })
  uploaderId: string;

  @Column({ name: 'auth_dept_id', type: 'uuid', nullable: true })
  authDeptId: string | null;

  @Index('idx_doc_document_content_sha256', { unique: true })
  @Column({ type: 'char', length: 64, nullable: true })
  sha256: string | null;

  @Column({ name: 'file_size', type: 'bigint' })
  fileSize: number;

  @Column({ name: 'mime_type', type: 'text' })
  mimeType: string;

  @Column({ type: 'text', nullable: true })
  language: string;

  @Column({ type: 'text', nullable: true })
  encoding: string;

  @Index('idx_doc_document_content_status')
  @Column({
    type: 'enum',
    enum: DocStatus,
    enumName: 'doc_status',
    default: DocStatus.UPLOADED,
  })
  status: DocStatus;

  @Column({ name: 'status_reason', type: 'text', nullable: true })
  statusReason: string | null;

  @Column({ name: 'requested_at', type: 'timestamptz', nullable: true })
  requestedAt: Date | null;

  @Column({ name: 'queued_at', type: 'timestamptz', nullable: true })
  queuedAt: Date;

  @Column({ name: 'started_at', type: 'timestamptz', nullable: true })
  startedAt: Date;

  @Column({ name: 'finished_at', type: 'timestamptz', nullable: true })
  finishedAt: Date;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;

  @Column({ name: 'file_modified_at', type: 'timestamptz' })
  fileModifiedAt: Date;

  @Index('idx_doc_document_content_deleted_at')
  @Column({ name: 'deleted_at', type: 'timestamptz', nullable: true })
  deletedAt: Date | null;

  @Column({ name: 'is_active', type: 'char', length: 1, default: 'Y' })
  isActive: string;

  // Relations
  @ManyToOne(() => DocDocument, (doc) => doc.contents, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'document_id' })
  document: DocDocument;

  @OneToMany(() => RagEmbeddingJob, (job) => job.docContent)
  embeddingJobs: RagEmbeddingJob[];

  @OneToMany(() => RagStatusEvent, (event) => event.docContent)
  statusEvents: RagStatusEvent[];

  @OneToMany(() => RagChunk, (chunk) => chunk.docContent)
  chunks: RagChunk[];

  @OneToMany(() => RagEmbeddingsIndex, (index) => index.docContent)
  embeddingsIndices: RagEmbeddingsIndex[];

  @OneToMany(() => RagUpsertHistory, (history) => history.docContent)
  upsertHistories: RagUpsertHistory[];

  @OneToMany(() => RagProcessingStats, (stats) => stats.docContent)
  processingStats: RagProcessingStats[];

  @OneToMany(() => StorageObjectFile, (file) => file.docContent)
  storageFiles: StorageObjectFile[];

  @OneToMany(() => ChatDocumentReference, (ref) => ref.docContent)
  chatDocumentReferences: ChatDocumentReference[];

  @OneToMany(() => DocDocumentExclude, (ex) => ex.documentContent)
  excludes: DocDocumentExclude[];
}
