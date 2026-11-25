import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { DocDocumentContent } from '../../document/entities/doc-document-content.entity';
import { RagChunk } from './rag-chunk.entity';
import { VecQdrantCollection } from '../../storage/entities/vec-qdrant-collection.entity';

/**
 * 각 청크(chunk_id)가 Qdrant에 어떤 컬렉션/point_id로 저장돼 있는지를 매핑
 */
@Entity('rag_embeddings_index')
export class RagEmbeddingsIndex {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_rag_embeddings_index_doc_content_id')
  @Column({ name: 'doc_content_id', type: 'uuid' })
  docContentId: string;

  @Index('idx_rag_embeddings_index_chunk_id')
  @Column({ name: 'chunk_id', type: 'uuid' })
  chunkId: string;

  @Column({ name: 'chunk_index', type: 'integer' })
  chunkIndex: number;

  @Column({ name: 'qdrant_point_id', type: 'varchar', length: 128 })
  qdrantPointId: string;

  @Index('idx_rag_embeddings_index_qdrant_collection')
  @Column({ name: 'qdrant_collection_name', type: 'varchar', length: 100 })
  qdrantCollectionName: string;

  @Column({
    name: 'qdrant_vector_checksum',
    type: 'varchar',
    length: 128,
    nullable: true,
  })
  qdrantVectorChecksum: string;

  @Column({
    name: 'qdrant_payload_checksum',
    type: 'varchar',
    length: 128,
    nullable: true,
  })
  qdrantPayloadChecksum: string;

  @Column({ name: 'vector_dim', type: 'integer' })
  vectorDim: number;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz', nullable: true })
  updatedAt: Date;

  // Relations
  @ManyToOne(() => DocDocumentContent, (content) => content.embeddingsIndices)
  @JoinColumn({ name: 'doc_content_id' })
  docContent: DocDocumentContent;

  @ManyToOne(() => RagChunk, (chunk) => chunk.embeddingsIndices)
  @JoinColumn({ name: 'chunk_id' })
  chunk: RagChunk;

  @ManyToOne(
    () => VecQdrantCollection,
    (collection) => collection.embeddingsIndices,
  )
  @JoinColumn({ name: 'qdrant_collection_name', referencedColumnName: 'name' })
  qdrantCollection: VecQdrantCollection;
}
