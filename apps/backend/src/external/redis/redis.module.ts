import { Module, Global } from '@nestjs/common';
import { RedisService } from './redis.service';
import { RedisController } from './redis.controller';

@Global()
@Module({
  controllers: [RedisController], // ⚠️ DEV ONLY - 프로덕션 배포 시 제거 고려
  providers: [RedisService],
  exports: [RedisService],
})
export class RedisModule {}
