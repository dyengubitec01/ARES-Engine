import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AlarmController } from './alarm.controller';
import { AlarmService } from './alarm.service';
import { AuthUsersAlarm } from '../auth/entities/auth-users-alarm.entity';

@Module({
  imports: [TypeOrmModule.forFeature([AuthUsersAlarm])],
  controllers: [AlarmController],
  providers: [AlarmService],
  exports: [AlarmService],
})
export class AlarmModule {}
