import { ApiProperty } from '@nestjs/swagger';
import { IsInt, Max, Min } from 'class-validator';
import { Type } from 'class-transformer';

export class AdoptPostDto {
  @ApiProperty({
    description: '채택 등급 (50~200)',
    example: 150,
    minimum: 50,
    maximum: 200,
  })
  @Type(() => Number)
  @IsInt()
  @Min(50)
  @Max(200)
  grade: number;
}
