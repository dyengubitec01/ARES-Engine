import {
  IsInt,
  IsNotEmpty,
  IsOptional,
  IsString,
  Min,
  Max,
  MaxLength,
} from 'class-validator';
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

// ============================================================
// Survey - Create
// ============================================================

export class CreateSurveyDto {
  // 로그인/회원가입 경험
  @ApiProperty({
    description: '[로그인] 로그인 과정을 이해하기 쉬웠다 (1~5)',
    example: 4,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  loginUnderstand: number;

  @ApiProperty({
    description: '[로그인] 로그인 과정이 간단했다 (1~5)',
    example: 5,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  loginSimple: number;

  // 홈 화면 경험
  @ApiProperty({ description: '[홈] 홈 화면이 직관적이었다 (1~5)', example: 4 })
  @IsInt()
  @Min(1)
  @Max(5)
  homeIntuitive: number;

  @ApiProperty({ description: '[홈] 입력창 위치가 적절했다 (1~5)', example: 3 })
  @IsInt()
  @Min(1)
  @Max(5)
  homeInputPosition: number;

  @ApiProperty({
    description: '[홈] 자연스럽게 시작할 수 있었다 (1~5)',
    example: 4,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  homeNaturalStart: number;

  // 채팅 및 AI 답변 품질
  @ApiProperty({
    description: '[채팅] AI 답변 속도가 만족스러웠다 (1~5)',
    example: 5,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  chatSpeed: number;

  @ApiProperty({
    description: '[채팅] 채팅 인터페이스가 사용하기 쉬웠다 (1~5)',
    example: 4,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  chatEasy: number;

  @ApiProperty({ description: '[채팅] 답변 길이가 적절했다 (1~5)', example: 3 })
  @IsInt()
  @Min(1)
  @Max(5)
  chatLength: number;

  @ApiProperty({
    description: '[채팅] AI 답변이 업무에 도움이 되었다 (1~5)',
    example: 5,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  chatProcessHelpful: number;

  // 출처 보기 기능
  @ApiProperty({
    description: '[출처] 출처 문서가 잘 보였다 (1~5)',
    example: 4,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  sourceVisible: number;

  @ApiProperty({
    description: '[출처] 출처 보기 UI가 사용하기 쉬웠다 (1~5)',
    example: 4,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  sourceUiEasy: number;

  @ApiProperty({
    description: '[출처] 출처 정보를 신뢰할 수 있었다 (1~5)',
    example: 3,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  sourceTrust: number;

  // 문서함 기능
  @ApiProperty({
    description: '[문서함] 문서 업로드가 쉬웠다 (1~5)',
    example: 5,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  docUploadEasy: number;

  @ApiProperty({
    description:
      '[문서함] 문서 상태(임베딩 진행 등)가 명확하게 표시되었다 (1~5)',
    example: 4,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  docStatusClear: number;

  @ApiProperty({
    description: '[문서함] AI가 문서 내용을 잘 이해하는 것 같았다 (1~5)',
    example: 4,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  docAiKnowledge: number;

  // 업무 활용도
  @ApiProperty({
    description: '[활용도] 업무에 전반적으로 도움이 되었다 (1~5)',
    example: 5,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  workHelpful: number;

  @ApiProperty({
    description: '[활용도] 일반 LLM보다 더 유용했다 (1~5)',
    example: 4,
  })
  @IsInt()
  @Min(1)
  @Max(5)
  workBetterThanLlm: number;

  // 주관식
  @ApiProperty({
    description: '[주관식] 가장 좋았던 기능',
    example: '문서 검색 기능이 가장 유용했습니다',
  })
  @IsString()
  @IsNotEmpty()
  @MaxLength(1000)
  bestFeature: string;

  @ApiProperty({
    description: '[주관식] 가장 아쉬웠던 점',
    example: '로딩 속도가 가끔 느렸습니다',
  })
  @IsString()
  @IsNotEmpty()
  @MaxLength(1000)
  worstFeature: string;

  @ApiPropertyOptional({
    description: '[주관식] 자유 의견 (선택)',
    example: '전반적으로 만족합니다',
  })
  @IsOptional()
  @IsString()
  @MaxLength(1000)
  freeComment?: string;
}

// ============================================================
// Survey - Responses
// ============================================================

export class SurveyStatusDto {
  submitted: boolean;
}
