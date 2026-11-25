import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  OneToMany,
  JoinColumn,
  Index,
} from 'typeorm';
import { AuthUsersDept } from './auth-users-dept.entity';
import { AuthUsersAuthorityPermission } from './auth-users-authority-permission.entity';
import { AuthUsersDeptAuthorityPermission } from './auth-users-dept-authority-permission.entity';
import { AuthUsersAlarm } from './auth-users-alarm.entity';
import { DocDocument } from '../../document/entities/doc-document.entity';
import { DocDocumentFavorite } from '../../document/entities/doc-document-favorite.entity';
import { StorageObjectFile } from '../../storage/entities/storage-object-file.entity';
import { ChatSession } from '../../chat/entities/chat-session.entity';

/**
 * LLM 시스템을 사용하는 사용자 계정을 관리
 * 권한은 auth_users_authority_permission 테이블로 관리
 */
@Entity('auth_users')
export class AuthUser {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_auth_users_email')
  @Column({ type: 'varchar', length: 320, unique: true })
  email: string;

  @Column({ type: 'varchar', length: 100, nullable: true })
  name: string;

  @Index('idx_auth_users_dept_id')
  @Column({
    name: 'auth_dept_id',
    type: 'uuid',
    nullable: true,
  })
  authDeptId: string | null;

  @Column({ name: 'job_title', type: 'varchar', length: 100, nullable: true })
  jobTitle: string | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(() => AuthUsersDept, (dept) => dept.users)
  @JoinColumn({ name: 'auth_dept_id' })
  authDept: AuthUsersDept;

  @OneToMany(
    () => AuthUsersAuthorityPermission,
    (permission) => permission.user,
  )
  authorityPermissions: AuthUsersAuthorityPermission[];

  @OneToMany(
    () => AuthUsersDeptAuthorityPermission,
    (permission) => permission.user,
  )
  deptPermissions: AuthUsersDeptAuthorityPermission[];

  @OneToMany(() => AuthUsersAlarm, (alarm) => alarm.user)
  alarms: AuthUsersAlarm[];

  @OneToMany(() => DocDocument, (doc) => doc.createdByUser)
  createdDocuments: DocDocument[];

  @OneToMany(() => DocDocumentFavorite, (fav) => fav.user)
  favorites: DocDocumentFavorite[];

  @OneToMany(() => StorageObjectFile, (file) => file.createdByUser)
  storageFiles: StorageObjectFile[];

  @OneToMany(() => ChatSession, (session) => session.user)
  chatSessions: ChatSession[];
}
