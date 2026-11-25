import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsOptional, IsIn, IsInt, Min, Max } from 'class-validator';
import { Type } from 'class-transformer';

export class AlarmListQueryDto {
  @ApiPropertyOptional({ description: '페이지 번호', default: 1 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  page?: number = 1;

  @ApiPropertyOptional({ description: '페이지당 항목 수', default: 20 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number = 20;

  @ApiPropertyOptional({ description: '읽음 여부 필터', enum: ['Y', 'N'] })
  @IsOptional()
  @IsIn(['Y', 'N'])
  isRead?: string;
}

export class AlarmResponseDto {
  @ApiProperty({ description: '알림 ID' })
  id: string;

  @ApiProperty({ description: '문서 ID', nullable: true })
  documentId: string | null;

  @ApiProperty({ description: '게시글 ID', nullable: true })
  postId: string | null;

  @ApiProperty({ description: '메시지' })
  message: string;

  @ApiProperty({ description: '읽음 여부', enum: ['Y', 'N'] })
  isRead: string;

  @ApiProperty({ description: '생성일' })
  createdAt: Date;
}
