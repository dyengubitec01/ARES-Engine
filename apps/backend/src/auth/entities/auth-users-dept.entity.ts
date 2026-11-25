import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  OneToMany,
} from 'typeorm';
import { AuthUser } from './auth-user.entity';
import { AuthUsersDeptAuthorityPermission } from './auth-users-dept-authority-permission.entity';

/**
 * 유저의 조직 관리 테이블
 */
@Entity('auth_users_dept')
export class AuthUsersDept {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({
    name: 'dept_name',
    type: 'varchar',
    length: 100,
    default: '기술연구소',
  })
  deptName: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @OneToMany(() => AuthUser, (user) => user.authDept)
  users: AuthUser[];

  @OneToMany(
    () => AuthUsersDeptAuthorityPermission,
    (permission) => permission.dept,
  )
  deptAuthorityPermissions: AuthUsersDeptAuthorityPermission[];
}
