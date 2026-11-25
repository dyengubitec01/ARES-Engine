import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  Index,
  ManyToOne,
  JoinColumn,
  Unique,
} from 'typeorm';
import { AuthUser } from './auth-user.entity';

@Entity('auth_users_login_history')
@Unique('uq_login_history_user_date', ['userId', 'uniqueLoginDate'])
export class AuthUsersLoginHistory {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_login_history_user_id')
  @Column({ name: 'user_id', type: 'uuid' })
  userId: string;

  @Index('idx_login_history_date')
  @Column({ name: 'unique_login_date', type: 'date' })
  uniqueLoginDate: string;

  @Column({ name: 'logged_in_at', type: 'timestamptz', default: () => 'now()' })
  loggedInAt: Date;

  @ManyToOne(() => AuthUser)
  @JoinColumn({ name: 'user_id' })
  user: AuthUser;
}
