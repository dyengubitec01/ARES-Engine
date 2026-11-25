import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsString,
  IsOptional,
  Length,
  Matches,
  IsArray,
  IsUUID,
  ArrayMaxSize,
} from 'class-validator';

const COLOR_PATTERN = /^#([0-9a-fA-F]{6})$/;

export class CreateTagDto {
  @ApiProperty({ example: '재무', description: '태그 이름 (1~50자)' })
  @IsString()
  @Length(1, 50)
  name: string;

  @ApiPropertyOptional({
    example: '#4caf50',
    description: '태그 색상 (#RRGGBB)',
    default: '#9e9e9e',
  })
  @IsOptional()
  @IsString()
  @Matches(COLOR_PATTERN, { message: 'color는 #RRGGBB 형식이어야 합니다' })
  color?: string;
}

export class UpdateTagDto {
  @ApiPropertyOptional({ example: '재무/회계', description: '태그 이름' })
  @IsOptional()
  @IsString()
  @Length(1, 50)
  name?: string;

  @ApiPropertyOptional({ example: '#ff9800', description: '태그 색상 (#RRGGBB)' })
  @IsOptional()
  @IsString()
  @Matches(COLOR_PATTERN, { message: 'color는 #RRGGBB 형식이어야 합니다' })
  color?: string;
}

export class SetDocumentTagsDto {
  @ApiProperty({
    description: '문서에 부여할 태그 ID 배열 (기존 매핑은 모두 대체됨)',
    type: [String],
    example: ['tag-uuid-1', 'tag-uuid-2'],
  })
  @IsArray()
  @ArrayMaxSize(20)
  @IsUUID('all', { each: true })
  tagIds: string[];
}
