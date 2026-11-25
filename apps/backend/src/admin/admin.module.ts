import { Module, forwardRef } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AdminController } from './admin.controller';
import { AdminService } from './admin.service';
import { ActivityService } from './activity.service';
import { AdoptionService } from './adoption.service';
import { AuthUser } from '../auth/entities/auth-user.entity';
import { AuthUsersAuthority } from '../auth/entities/auth-users-authority.entity';
import { AuthUsersAuthorityPermission } from '../auth/entities/auth-users-authority-permission.entity';
import { AuthUsersDept } from '../auth/entities/auth-users-dept.entity';
import { AuthUsersDeptAuthorityPermission } from '../auth/entities/auth-users-dept-authority-permission.entity';
import { BoardPost } from '../board/entities/board-post.entity';
import { BoardPostAdoption } from '../board/entities/board-post-adoption.entity';
import { DocumentModule } from '../document/document.module';
import { RedisModule } from '../external/redis/redis.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      AuthUser,
      AuthUsersAuthority,
      AuthUsersAuthorityPermission,
      AuthUsersDept,
      AuthUsersDeptAuthorityPermission,
      BoardPost,
      BoardPostAdoption,
    ]),
    forwardRef(() => DocumentModule),
    RedisModule,
  ],
  controllers: [AdminController],
  providers: [AdminService, ActivityService, AdoptionService],
  exports: [AdminService, ActivityService, AdoptionService],
})
export class AdminModule {}
