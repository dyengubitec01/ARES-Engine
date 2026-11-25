import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { JobStatus } from '../../common/enums';
import { DocDocumentContent } from '../../document/entities/doc-document-content.entity';
import { RagChunk } from './rag-chunk.entity';
import { RagEmbeddingJob } from './rag-embedding-job.entity';

/**
 * 각 청크에 대해 Qdrant 업서트를 몇 번 시도했고, 어떤 결과였는지를 기록
 */
@Entity('rag_upsert_history')
export class RagUpsertHistory {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_rag_upsert_history_doc_content_id')
  @Column({ name: 'doc_content_id', type: 'uuid' })
  docContentId: string;

  @Index('idx_rag_upsert_history_chunk_id')
  @Column({ name: 'chunk_id', type: 'uuid' })
  chunkId: string;

  @Index('idx_rag_upsert_history_job_id')
  @Column({ name: 'job_id', type: 'uuid' })
  jobId: string;

  @Column({ name: 'chunk_index', type: 'integer' })
  chunkIndex: number;

  @Column({ name: 'qdrant_collection_name', type: 'varchar', length: 255 })
  qdrantCollectionName: string;

  @Column({ name: 'qdrant_point_id', type: 'varchar', length: 128 })
  qdrantPointId: string;

  @Column({ name: 'vector_dim', type: 'integer' })
  vectorDim: number;

  @Column({
    type: 'enum',
    enum: JobStatus,
    enumName: 'job_status',
  })
  status: JobStatus;

  @Column({ name: 'error_message', type: 'text', nullable: true })
  errorMessage: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => DocDocumentContent, (content) => content.upsertHistories)
  @JoinColumn({ name: 'doc_content_id' })
  docContent: DocDocumentContent;

  @ManyToOne(() => RagChunk, (chunk) => chunk.upsertHistories)
  @JoinColumn({ name: 'chunk_id' })
  chunk: RagChunk;

  @ManyToOne(() => RagEmbeddingJob, (job) => job.upsertHistories)
  @JoinColumn({ name: 'job_id' })
  job: RagEmbeddingJob;
}
