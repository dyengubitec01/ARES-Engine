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
import { DocDocumentContent } from '../../document/entities/doc-document-content.entity';
import { RagEmbeddingsIndex } from './rag-embeddings-index.entity';
import { RagUpsertHistory } from './rag-upsert-history.entity';

/**
 * 파싱된 문서를 여러 청크로 나눈 결과를 관리
 */
@Entity('rag_chunks')
export class RagChunk {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_rag_chunks_doc_content_id')
  @Column({ name: 'doc_content_id', type: 'uuid' })
  docContentId: string;

  @Column({ name: 'chunk_index', type: 'integer' })
  chunkIndex: number;

  @Column({ name: 'ref_hash', type: 'varchar', length: 128, nullable: true })
  refHash: string;

  @Column({ type: 'text', nullable: true })
  text: string;

  @Column({
    name: 'text_checksum',
    type: 'varchar',
    length: 64,
    nullable: true,
  })
  textChecksum: string;

  @Column({ name: 'page_start', type: 'integer', nullable: true })
  pageStart: number;

  @Column({ name: 'page_end', type: 'integer', nullable: true })
  pageEnd: number;

  @Column({ name: 'sheet_name', type: 'varchar', length: 255, nullable: true })
  sheetName: string;

  @Column({ name: 'row_start', type: 'integer', nullable: true })
  rowStart: number;

  @Column({ name: 'row_end', type: 'integer', nullable: true })
  rowEnd: number;

  @Column({ type: 'jsonb', nullable: true })
  metadata: object;

  @Column({ name: 'start_char', type: 'integer', nullable: true })
  startChar: number;

  @Column({ name: 'end_char', type: 'integer', nullable: true })
  endChar: number;

  @Column({ name: 'token_count', type: 'integer' })
  tokenCount: number;

  @Index('idx_rag_chunks_text_hash')
  @Column({ name: 'text_hash', type: 'char', length: 64 })
  textHash: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => DocDocumentContent, (content) => content.chunks)
  @JoinColumn({ name: 'doc_content_id' })
  docContent: DocDocumentContent;

  @OneToMany(() => RagEmbeddingsIndex, (index) => index.chunk)
  embeddingsIndices: RagEmbeddingsIndex[];

  @OneToMany(() => RagUpsertHistory, (history) => history.chunk)
  upsertHistories: RagUpsertHistory[];
}
