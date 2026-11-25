import {
  Controller,
  Get,
  Patch,
  Delete,
  Param,
  Query,
  ParseUUIDPipe,
} from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
} from '@nestjs/swagger';
import { AlarmService } from './alarm.service';
import { AlarmListQueryDto } from './dto/alarm.dto';
import { ResponseCode as RC } from '../common/constants/response-codes';
import { ResponseCode } from '../common/decorators/response-code.decorator';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import type { AuthenticatedUser } from '../auth/types/authenticated-user';
import * as Examples from './swagger-examples/alarm.examples';

@ApiTags('alarms')
@ApiBearerAuth()
@Controller('alarms')
export class AlarmController {
  constructor(private readonly alarmService: AlarmService) {}

  @Get()
  @ResponseCode(RC.ALARM_LIST_SUCCESS)
  @ApiOperation({ summary: '내 알림 목록 조회' })
  @ApiResponse({
    status: 200,
    description: '알림 목록 반환',
    schema: { example: Examples.GetAlarmsSuccessExample },
  })
  async getAlarms(
    @CurrentUser() user: AuthenticatedUser,
    @Query() query: AlarmListQueryDto,
  ) {
    const { data, total, page, limit, totalPages } =
      await this.alarmService.getAlarms(user.userId, query);
    return {
      items: data,
      meta: { total, page, limit, totalPages },
    };
  }

  @Get('unread-count')
  @ResponseCode(RC.ALARM_LIST_SUCCESS)
  @ApiOperation({ summary: '읽지 않은 알림 수 조회' })
  @ApiResponse({
    status: 200,
    description: '읽지 않은 알림 수 반환',
    schema: { example: Examples.GetUnreadCountSuccessExample },
  })
  async getUnreadCount(@CurrentUser() user: AuthenticatedUser) {
    const count = await this.alarmService.getUnreadCount(user.userId);
    return { data: { count } };
  }

  @Patch(':alarmId/read')
  @ResponseCode(RC.ALARM_READ_SUCCESS)
  @ApiOperation({ summary: '알림 읽음 처리' })
  @ApiResponse({
    status: 200,
    description: '알림 읽음 처리 완료',
    schema: { example: Examples.MarkAsReadSuccessExample },
  })
  @ApiResponse({ status: 404, description: '알림을 찾을 수 없습니다' })
  async markAsRead(
    @CurrentUser() user: AuthenticatedUser,
    @Param('alarmId', ParseUUIDPipe) alarmId: string,
  ) {
    return {
      data: await this.alarmService.markAsRead(user.userId, alarmId),
    };
  }

  @Patch('read-all')
  @ResponseCode(RC.ALARM_READ_SUCCESS)
  @ApiOperation({ summary: '모든 알림 읽음 처리' })
  @ApiResponse({
    status: 200,
    description: '전체 읽음 처리 완료',
    schema: { example: Examples.MarkAllAsReadSuccessExample },
  })
  async markAllAsRead(@CurrentUser() user: AuthenticatedUser) {
    const affected = await this.alarmService.markAllAsRead(user.userId);
    return {
      data: { affected },
      message: `${affected}건의 알림을 읽음 처리했습니다`,
    };
  }

  @Delete(':alarmId')
  @ResponseCode(RC.ALARM_DELETE_SUCCESS)
  @ApiOperation({ summary: '알림 삭제' })
  @ApiResponse({
    status: 200,
    description: '알림 삭제 완료',
    schema: { example: Examples.DeleteAlarmSuccessExample },
  })
  @ApiResponse({ status: 404, description: '알림을 찾을 수 없습니다' })
  async deleteAlarm(
    @CurrentUser() user: AuthenticatedUser,
    @Param('alarmId', ParseUUIDPipe) alarmId: string,
  ) {
    await this.alarmService.deleteAlarm(user.userId, alarmId);
    return { message: '알림이 삭제되었습니다' };
  }
}
