import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { BoardPost } from './board-post.entity';
import { AuthUser } from '../../auth/entities/auth-user.entity';

/**
 * suggestion 게시글의 평가위원회 채택 결과
 * - post_id UNIQUE: 게시글당 채택 1회
 * - grade: 50~200
 * - 월 4건 cap 은 Materialized View 계산에서 적용
 */
@Entity('board_post_adoptions')
export class BoardPostAdoption {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_board_post_adoptions_post_id')
  @Column({ name: 'post_id', type: 'uuid', unique: true })
  postId: string;

  @Column({ type: 'integer' })
  grade: number;

  @Column({ name: 'reviewer_id', type: 'uuid' })
  reviewerId: string;

  @Index('idx_board_post_adoptions_reviewed_at')
  @Column({ name: 'reviewed_at', type: 'timestamptz', default: () => 'now()' })
  reviewedAt: Date;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @ManyToOne(() => BoardPost, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'post_id' })
  post: BoardPost;

  @ManyToOne(() => AuthUser)
  @JoinColumn({ name: 'reviewer_id' })
  reviewer: AuthUser;
}
