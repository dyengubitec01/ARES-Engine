import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { AuthUsersAuthority } from './auth-users-authority.entity';
import { AuthUser } from './auth-user.entity';

/**
 * 유저가 가진 권한들을 관리하는 테이블
 */
@Entity('auth_users_authority_permission')
export class AuthUsersAuthorityPermission {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_auth_users_authority_permission_authority_id')
  @Column({ name: 'authority_id', type: 'uuid' })
  authorityId: string;

  @Index('idx_auth_users_authority_permission_users_id')
  @Column({ name: 'users_id', type: 'uuid' })
  usersId: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => AuthUsersAuthority, (authority) => authority.permissions)
  @JoinColumn({ name: 'authority_id' })
  authority: AuthUsersAuthority;

  @ManyToOne(() => AuthUser, (user) => user.authorityPermissions)
  @JoinColumn({ name: 'users_id' })
  user: AuthUser;
}
