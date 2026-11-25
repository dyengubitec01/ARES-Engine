import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { AuthUsersAlarm } from '../auth/entities/auth-users-alarm.entity';
import { AlarmListQueryDto, AlarmResponseDto } from './dto/alarm.dto';
import { BusinessException } from '../common/exceptions/business.exception';
import {
  ResponseCode,
  getHttpStatus,
} from '../common/constants/response-codes';

@Injectable()
export class AlarmService {
  private readonly logger = new Logger(AlarmService.name);

  constructor(
    @InjectRepository(AuthUsersAlarm)
    private readonly alarmRepository: Repository<AuthUsersAlarm>,
  ) {}

  async getAlarms(
    userId: string,
    query: AlarmListQueryDto,
  ): Promise<{
    data: AlarmResponseDto[];
    total: number;
    page: number;
    limit: number;
    totalPages: number;
  }> {
    const { page = 1, limit = 20, isRead } = query;
    const skip = (page - 1) * limit;

    const qb = this.alarmRepository
      .createQueryBuilder('alarm')
      .where('alarm.users_id = :userId', { userId });

    if (isRead) {
      qb.andWhere('alarm.is_read = :isRead', { isRead });
    }

    const total = await qb.getCount();
    const alarms = await qb
      .orderBy('alarm.created_at', 'DESC')
      .skip(skip)
      .take(limit)
      .getMany();

    return {
      data: alarms.map(this.toResponseDto),
      total,
      page,
      limit,
      totalPages: Math.ceil(total / limit) || 1,
    };
  }

  async getUnreadCount(userId: string): Promise<number> {
    return this.alarmRepository.count({
      where: { usersId: userId, isRead: 'N' },
    });
  }

  async markAsRead(userId: string, alarmId: string): Promise<AlarmResponseDto> {
    const alarm = await this.alarmRepository.findOne({
      where: { id: alarmId, usersId: userId },
    });

    if (!alarm) {
      throw new BusinessException(
        ResponseCode.ALARM_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.ALARM_NOT_FOUND),
      );
    }

    alarm.isRead = 'Y';
    const updated = await this.alarmRepository.save(alarm);
    return this.toResponseDto(updated);
  }

  async markAllAsRead(userId: string): Promise<number> {
    const result = await this.alarmRepository.update(
      { usersId: userId, isRead: 'N' },
      { isRead: 'Y' },
    );
    return result.affected || 0;
  }

  async deleteAlarm(userId: string, alarmId: string): Promise<void> {
    const alarm = await this.alarmRepository.findOne({
      where: { id: alarmId, usersId: userId },
    });

    if (!alarm) {
      throw new BusinessException(
        ResponseCode.ALARM_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.ALARM_NOT_FOUND),
      );
    }

    await this.alarmRepository.remove(alarm);
  }

  private toResponseDto(alarm: AuthUsersAlarm): AlarmResponseDto {
    return {
      id: alarm.id,
      documentId: alarm.documentId,
      postId: alarm.postId,
      message: alarm.message,
      isRead: alarm.isRead,
      createdAt: alarm.createdAt,
    };
  }
}
