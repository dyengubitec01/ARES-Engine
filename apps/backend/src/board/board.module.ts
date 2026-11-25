import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { BoardController } from './board.controller';
import { BoardService } from './board.service';
import { BoardType } from './entities/board-type.entity';
import { BoardPost } from './entities/board-post.entity';
import { BoardPostImage } from './entities/board-post-image.entity';
import { BoardComment } from './entities/board-comment.entity';
import { BoardSurvey } from './entities/board-survey.entity';
import { AuthUser } from '../auth/entities/auth-user.entity';
import { BoardPostAdoption } from './entities/board-post-adoption.entity';
import { AuthUsersAlarm } from '../auth/entities/auth-users-alarm.entity';
import { MinioModule } from '../external/minio/minio.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      BoardType,
      BoardPost,
      BoardPostImage,
      BoardComment,
      BoardSurvey,
      BoardPostAdoption,
      AuthUser,
      AuthUsersAlarm,
    ]),
    MinioModule,
  ],
  controllers: [BoardController],
  providers: [BoardService],
  exports: [BoardService],
})
export class BoardModule {}
