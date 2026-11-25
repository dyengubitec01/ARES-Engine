import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { DocStatus } from '../../common/enums';

/**
 * Version detail in document detail response
 */
export class VersionDetailDto {
  @ApiProperty({ description: 'Version ID', format: 'uuid' })
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

  @ApiPropertyOptional({ description: 'Status reason (for failed status)' })
  statusReason: string | null;

  @ApiPropertyOptional({ description: 'When queued for embedding' })
  queuedAt: Date | null;

  @ApiPropertyOptional({ description: 'When processing started' })
  startedAt: Date | null;

  @ApiPropertyOptional({ description: 'When processing finished' })
  finishedAt: Date | null;

  @ApiProperty({ description: 'Version creation date' })
  createdAt: Date;
}

/**
 * Document detail response
 */
export class DocumentDetailDto {
  @ApiProperty({ description: 'Document ID', format: 'uuid' })
  id: string;

  @ApiProperty({ description: 'Document title' })
  title: string;

  @ApiProperty({ description: 'MinIO URL path' })
  minioUrl: string;

  @ApiProperty({ description: 'Creator user ID', format: 'uuid' })
  createdBy: string;

  @ApiProperty({ description: 'Document creation date' })
  createdAt: Date;

  @ApiProperty({ description: 'Version history', type: [VersionDetailDto] })
  versions: VersionDetailDto[];

  @ApiProperty({ description: 'Whether document is favorited by user' })
  isFavorite: boolean;
}
