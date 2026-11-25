import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { AuthUser } from './auth-user.entity';
import { DocDocument } from '../../document/entities/doc-document.entity';
import { BoardPost } from '../../board/entities/board-post.entity';

/**
 * 유저가 전달 받을 상태 이벤트 알람 테이블
 */
@Entity('auth_users_alarm')
export class AuthUsersAlarm {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_auth_users_alarm_users_id')
  @Column({ name: 'users_id', type: 'uuid' })
  usersId: string;

  @Column({ name: 'document_id', type: 'uuid', nullable: true })
  documentId: string | null;

  @Column({ name: 'post_id', type: 'uuid', nullable: true })
  postId: string | null;

  @Column({ type: 'varchar', length: 255, nullable: true })
  message: string;

  @Index('idx_auth_users_alarm_is_read')
  @Column({ name: 'is_read', type: 'varchar', length: 10, default: 'N' })
  isRead: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => AuthUser, (user) => user.alarms)
  @JoinColumn({ name: 'users_id' })
  user: AuthUser;

  @ManyToOne(() => DocDocument, (doc) => doc.alarms, {
    nullable: true,
    onDelete: 'CASCADE',
  })
  @JoinColumn({ name: 'document_id' })
  document: DocDocument;

  @ManyToOne(() => BoardPost, { nullable: true, onDelete: 'CASCADE' })
  @JoinColumn({ name: 'post_id' })
  post: BoardPost;
}
