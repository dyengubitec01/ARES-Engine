import {
  IsString,
  IsNotEmpty,
  IsOptional,
  IsUUID,
  IsInt,
  IsArray,
  Min,
  Max,
  MaxLength,
  ValidateNested,
} from 'class-validator';
import { Type } from 'class-transformer';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

// ============================================================
// Post - Create
// ============================================================

export class ImageMetadataDto {
  @ApiProperty({
    description: 'presigned-url 발급 시 반환된 objectKey',
    example: 'board/feedback/2026/03/uuid/screenshot.png',
  })
  @IsString()
  @IsNotEmpty()
  objectKey: string;

  @ApiProperty({ description: '원본 파일명', example: 'screenshot.png' })
  @IsString()
  @IsNotEmpty()
  originalFilename: string;

  @ApiPropertyOptional({ description: '파일 크기 (bytes)', example: 204800 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  fileSize?: number;

  @ApiPropertyOptional({ description: 'MIME 타입', example: 'image/png' })
  @IsOptional()
  @IsString()
  mimeType?: string;

  @ApiPropertyOptional({
    description: '이미지 정렬 순서 (0부터 시작, 기본값: 배열 인덱스)',
    example: 0,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(0)
  sortOrder?: number;
}

export class CreatePostDto {
  @ApiProperty({
    description: '게시판 타입 UUID',
    example: 'b1b2c3d4-e5f6-7890-abcd-ef1234567890',
  })
  @IsUUID('all')
  @IsNotEmpty()
  boardTypeId: string;

  @ApiProperty({
    description: '게시글 제목 (최대 200자)',
    example: '서비스 사용 후기입니다',
  })
  @IsString()
  @IsNotEmpty()
  @MaxLength(200)
  title: string;

  @ApiProperty({
    description: '게시글 본문 (최대 5000자)',
    example: '전반적으로 만족스럽습니다. 특히 문서 검색 기능이 편리했습니다.',
  })
  @IsString()
  @IsNotEmpty()
  @MaxLength(5000)
  content: string;

  @ApiPropertyOptional({
    description: '첨부 이미지 목록 (presigned-url로 업로드 후 objectKey 전달)',
    type: [ImageMetadataDto],
  })
  @IsOptional()
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => ImageMetadataDto)
  images?: ImageMetadataDto[];
}

// ============================================================
// Post - List Query
// ============================================================

export class PostListQueryDto {
  @ApiPropertyOptional({ description: '페이지 번호 (기본값: 1)', example: 1 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  page?: number = 1;

  @ApiPropertyOptional({
    description: '페이지당 항목 수 (기본값: 20, 최대: 100)',
    example: 20,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number = 20;

  @ApiPropertyOptional({
    description: '게시판 타입 UUID 필터',
    example: 'b1b2c3d4-e5f6-7890-abcd-ef1234567890',
  })
  @IsOptional()
  @IsUUID('all')
  boardTypeId?: string;

}

// ============================================================
// Post - Responses
// ============================================================

export class PostListItemDto {
  id: string;
  boardTypeId: string;
  userId: string;
  userName: string | null;
  title: string;
  hasImage: boolean;
  isReplied: boolean;
  createdAt: Date;
}

export class PaginationMetaDto {
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}

export class PostListResponseDto {
  items: PostListItemDto[];
  meta: PaginationMetaDto;
}

export class ReplyDetailDto {
  id: string;
  userId: string;
  userName: string | null;
  content: string;
  createdAt: Date;
}

export class PostDetailDto {
  id: string;
  boardTypeId: string;
  userId: string;
  userName: string | null;
  title: string;
  content: string;
  hasImage: boolean;
  isReplied: boolean;
  images: PostImageDto[];
  reply: ReplyDetailDto | null;
  createdAt: Date;
}

export class PostImageDto {
  id: string;
  objectKey: string;
  originalFilename: string;
  fileSize: number | null;
  mimeType: string | null;
  sortOrder: number;
  viewUrl: string;
}

// ============================================================
// Reply - Create
// ============================================================

export class CreateReplyDto {
  @ApiProperty({
    description: '답변 내용 (최대 5000자)',
    example: '피드백 감사합니다. 해당 이슈는 다음 업데이트에 반영하겠습니다.',
  })
  @IsString()
  @IsNotEmpty()
  @MaxLength(5000)
  content: string;
}

// ============================================================
// Presigned URL
// ============================================================

export class PresignedUrlRequestDto {
  @ApiProperty({
    description: '업로드할 원본 파일명',
    example: 'screenshot.png',
  })
  @IsString()
  @IsNotEmpty()
  filename: string;

  @ApiProperty({
    description: '게시판 타입명 (prefix 결정용)',
    example: 'feedback',
    enum: ['feedback', 'suggestion', 'answer_suggestion'],
  })
  @IsString()
  @IsNotEmpty()
  boardTypeName: string;

  @ApiPropertyOptional({ description: 'MIME 타입', example: 'image/png' })
  @IsOptional()
  @IsString()
  mimeType?: string;
}

export class PresignedUrlResponseDto {
  uploadUrl: string;
  objectKey: string;
  expiresIn: number;
}
