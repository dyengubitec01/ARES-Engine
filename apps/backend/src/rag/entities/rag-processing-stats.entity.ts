import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { DocDocumentContent } from '../../document/entities/doc-document-content.entity';

/**
 * 문서 버전 단위로 임베딩 처리 결과 요약 통계를 저장
 */
@Entity('rag_processing_stats')
export class RagProcessingStats {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_rag_processing_stats_doc_content_id')
  @Column({ name: 'doc_content_id', type: 'uuid' })
  docContentId: string;

  @Column({ name: 'model_name', type: 'varchar', length: 100 })
  modelName: string;

  @Column({ name: 'model_version', type: 'varchar', length: 50 })
  modelVersion: string;

  @Column({ name: 'vector_dim', type: 'integer' })
  vectorDim: number;

  @Column({ name: 'total_chunks', type: 'integer' })
  totalChunks: number;

  @Column({ name: 'success_chunks', type: 'integer' })
  successChunks: number;

  @Column({ name: 'failed_chunks', type: 'integer' })
  failedChunks: number;

  @Column({ name: 'total_tokens', type: 'bigint', default: 0 })
  totalTokens: number;

  @Column({ name: 'embed_ms', type: 'bigint', default: 0 })
  embedMs: number;

  @Column({
    name: 'content_type',
    type: 'varchar',
    length: 255,
    default: 'application/octet-stream',
  })
  contentType: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => DocDocumentContent, (content) => content.processingStats)
  @JoinColumn({ name: 'doc_content_id' })
  docContent: DocDocumentContent;
}
