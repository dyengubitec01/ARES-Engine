import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  OneToMany,
} from 'typeorm';
import { AuthorityType } from '../../common/enums';
import { AuthUsersAuthorityPermission } from './auth-users-authority-permission.entity';

/**
 * 시스템 기본 권한 테이블 (uploader, admin, embedding, soft_delete, download)
 */
@Entity('auth_users_authority')
export class AuthUsersAuthority {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({
    name: 'authority_name',
    type: 'enum',
    enum: AuthorityType,
    enumName: 'authority_type',
    unique: true,
  })
  authorityName: AuthorityType;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @OneToMany(
    () => AuthUsersAuthorityPermission,
    (permission) => permission.authority,
  )
  permissions: AuthUsersAuthorityPermission[];
}
