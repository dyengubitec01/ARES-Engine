import { ApiProperty } from '@nestjs/swagger';

export class ApiResponseDto<T> {
  @ApiProperty()
  data: T;

  @ApiProperty({ required: false })
  message?: string;
}

export class ApiErrorDto {
  @ApiProperty()
  statusCode: number;

  @ApiProperty()
  message: string;

  @ApiProperty({ required: false })
  error?: string;

  @ApiProperty()
  timestamp: string;

  @ApiProperty()
  path: string;
}
