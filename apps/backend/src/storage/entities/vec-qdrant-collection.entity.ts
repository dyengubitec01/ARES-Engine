import {
  Entity,
  PrimaryColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  OneToMany,
} from 'typeorm';
import { DistanceMetric } from '../../common/enums';
import { RagEmbeddingsIndex } from '../../rag/entities/rag-embeddings-index.entity';

/**
 * Qdrant에 존재하는 컬렉션에 대한 구성 정보 메타를 RDB에 복제해 관리
 */
@Entity('vec_qdrant_collections')
export class VecQdrantCollection {
  @PrimaryColumn({ type: 'varchar', length: 100 })
  name: string;

  @Column({ name: 'vector_dim', type: 'integer' })
  vectorDim: number;

  @Column({
    type: 'enum',
    enum: DistanceMetric,
    enumName: 'distance_metric',
  })
  metric: DistanceMetric;

  @Column({ name: 'shard_count', type: 'integer' })
  shardCount: number;

  @Column({ name: 'replication_factor', type: 'integer' })
  replicationFactor: number;

  @Column({ name: 'write_consistency', type: 'varchar', length: 20 })
  writeConsistency: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;

  // Relations
  @OneToMany(() => RagEmbeddingsIndex, (index) => index.qdrantCollection)
  embeddingsIndices: RagEmbeddingsIndex[];
}
