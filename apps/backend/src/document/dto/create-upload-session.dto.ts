import {
  IsArray,
  IsNotEmpty,
  IsString,
  IsNumber,
  IsDateString,
  ValidateNested,
  ArrayMinSize,
  Min,
  Matches,
} from 'class-validator';
import { Type } from 'class-transformer';
import { ApiProperty } from '@nestjs/swagger';

// Maximum file size: 100MB in bytes
const MAX_FILE_SIZE = 100 * 1024 * 1024;

export class FileMetadataDto {
  @ApiProperty({
    description: 'Original filename with extension',
    example: 'document.pdf',
  })
  @IsString()
  @IsNotEmpty()
  filename: string;

  @ApiProperty({
    description: 'MIME type of the file',
    example: 'application/pdf',
  })
  @IsString()
  @IsNotEmpty()
  mimeType: string;

  @ApiProperty({
    description: 'File size in bytes (max 100MB)',
    example: 1024000,
    minimum: 1,
    maximum: MAX_FILE_SIZE,
  })
  @IsNumber()
  @Min(1)
  size: number;

  @ApiProperty({
    description: 'File last modified date (ISO 8601 format)',
    example: '2026-01-14T09:30:00.000Z',
  })
  @IsDateString()
  @IsNotEmpty()
  fileModifiedAt: string;

  @ApiProperty({
    description: 'SHA256 hash of the file (64 hex characters)',
    example: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
  })
  @IsString()
  @IsNotEmpty()
  @Matches(/^[a-fA-F0-9]{64}$/, {
    message: 'sha256 must be a valid 64-character hex string',
  })
  sha256: string;
}

export class CreateUploadSessionDto {
  @ApiProperty({
    description: 'Array of file metadata for upload',
    type: [FileMetadataDto],
    example: [
      {
        filename: 'document.pdf',
        mimeType: 'application/pdf',
        size: 1024000,
        fileModifiedAt: '2026-03-20T09:00:00.000Z',
        sha256:
          'a3f1c2e4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2',
      },
    ],
  })
  @IsArray()
  @ArrayMinSize(1)
  @ValidateNested({ each: true })
  @Type(() => FileMetadataDto)
  files: FileMetadataDto[];
}

export { MAX_FILE_SIZE };
