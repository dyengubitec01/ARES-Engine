import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
  Unique,
  OneToMany,
} from 'typeorm';
import { AuthUser } from '../../auth/entities/auth-user.entity';
import { DocUserTagMapping } from './doc-user-tag-mapping.entity';

@Entity('doc_user_tags')
@Unique('UQ_doc_user_tags_user_name', ['userId', 'name'])
export class DocUserTag {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_doc_user_tags_user_id')
  @Column({ name: 'user_id', type: 'uuid' })
  userId: string;

  @Column({ name: 'name', type: 'varchar', length: 50 })
  name: string;

  @Column({ name: 'color', type: 'varchar', length: 20, default: '#9e9e9e' })
  color: string;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @UpdateDateColumn({ name: 'updated_at', type: 'timestamptz' })
  updatedAt: Date;

  @ManyToOne(() => AuthUser, { onDelete: 'CASCADE' })
  @JoinColumn({ name: 'user_id' })
  user: AuthUser;

  @OneToMany(() => DocUserTagMapping, (m) => m.tag)
  mappings: DocUserTagMapping[];
}
