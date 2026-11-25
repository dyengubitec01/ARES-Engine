import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsOptional,
  IsInt,
  Min,
  Max,
  IsEnum,
  IsBoolean,
  IsIn,
  IsArray,
  IsUUID,
} from 'class-validator';
import { Transform, Type } from 'class-transformer';
import { DocStatus } from '../../common/enums';

/**
 * Query parameters for admin document list endpoint
 */
export class AdminDocumentListQueryDto {
  @ApiPropertyOptional({
    description: 'Page number (1-based)',
    minimum: 1,
    default: 1,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  page?: number = 1;

  @ApiPropertyOptional({
    description: 'Number of items per page',
    minimum: 1,
    maximum: 100,
    default: 20,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number = 20;

  @ApiPropertyOptional({
    description: 'Filter by document status',
    enum: DocStatus,
  })
  @IsOptional()
  @IsEnum(DocStatus)
  status?: DocStatus;

  @ApiPropertyOptional({
    description: 'Show only deleted documents',
    type: Boolean,
    default: false,
  })
  @IsOptional()
  @Transform(({ value }) => {
    if (value === 'true') return true;
    if (value === 'false') return false;
    return value;
  })
  @IsBoolean()
  deletedOnly?: boolean;

  @ApiPropertyOptional({
    description: '정렬 순서 (latest: 최신순, oldest: 오래된순)',
    enum: ['latest', 'oldest'],
    default: 'latest',
  })
  @IsOptional()
  @IsIn(['latest', 'oldest'])
  sort?: 'latest' | 'oldest' = 'latest';

  @ApiPropertyOptional({
    description: '조회할 부서 ID 목록. 미입력 시 전체 조회',
    type: [String],
    example: ['dept-uuid-1', 'dept-uuid-2'],
  })
  @IsOptional()
  @Transform(({ value }) => {
    if (typeof value === 'string') return [value];
    return value;
  })
  @IsArray()
  @IsUUID('4', { each: true })
  deptIds?: string[];
}

/**
 * Document owner info in admin list response
 */
export class AdminDocumentOwnerDto {
  @ApiProperty({ description: 'User ID', format: 'uuid' })
  id: string;

  @ApiProperty({ description: 'User name', nullable: true })
  name: string | null;

  @ApiProperty({ description: 'User email' })
  email: string;

  @ApiProperty({ description: '소속 부서명', nullable: true })
  department: string | null;
}

/**
 * Latest version info in admin document list response
 */
export class AdminLatestContentDto {
  @ApiProperty({ description: 'Version number' })
  versionNo: number;

  @ApiProperty({ description: 'Original filename' })
  originalFilename: string;

  @ApiProperty({ description: 'File size in bytes' })
  fileSize: number;

  @ApiProperty({ description: 'MIME type' })
  mimeType: string;

  @ApiProperty({ description: 'Processing status', enum: DocStatus })
  status: DocStatus;

  @ApiProperty({ description: '거절/오류 사유', nullable: true })
  statusReason: string | null;

  @ApiProperty({ description: 'Version creation date' })
  createdAt: Date;

  @ApiProperty({ description: 'Content deletion date', nullable: true })
  deletedAt: Date | null;
}

/**
 * Single document item in admin list response
 */
export class AdminDocumentListItemDto {
  @ApiProperty({ description: 'Document ID', format: 'uuid' })
  id: string;

  @ApiProperty({ description: 'Document title' })
  title: string;

  @ApiProperty({ description: 'Latest version information', nullable: true })
  latestContent: AdminLatestContentDto | null;

  @ApiProperty({ description: 'Document owner information' })
  createdBy: AdminDocumentOwnerDto;

  @ApiProperty({ description: 'Document creation date' })
  createdAt: Date;
}

/**
 * Pagination metadata
 */
export class AdminPaginationMetaDto {
  @ApiProperty({ description: 'Total number of items' })
  total: number;

  @ApiProperty({ description: 'Current page number' })
  page: number;

  @ApiProperty({ description: 'Items per page' })
  limit: number;

  @ApiProperty({ description: 'Total number of pages' })
  totalPages: number;
}

/**
 * Admin document list response with pagination
 */
export class AdminDocumentListResponseDto {
  @ApiProperty({ type: [AdminDocumentListItemDto] })
  data: AdminDocumentListItemDto[];

  @ApiProperty({ type: AdminPaginationMetaDto })
  meta: AdminPaginationMetaDto;
}
