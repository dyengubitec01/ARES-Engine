import { ApiProperty } from '@nestjs/swagger';
import { IsString, IsNotEmpty } from 'class-validator';

export class AzureLoginDto {
  @ApiProperty({ description: 'Azure AD authorization code' })
  @IsString()
  @IsNotEmpty()
  code: string;
}

export class TokenDataDto {
  @ApiProperty({ description: 'JWT access token' })
  accessToken: string;

  @ApiProperty({ description: 'JWT refresh token' })
  refreshToken: string;

  @ApiProperty({ description: 'Access token expiration in seconds' })
  expiresIn: number;
}

export class TokenResponseDto {
  @ApiProperty({ type: TokenDataDto })
  data: TokenDataDto;

  @ApiProperty({ description: 'Response message', required: false })
  message?: string;
}

export class RefreshTokenDto {
  @ApiProperty({ description: 'Refresh token' })
  @IsString()
  @IsNotEmpty()
  refreshToken: string;
}
