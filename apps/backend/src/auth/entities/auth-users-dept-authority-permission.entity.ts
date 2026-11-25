import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
  Unique,
} from 'typeorm';
import { AuthUser } from './auth-user.entity';
import { AuthUsersDept } from './auth-users-dept.entity';

/**
 * 사용자별 부서 권한 매핑 테이블 (사용자-부서 다대다)
 */
@Entity('auth_users_dept_authority_permission')
@Unique(['usersId', 'deptId'])
export class AuthUsersDeptAuthorityPermission {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_auth_users_dept_authority_permission_users_id')
  @Column({ name: 'users_id', type: 'uuid' })
  usersId: string;

  @Index('idx_auth_users_dept_authority_permission_dept_id')
  @Column({ name: 'dept_id', type: 'uuid' })
  deptId: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => AuthUser, (user) => user.deptPermissions)
  @JoinColumn({ name: 'users_id' })
  user: AuthUser;

  @ManyToOne(() => AuthUsersDept, (dept) => dept.deptAuthorityPermissions)
  @JoinColumn({ name: 'dept_id' })
  dept: AuthUsersDept;
}
