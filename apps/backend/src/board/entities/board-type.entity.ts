import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  OneToMany,
} from 'typeorm';
import { BoardTypeName } from '../../common/enums';
import { BoardPost } from './board-post.entity';

@Entity('board_types')
export class BoardType {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column({
    type: 'enum',
    enum: BoardTypeName,
    enumName: 'board_type_name',
    unique: true,
  })
  name: BoardTypeName;

  @Column({ type: 'varchar', length: 200, nullable: true })
  description: string | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  @OneToMany(() => BoardPost, (post) => post.boardType)
  posts: BoardPost[];
}
