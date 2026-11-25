import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { EventSource } from '../../common/enums';
import { DocDocumentContent } from '../../document/entities/doc-document-content.entity';
import { RagEmbeddingJob } from './rag-embedding-job.entity';

/**
 * 문서 버전 단위로 발생하는 상태 변경 이벤트 로그(append-only)
 */
@Entity('rag_status_events')
export class RagStatusEvent {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_rag_status_events_doc_content_id')
  @Column({ name: 'doc_content_id', type: 'uuid' })
  docContentId: string;

  @Index('idx_rag_status_events_job_id')
  @Column({ name: 'job_id', type: 'uuid', nullable: true })
  jobId: string;

  @Column({
    type: 'enum',
    enum: EventSource,
    enumName: 'event_source',
  })
  source: EventSource;

  @Column({ type: 'varchar', length: 32, default: 'job' })
  category: string;

  @Column({ type: 'text', nullable: true })
  message: string;

  @Column({ type: 'jsonb', nullable: true })
  metadata: object;

  @Column({ type: 'text' })
  status: string;

  @Index('idx_rag_status_events_created_at')
  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => DocDocumentContent, (content) => content.statusEvents)
  @JoinColumn({ name: 'doc_content_id' })
  docContent: DocDocumentContent;

  @ManyToOne(() => RagEmbeddingJob, (job) => job.statusEvents)
  @JoinColumn({ name: 'job_id' })
  job: RagEmbeddingJob;
}
