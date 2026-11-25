import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsInt, IsOptional, Max, Min } from 'class-validator';
import { Type } from 'class-transformer';

export class ActivityListQueryDto {
  @ApiPropertyOptional({ description: '페이지 번호 (1부터 시작)', default: 1 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  page?: number = 1;

  @ApiPropertyOptional({ description: '페이지 크기', default: 20, maximum: 100 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number = 20;
}

export class ActivityListItemDto {
  @ApiProperty() rank: number;
  @ApiProperty() userId: string;
  @ApiProperty() name: string;
  @ApiProperty({ nullable: true }) department: string | null;
  @ApiProperty({ nullable: true }) jobTitle: string | null;
  @ApiProperty({ description: '종합 점수 (0~5000, P+H+EX 합)' })
  totalScore: number;
  @ApiProperty({ description: '포상 대상 여부 (1200점 이상)' })
  eligible: boolean;
  @ApiProperty({ description: '질문 수 (참고)' })
  questionCount: number;
  @ApiProperty({ description: '업로드 수 (월 30 cap 합산)' })
  uploadCount: number;
  @ApiProperty({ description: '타인 문서 인용 수 (월 50 cap 합산)' })
  otherCitationCount: number;
  @ApiProperty({ nullable: true }) lastActivityAt: Date | null;
  @ApiProperty({
    nullable: true,
    enum: ['chat', 'upload', 'feedback', 'survey'],
  })
  lastActivityType: string | null;
}
