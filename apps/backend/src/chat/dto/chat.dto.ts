import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsString,
  IsNotEmpty,
  IsUUID,
  IsOptional,
  IsIn,
  IsNumber,
  Min,
  Max,
  MaxLength,
} from 'class-validator';
import { Type } from 'class-transformer';

// ============================================================
// Session DTOs
// ============================================================

export class CreateChatSessionDto {
  @ApiPropertyOptional({
    description: '즐겨찾기 여부',
    default: 'N',
    enum: ['Y', 'N'],
  })
  @IsIn(['Y', 'N'])
  @IsOptional()
  favorites?: string;
}

export class SessionListQueryDto {
  @ApiPropertyOptional({
    description: '마지막 조회 항목의 ID (커서)',
  })
  @IsUUID()
  @IsOptional()
  cursor?: string;

  @ApiPropertyOptional({
    description: '조회 개수 (기본: 20, 최대: 50)',
    default: 20,
    minimum: 1,
    maximum: 50,
  })
  @Type(() => Number)
  @IsNumber()
  @Min(1)
  @Max(50)
  @IsOptional()
  limit?: number;
}

export class SessionListItemDto {
  @ApiProperty()
  id: string;

  @ApiPropertyOptional()
  title: string | null;

  @ApiProperty()
  favorites: string;

  @ApiProperty()
  createdAt: Date;

  @ApiProperty({ description: '메시지 개수' })
  messageCount: number;
}

export class SessionListResponseDto {
  @ApiProperty({ type: [SessionListItemDto] })
  data: SessionListItemDto[];

  @ApiPropertyOptional({ description: '다음 페이지 커서' })
  nextCursor: string | null;

  @ApiProperty({ description: '다음 페이지 존재 여부' })
  hasMore: boolean;
}

export class ChatSessionResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  favorites: string;

  @ApiProperty()
  usersId: string;

  @ApiProperty()
  createdAt: Date;
}

export class UpdateSessionDto {
  @ApiProperty({
    description: '채팅방 제목',
    example: '새로운 제목',
    maxLength: 20,
  })
  @IsString()
  @IsNotEmpty({ message: '제목을 입력해주세요' })
  @MaxLength(20, { message: '제목은 최대 20자까지 가능합니다' })
  title: string;
}

// ============================================================
// Interaction DTOs
// ============================================================

export class CreateInteractionDto {
  @ApiProperty({ description: '메시지 타입', enum: ['Q', 'A'], default: 'Q' })
  @IsIn(['Q', 'A'])
  @IsOptional()
  type?: string;

  @ApiProperty({ description: '메시지 내용 (최대 10000자)' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(10000)
  content: string;

  @ApiPropertyOptional({ description: '채팅 턴 번호' })
  @IsOptional()
  chatTurn?: number;
}

export class ChatInteractionResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty({ enum: ['Q', 'A'] })
  type: string;

  @ApiProperty()
  content: string;

  @ApiProperty()
  chatTurn: number;

  @ApiPropertyOptional()
  feedback?: string | null;

  @ApiProperty()
  sessionId: string;

  @ApiProperty()
  createdAt: Date;
}

// ============================================================
// Feedback DTOs
// ============================================================

export class SubmitFeedbackDto {
  @ApiProperty({
    description:
      '피드백 값: Y (좋아요), N (싫어요) — 같은 값 재전송 시 null(취소)로 처리',
    enum: ['Y', 'N'],
    example: 'Y',
  })
  @IsIn(['Y', 'N'])
  feedback: string;
}

export class FeedbackResponseDto {
  @ApiProperty({ description: 'Interaction ID' })
  interactionId: string;

  @ApiPropertyOptional({ description: '피드백 값' })
  feedback: string | null;
}

// ============================================================
// Document Reference DTOs
// ============================================================

export class AddDocumentReferenceDto {
  @ApiProperty({ description: '문서 버전 ID (doc_document_content.id)' })
  @IsUUID()
  @IsNotEmpty()
  documentContentId: string;
}

export class DocumentReferenceResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  documentContentId: string;

  @ApiProperty()
  chatInteractionId: string;

  @ApiProperty()
  createdAt: Date;
}

// ============================================================
// Send Prompt DTO (for AI interaction)
// ============================================================

export class SendPromptDto {
  @ApiProperty({ description: '질문 내용 (최대 5000자)' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(5000)
  prompt: string;

  @ApiPropertyOptional({ description: '기존 세션 ID (없으면 자동 생성)' })
  @IsUUID()
  @IsOptional()
  sessionId?: string;
}

// ============================================================
// RAG Reference DTOs
// ============================================================

export class RagReferenceDto {
  @ApiProperty({ description: '문서 ID' })
  documentId: string;

  @ApiProperty({ description: '문서 제목' })
  title: string;

  @ApiProperty({ description: '관련도 점수 (0.0 ~ 1.0)' })
  relevance: number;
}

export class SseChunkDto {
  @ApiPropertyOptional({ description: 'AI 응답 청크' })
  content?: string;

  @ApiPropertyOptional({ description: '참조 문서 목록 (done 이벤트에서만)' })
  references?: RagReferenceDto[] | null;

  @ApiPropertyOptional({ description: '완료 여부' })
  done?: boolean;
}

// ============================================================
// Message History DTOs
// ============================================================

export class MessageListQueryDto {
  @ApiPropertyOptional({
    description: '마지막 조회한 chat_turn 값 (커서)',
  })
  @Type(() => Number)
  @IsNumber()
  @IsOptional()
  cursor?: number;
}

export class MessageItemDto {
  @ApiProperty()
  id: string;

  @ApiProperty({ enum: ['Q', 'A'] })
  type: string;

  @ApiProperty()
  content: string;

  @ApiProperty()
  chatTurn: number;

  @ApiProperty()
  feedback: string;

  @ApiProperty()
  createdAt: Date;
}

export class MessageListResponseDto {
  @ApiProperty({ type: [MessageItemDto] })
  data: MessageItemDto[];

  @ApiPropertyOptional({ description: '다음 페이지 커서 (chat_turn)' })
  nextCursor: number | null;

  @ApiProperty({ description: '다음 페이지 존재 여부' })
  hasMore: boolean;
}
