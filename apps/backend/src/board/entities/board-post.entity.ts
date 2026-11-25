import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  Index,
  ManyToOne,
  OneToMany,
  JoinColumn,
} from 'typeorm';
import { BoardType } from './board-type.entity';
import { BoardPostImage } from './board-post-image.entity';
import { BoardComment } from './board-comment.entity';

@Entity('board_posts')
export class BoardPost {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_board_posts_board_type_id')
  @Column({ name: 'board_type_id', type: 'uuid' })
  boardTypeId: string;

  @Index('idx_board_posts_user_id')
  @Column({ name: 'user_id', type: 'uuid' })
  userId: string;

  @Column({ type: 'varchar', length: 200 })
  title: string;

  @Column({ type: 'text' })
  content: string;

  @Column({ name: 'has_image', type: 'boolean', default: false })
  hasImage: boolean;

  @Index('idx_board_posts_created_at')
  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations (boardType만 FK)
  @ManyToOne(() => BoardType, (type) => type.posts)
  @JoinColumn({ name: 'board_type_id' })
  boardType: BoardType;

  @OneToMany(() => BoardPostImage, (image) => image.post)
  images: BoardPostImage[];

  @OneToMany(() => BoardComment, (comment) => comment.post)
  comments: BoardComment[];
}
