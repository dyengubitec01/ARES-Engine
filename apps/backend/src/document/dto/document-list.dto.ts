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
  IsString,
  Length,
} from 'class-validator';
import { Transform, Type } from 'class-transformer';
import { DocStatus } from '../../common/enums';

/**
 * Query parameters for document list endpoint
 */
export class DocumentListQueryDto {
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
    description: 'Filter by favorite status',
    type: Boolean,
  })
  @IsOptional()
  @Transform(({ value }) => {
    if (value === 'true') return true;
    if (value === 'false') return false;
    return value;
  })
  @IsBoolean()
  favorite?: boolean;

  @ApiPropertyOptional({
    description:
      '조회할 부서 ID 목록 (접근 가능한 부서 내에서 선택). 미입력 시 본인이 올린 문서만 조회',
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

  @ApiPropertyOptional({
    description: '정렬 순서 (latest: 최신순, oldest: 오래된순)',
    enum: ['latest', 'oldest'],
    default: 'latest',
  })
  @IsOptional()
  @IsIn(['latest', 'oldest'])
  sort?: 'latest' | 'oldest' = 'latest';

  @ApiPropertyOptional({
    description:
      '내 태그 ID로 필터링 (콤마구분 또는 배열). 입력된 태그 중 하나라도 매칭되는 문서 반환 (OR)',
    type: [String],
    example: ['tag-uuid-1', 'tag-uuid-2'],
  })
  @IsOptional()
  @Transform(({ value }) => {
    if (typeof value === 'string') return value.split(',').filter(Boolean);
    return value;
  })
  @IsArray()
  @IsUUID('all', { each: true })
  tagIds?: string[];

  @ApiPropertyOptional({
    description: '파일명 검색 키워드 (ILIKE %keyword%)',
    example: '계약',
  })
  @IsOptional()
  @Transform(({ value }) =>
    typeof value === 'string' ? value.trim() : value,
  )
  @IsString()
  @Length(1, 100)
  keyword?: string;

  @ApiPropertyOptional({
    description:
      '조회 모드. mine: 본인 업로드만 | all: 본인 부서+권한 부서+공개 부서 (기본) | public: 공개 부서만 | dept: deptIds 지정 부서만',
    enum: ['mine', 'all', 'public', 'dept'],
    default: 'all',
  })
  @IsOptional()
  @IsIn(['mine', 'all', 'public', 'dept'])
  view?: 'mine' | 'all' | 'public' | 'dept';
}

/**
 * Latest version info in document list response
 */
export class LatestContentDto {
  @ApiProperty({ description: 'Document content (version) ID', format: 'uuid' })
  id: string;

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

  @ApiProperty({ description: 'RAG 참조 활성화 여부 (true=ON, false=OFF)' })
  isEnabled: boolean;

  @ApiProperty({ description: 'Version creation date' })
  createdAt: Date;
}

/**
 * Single document item in list response
 */
export class DocumentListItemDto {
  @ApiProperty({ description: 'Document ID', format: 'uuid' })
  id: string;

  @ApiProperty({ description: 'Document title' })
  title: string;

  @ApiProperty({ description: 'Latest version information', nullable: true })
  latestContent: LatestContentDto | null;

  @ApiProperty({ description: 'Whether document is favorited by user' })
  isFavorite: boolean;

  @ApiProperty({ description: '업로더 소속 부서명', nullable: true })
  uploaderDepartment: string | null;

  @ApiProperty({
    description: '임베딩 실패 횟수 (rag_status_events 기반)',
    default: 0,
  })
  failedCount: number;

  @ApiProperty({
    description: '본인이 이 문서에 부여한 태그 목록',
    type: 'array',
    items: {
      type: 'object',
      properties: {
        id: { type: 'string', format: 'uuid' },
        name: { type: 'string' },
        color: { type: 'string' },
      },
    },
    default: [],
  })
  myTags: Array<{ id: string; name: string; color: string }>;

  @ApiProperty({ description: 'Document creation date' })
  createdAt: Date;
}

/**
 * Pagination metadata
 */
export class PaginationMetaDto {
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
 * Document list response with pagination
 */
export class DocumentListResponseDto {
  @ApiProperty({ type: [DocumentListItemDto] })
  items: DocumentListItemDto[];

  @ApiProperty({ type: PaginationMetaDto })
  meta: PaginationMetaDto;
}
