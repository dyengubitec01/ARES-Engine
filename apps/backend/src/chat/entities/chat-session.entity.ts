import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  DeleteDateColumn,
  ManyToOne,
  OneToMany,
  JoinColumn,
  Index,
} from 'typeorm';
import { AuthUser } from '../../auth/entities/auth-user.entity';
import { ChatInteraction } from './chat-interaction.entity';

/**
 * 유저가 생성한 채팅 1개 세션 단위
 */
@Entity('chat_session')
export class ChatSession {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({ type: 'varchar', length: 255, nullable: true })
  title: string | null;

  @Column({ type: 'varchar', length: 10, default: 'N' })
  favorites: string;

  @Index('idx_chat_session_users_id')
  @Column({ name: 'users_id', type: 'uuid' })
  usersId: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @DeleteDateColumn({ name: 'deleted_at', type: 'timestamptz', nullable: true })
  deletedAt: Date | null;

  // Relations
  @ManyToOne(() => AuthUser, (user) => user.chatSessions)
  @JoinColumn({ name: 'users_id' })
  user: AuthUser;

  @OneToMany(() => ChatInteraction, (interaction) => interaction.session)
  interactions: ChatInteraction[];
}
