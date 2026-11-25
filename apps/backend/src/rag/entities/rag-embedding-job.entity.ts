import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  ManyToOne,
  OneToMany,
  JoinColumn,
  Index,
} from 'typeorm';
import { JobStatus } from '../../common/enums';
import { DocDocumentContent } from '../../document/entities/doc-document-content.entity';
import { RagStatusEvent } from './rag-status-event.entity';
import { RagUpsertHistory } from './rag-upsert-history.entity';

/**
 * BE/ER에서 생성해 Kafka로 발행하는 임베딩 작업 단위(Job)를 관리
 */
@Entity('rag_embedding_jobs')
export class RagEmbeddingJob {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_rag_embedding_jobs_doc_content_id')
  @Column({ name: 'doc_content_id', type: 'uuid' })
  docContentId: string;

  @Column({ name: 'kafka_topic', type: 'varchar', length: 100 })
  kafkaTopic: string;

  @Column({ name: 'kafka_key', type: 'varchar', length: 200 })
  kafkaKey: string;

  @Column({ type: 'integer', nullable: true })
  partition: number;

  @Column({ type: 'bigint', nullable: true })
  offset: number;

  @Column({ type: 'integer', default: 0 })
  priority: number;

  @Column({ name: 'retry_count', type: 'integer', default: 0 })
  retryCount: number;

  @Column({ name: 'payload_json', type: 'json', nullable: true })
  payloadJson: object;

  @Index('idx_rag_embedding_jobs_status')
  @Column({
    type: 'enum',
    enum: JobStatus,
    enumName: 'job_status',
    default: JobStatus.QUEUED,
  })
  status: JobStatus;

  @Index('idx_rag_embedding_jobs_enqueued_at')
  @Column({ name: 'enqueued_at', type: 'timestamptz', default: () => 'now()' })
  enqueuedAt: Date;

  @Column({ name: 'started_at', type: 'timestamptz', nullable: true })
  startedAt: Date;

  @Column({ name: 'finished_at', type: 'timestamptz', nullable: true })
  finishedAt: Date;

  @Column({
    name: 'minio_original_filename',
    type: 'varchar',
    length: 255,
    nullable: true,
  })
  minioOriginalFilename: string;

  @Column({
    name: 'minio_mime_type',
    type: 'varchar',
    length: 128,
    nullable: true,
  })
  minioMimeType: string;

  @Column({ name: 'minio_file_size', type: 'bigint', nullable: true })
  minioFileSize: number;

  @Column({ name: 'worker_id', type: 'varchar', length: 100, nullable: true })
  workerId: string;

  @Column({ name: 'error_message', type: 'text', nullable: true })
  errorMessage: string;

  // Relations
  @ManyToOne(() => DocDocumentContent, (content) => content.embeddingJobs)
  @JoinColumn({ name: 'doc_content_id' })
  docContent: DocDocumentContent;

  @OneToMany(() => RagStatusEvent, (event) => event.job)
  statusEvents: RagStatusEvent[];

  @OneToMany(() => RagUpsertHistory, (history) => history.job)
  upsertHistories: RagUpsertHistory[];
}
