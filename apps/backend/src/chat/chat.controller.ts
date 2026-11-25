import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Body,
  Param,
  Query,
  ParseUUIDPipe,
  Logger,
  Req,
} from '@nestjs/common';
import type { Request as ExpressRequest } from 'express';
import { Sse } from '../common/decorators';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiParam,
  ApiBearerAuth,
  ApiBody,
} from '@nestjs/swagger';
import { Observable } from 'rxjs';
import { ChatService } from './chat.service';
import {
  UpdateSessionDto,
  SessionListQueryDto,
  SendPromptDto,
  AddDocumentReferenceDto,
  MessageListQueryDto,
  SubmitFeedbackDto,
} from './dto/chat.dto';
import { Public } from '../auth/decorators/public.decorator';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import type { AuthenticatedUser } from '../auth/types/authenticated-user';
import { ChatbotService } from '../external/chatbot/chatbot.service';
import { ResponseCode } from '../common/decorators/response-code.decorator';
import {
  ResponseCode as RC,
  ResponseMessage,
} from '../common/constants/response-codes';
import * as Examples from './swagger-examples/chat.examples';

interface MessageEvent {
  data: string;
  type?: string;
}

@ApiTags('chat')
@ApiBearerAuth()
@Controller('chat')
export class ChatController {
  private readonly logger = new Logger(ChatController.name);

  constructor(
    private readonly chatService: ChatService,
    private readonly chatbotService: ChatbotService,
  ) {}

  @Public()
  @Get('health')
  @ResponseCode(RC.CHAT_HEALTH_SUCCESS)
  @ApiOperation({ summary: '챗봇 서비스 상태 확인' })
  @ApiResponse({
    status: 200,
    description: 'Health check result',
    schema: { example: Examples.HealthCheckSuccessExample },
  })
  async healthCheck() {
    const chatbotHealthy = await this.chatbotService.healthCheck();
    return {
      data: { chatbot: chatbotHealthy },
      message: 'Health check completed',
    };
  }

  // ============================================================
  // Session Endpoints
  // ============================================================

  @Get('sessions')
  @ResponseCode(RC.CHAT_SESSION_LIST_SUCCESS)
  @ApiOperation({ summary: '내 채팅방 목록 조회' })
  @ApiResponse({
    status: 200,
    description: 'List of chat sessions with pagination',
    schema: { example: Examples.GetSessionsSuccessExample },
  })
  async getSessions(
    @CurrentUser() user: AuthenticatedUser,
    @Query() query: SessionListQueryDto,
  ) {
    return this.chatService.getSessions(
      user.userId,
      query.cursor,
      query.limit ?? 20,
    );
  }

  @Get('sessions/:sessionId')
  @ResponseCode(RC.CHAT_SESSION_FOUND)
  @ApiOperation({ summary: '채팅방 상세 정보 조회' })
  @ApiResponse({
    status: 200,
    description: 'Chat session details',
    schema: { example: Examples.GetSessionSuccessExample },
  })
  async getSession(
    @CurrentUser() user: AuthenticatedUser,
    @Param('sessionId', ParseUUIDPipe) sessionId: string,
  ) {
    return {
      data: await this.chatService.getSession(
        user.userId,
        sessionId,
        user.authorities,
      ),
    };
  }

  @Patch('sessions/:sessionId')
  @ResponseCode(RC.CHAT_SESSION_UPDATED)
  @ApiOperation({ summary: '채팅방 제목 변경' })
  @ApiResponse({
    status: 200,
    description: '제목이 변경되었습니다',
    schema: { example: Examples.UpdateSessionSuccessExample },
  })
  @ApiBody({ type: UpdateSessionDto })
  @ApiResponse({ status: 400, description: '제목 검증 실패' })
  @ApiResponse({ status: 403, description: '이 채팅방에 대한 권한이 없습니다' })
  @ApiResponse({ status: 404, description: '채팅방을 찾을 수 없습니다' })
  async updateSession(
    @CurrentUser() user: AuthenticatedUser,
    @Param('sessionId', ParseUUIDPipe) sessionId: string,
    @Body() dto: UpdateSessionDto,
  ) {
    const result = await this.chatService.updateSession(
      user.userId,
      sessionId,
      dto.title,
      user.authorities,
    );
    return {
      data: result,
      message: '제목이 변경되었습니다',
    };
  }

  @Patch('sessions/:sessionId/favorite')
  @ResponseCode(RC.CHAT_SESSION_FAVORITE_TOGGLED)
  @ApiOperation({ summary: '채팅방 즐겨찾기 토글' })
  @ApiResponse({
    status: 200,
    description: '즐겨찾기 상태가 변경되었습니다',
    schema: { example: Examples.ToggleFavoriteSuccessExample },
  })
  @ApiResponse({ status: 403, description: '이 채팅방에 대한 권한이 없습니다' })
  @ApiResponse({ status: 404, description: '채팅방을 찾을 수 없습니다' })
  async toggleFavorite(
    @CurrentUser() user: AuthenticatedUser,
    @Param('sessionId', ParseUUIDPipe) sessionId: string,
  ) {
    return this.chatService.toggleFavorite(
      user.userId,
      sessionId,
      user.authorities,
    );
  }

  @Delete('sessions/:sessionId')
  @ResponseCode(RC.CHAT_SESSION_DELETED)
  @ApiOperation({
    summary: '채팅방 삭제 (Soft Delete)',
    description:
      'deleted_at에 시각을 기록하며 DB 레코드는 보존됩니다. ADMIN 권한은 모든 채팅방 삭제 가능, 일반 사용자는 본인 채팅방만 삭제 가능합니다.',
  })
  @ApiParam({
    name: 'sessionId',
    description: '삭제할 채팅방 UUID',
    example: 's1b2c3d4-e5f6-7890-abcd-ef1234567890',
  })
  @ApiResponse({
    status: 200,
    description: '채팅방 소프트 삭제 성공',
    schema: { example: Examples.DeleteSessionSuccessExample },
  })
  @ApiResponse({ status: 403, description: '이 채팅방에 대한 권한이 없습니다' })
  @ApiResponse({ status: 404, description: '채팅방을 찾을 수 없습니다' })
  async deleteSession(
    @CurrentUser() user: AuthenticatedUser,
    @Param('sessionId', ParseUUIDPipe) sessionId: string,
  ) {
    return this.chatService.deleteSession(
      user.userId,
      sessionId,
      user.authorities,
    );
  }

  // ============================================================
  // Interaction Endpoints
  // ============================================================

  @Get('sessions/:sessionId/messages')
  @ResponseCode(RC.CHAT_INTERACTION_SUCCESS)
  @ApiOperation({ summary: '채팅 메시지 히스토리 조회 (커서 페이징)' })
  @ApiResponse({
    status: 200,
    description: 'Message history with pagination',
    schema: { example: Examples.GetMessagesSuccessExample },
  })
  @ApiResponse({ status: 403, description: '이 채팅방에 대한 권한이 없습니다' })
  @ApiResponse({ status: 404, description: '채팅방을 찾을 수 없습니다' })
  async getMessages(
    @CurrentUser() user: AuthenticatedUser,
    @Param('sessionId', ParseUUIDPipe) sessionId: string,
    @Query() query: MessageListQueryDto,
  ) {
    return this.chatService.getMessages(
      user.userId,
      sessionId,
      query.cursor,
      user.authorities,
    );
  }

  @Post('prompt')
  @Sse()
  @ApiOperation({
    summary: 'AI에게 질문 전송 (sessionId 없으면 세션 자동 생성)',
  })
  @ApiBody({ type: SendPromptDto })
  @ApiResponse({
    status: 200,
    description:
      'SSE 스트림 — text/event-stream. 이벤트 타입: connected | message | done | error',
    schema: { example: Examples.SendPromptSseExample },
  })
  sendPrompt(
    @CurrentUser() user: AuthenticatedUser,
    @Req() req: ExpressRequest,
    @Body() dto: SendPromptDto,
  ): Observable<MessageEvent> {
    const accessToken = (req.cookies as Record<string, string> | undefined)
      ?.access_token;
    return this._handlePrompt(user, accessToken, dto.sessionId ?? null, dto);
  }

  private _handlePrompt(
    user: AuthenticatedUser,
    accessToken: string | undefined,
    sessionIdOrNull: string | null,
    dto: SendPromptDto,
  ): Observable<MessageEvent> {
    return new Observable((subscriber) => {
      let resolvedSessionId = '';
      let currentTurn = 0;
      let fullResponse = '';
      let capturedSources: Array<{
        doc_id: string;
        doc_title: string;
        doc_content: string;
        location?: string;
      }> = [];
      let capturedUsage:
        | { input_tokens: number; output_tokens: number; total_tokens: number }
        | undefined;
      const abortController = new AbortController();

      (async () => {
        try {
          // 세션 확인 또는 자동 생성
          if (sessionIdOrNull) {
            await this.chatService.getSession(user.userId, sessionIdOrNull);
            resolvedSessionId = sessionIdOrNull;
          } else {
            const newSession = await this.chatService.createSession(
              user.userId,
              { favorites: 'N' },
            );
            resolvedSessionId = newSession.id;
          }

          // SSE 연결 성공 메시지 전송
          subscriber.next({
            type: 'connected',
            data: JSON.stringify({
              success: true,
              code: RC.EVENT_SUBSCRIBE_SUCCESS,
              message: ResponseMessage[RC.EVENT_SUBSCRIBE_SUCCESS],
              data: { sessionId: resolvedSessionId },
            }),
          });

          // 세션 컨텍스트 조회 (Redis 요약본 또는 히스토리)
          const context =
            await this.chatService.getSessionContext(resolvedSessionId);

          // 이전 대화 내역 조회 (chatTurn 계산용)
          const interactions = await this.chatService.getInteractions(
            user.userId,
            resolvedSessionId,
          );

          // 메시지 구성: 최근 대화 내역만 (요약본은 별도 필드로 전달)
          const messages: { role: string; content: string }[] = [];

          // 최근 대화 내역 추가 (recentHistory가 있으면 사용, 없으면 전체 interactions 사용)
          const historyToUse = context.recentHistory || interactions;
          for (const item of historyToUse) {
            if (item.type === 'Q') {
              messages.push({ role: 'user', content: item.content });
            } else if (item.type === 'A') {
              messages.push({ role: 'assistant', content: item.content });
            }
          }

          // 마지막 chatTurn 조회
          const lastInteraction =
            interactions.length > 0
              ? interactions[interactions.length - 1]
              : null;
          currentTurn = lastInteraction ? lastInteraction.chatTurn + 1 : 1;

          // 첫 질문인 경우 제목 자동 생성
          if (interactions.length === 0) {
            await this.chatService.setSessionTitleIfEmpty(
              user.userId,
              resolvedSessionId,
              dto.prompt,
            );
          }

          // 질문 저장
          await this.chatService.createInteraction(resolvedSessionId, {
            type: 'Q',
            content: dto.prompt,
            chatTurn: currentTurn,
          });

          // 챗봇 서버에 메시지 전송 (summary, user_position 포함)
          this.logger.debug(
            `📤 [Chatbot Request] sessionId=${resolvedSessionId}`,
          );
          this.logger.debug(`📤 [Query] "${dto.prompt}"`);
          this.logger.debug(
            `📤 [User Info] userId=${user.userId}, jobTitle=${user.jobTitle}, department=${user.department}`,
          );
          this.logger.debug(`📤 [History] ${messages.length} messages:`);
          messages.forEach((msg, idx) => {
            this.logger.debug(
              `   [${idx}] ${msg.role}: "${msg.content.substring(0, 100)}${msg.content.length > 100 ? '...' : ''}"`,
            );
          });
          if (context.summary) {
            this.logger.debug(
              `📤 [Summary] "${context.summary.substring(0, 200)}${context.summary.length > 200 ? '...' : ''}"`,
            );
          } else {
            this.logger.debug(`📤 [Summary] None`);
          }

          // 사용자의 RAG 제외 문서 목록 조회
          const excludedDocs = await this.chatService.getExcludedDocIds(
            user.userId,
          );

          const stream = this.chatbotService.sendMessage(
            {
              query: dto.prompt,
              history: messages,
              sessionId: resolvedSessionId,
              userId: user.userId,
              userPosition: user.jobTitle ?? undefined,
              authDeptIds: [
                ...new Set([
                  ...(user.authDeptId ? [user.authDeptId] : []),
                  ...(user.deptPermissions || []),
                ]),
              ],
              excludedDocs,
              summary: context.summary ?? undefined,
              accessToken,
            },
            abortController.signal,
          );

          // 챗봇 SSE 이벤트를 그대로 프론트에 패스스루
          for await (const event of stream) {
            // message 이벤트의 content만 DB 저장용으로 누적
            if (event.event === 'message' && event.content) {
              fullResponse += event.content;
            }

            // done 이벤트에서 참조 문서 + 토큰 사용량 캡처
            if (event.event === 'done') {
              if (event.sources) {
                capturedSources = event.sources;
              }
              if (event.usage) {
                capturedUsage = event.usage;
              }
            }

            // 챗봇 이벤트를 그대로 프론트에 전달
            subscriber.next({
              type: event.event,
              data: JSON.stringify(event),
            });
          }

          this.logger.debug(
            `📥 [Chatbot Response] sessionId=${resolvedSessionId}, responseLength=${fullResponse.length}, preview="${fullResponse.substring(0, 100)}..."`,
          );

          // 답변 저장
          await this._saveResponse(
            resolvedSessionId,
            currentTurn,
            fullResponse,
            capturedSources,
            capturedUsage,
            user.userId,
            dto.prompt,
          );

          subscriber.complete();
        } catch (error) {
          // 클라이언트 끊김으로 인한 abort인 경우 → 부분 답변 저장
          if (abortController.signal.aborted && fullResponse.length > 0) {
            this.logger.debug(
              `📥 [Client Disconnected] sessionId=${resolvedSessionId}, saving partial response (${fullResponse.length} chars)`,
            );
            await this._saveResponse(
              resolvedSessionId,
              currentTurn,
              fullResponse,
              capturedSources,
              capturedUsage,
              user.userId,
              dto.prompt,
            ).catch((e: Error) => {
              this.logger.warn(
                `Partial response save failed: ${e.message || 'Unknown'}`,
              );
            });
            return;
          }

          this.logger.error(
            `Error in sendPrompt: ${error instanceof Error ? error.message : 'Unknown error'}`,
          );
          // 에러 이벤트 전송
          subscriber.next({
            type: 'error',
            data: JSON.stringify({
              success: false,
              message: error instanceof Error ? error.message : 'Unknown error',
            }),
          });
          subscriber.error(error);
        }
      })();

      // 클라이언트 연결 해제 감지 → 에이전트 스트림 abort
      return () => {
        this.logger.debug(
          `Client disconnected from SSE, aborting agent stream: ${resolvedSessionId}`,
        );
        abortController.abort();
      };
    });
  }

  /**
   * 답변 저장 + 문서 참조 저장 + Redis 캐시 업데이트 (정상 완료 / 부분 저장 공통)
   */
  private async _saveResponse(
    sessionId: string,
    chatTurn: number,
    fullResponse: string,
    capturedSources: Array<{
      doc_id: string;
      doc_title: string;
      doc_content: string;
      location?: string;
    }>,
    capturedUsage:
      | { input_tokens: number; output_tokens: number; total_tokens: number }
      | undefined,
    userId: string,
    prompt: string,
  ): Promise<void> {
    const answerInteraction = await this.chatService.createAnswerInteraction({
      sessionId,
      chatTurn,
      content: fullResponse,
      inputTokens: capturedUsage?.input_tokens,
      outputTokens: capturedUsage?.output_tokens,
      sourceDocIds: capturedSources.map((s) => s.doc_id),
      userId,
    });

    // 문서 참조 저장 (백그라운드)
    if (capturedSources.length > 0) {
      this.chatService
        .addDocumentReferences(
          answerInteraction.id,
          capturedSources.map((s) => ({
            documentContentId: s.doc_id,
            relevance: 0,
            location: s.location || null,
          })),
        )
        .catch((e: Error) => {
          this.logger.warn(
            `Document reference save failed: ${e.message || 'Unknown'}`,
          );
        });
    }

    // Redis 캐시 업데이트
    this.chatService
      .updateSessionCache(
        sessionId,
        { content: prompt, chatTurn },
        { content: fullResponse, chatTurn },
      )
      .catch((e: Error) => {
        this.logger.warn(
          `Background cache update failed: ${e.message || 'Unknown'}`,
        );
      });
  }

  // ============================================================
  // Feedback Endpoints
  // ============================================================

  @Patch('interactions/:interactionId/feedback')
  @ResponseCode(RC.CHAT_FEEDBACK_SUCCESS)
  @ApiOperation({ summary: 'AI 답변 피드백 토글' })
  @ApiResponse({
    status: 200,
    description: '피드백이 저장되었습니다',
    schema: { example: Examples.ToggleFeedbackSuccessExample },
  })
  @ApiBody({ type: SubmitFeedbackDto })
  @ApiResponse({
    status: 400,
    description: '답변에만 피드백을 남길 수 있습니다',
  })
  @ApiResponse({ status: 403, description: '이 대화에 대한 권한이 없습니다' })
  @ApiResponse({ status: 404, description: '대화 내역을 찾을 수 없습니다' })
  async toggleFeedback(
    @CurrentUser() user: AuthenticatedUser,
    @Param('interactionId', ParseUUIDPipe) interactionId: string,
    @Body() dto: SubmitFeedbackDto,
  ) {
    return this.chatService.setFeedback(
      user.userId,
      interactionId,
      dto.feedback,
      user.authorities,
    );
  }

  // ============================================================
  // Document Reference Endpoints
  // ============================================================

  @Get('interactions/:interactionId/documents')
  @ResponseCode(RC.CHAT_DOC_REF_LIST_SUCCESS)
  @ApiOperation({ summary: '대화의 문서 참조 조회' })
  @ApiResponse({
    status: 200,
    description: 'List of document references',
    schema: { example: Examples.GetDocumentReferencesSuccessExample },
  })
  async getDocumentReferences(
    @CurrentUser() user: AuthenticatedUser,
    @Param('interactionId', ParseUUIDPipe) interactionId: string,
  ) {
    // 권한 검증
    const interaction = await this.chatService.getInteraction(interactionId);
    await this.chatService.getSession(
      user.userId,
      interaction.sessionId,
      user.authorities,
    );

    return {
      data: await this.chatService.getDocumentReferences(interactionId),
    };
  }

  @Post('interactions/:interactionId/documents')
  @ResponseCode(RC.CHAT_DOC_REF_ADDED)
  @ApiOperation({ summary: '대화에 문서 참조 추가' })
  @ApiBody({ type: AddDocumentReferenceDto })
  @ApiResponse({
    status: 201,
    description: 'Document reference added',
    schema: { example: Examples.AddDocumentReferenceSuccessExample },
  })
  async addDocumentReference(
    @CurrentUser() user: AuthenticatedUser,
    @Param('interactionId', ParseUUIDPipe) interactionId: string,
    @Body() dto: AddDocumentReferenceDto,
  ) {
    // 권한 검증
    const interaction = await this.chatService.getInteraction(interactionId);
    await this.chatService.getSession(
      user.userId,
      interaction.sessionId,
      user.authorities,
    );

    return {
      data: await this.chatService.addDocumentReference(
        interactionId,
        dto.documentContentId,
      ),
    };
  }

  @Delete('documents/:referenceId')
  @ResponseCode(RC.CHAT_DOC_REF_DELETED)
  @ApiOperation({ summary: '문서 참조 삭제' })
  @ApiResponse({
    status: 200,
    description: 'Document reference deleted',
    schema: { example: Examples.DeleteDocumentReferenceSuccessExample },
  })
  async deleteDocumentReference(
    @CurrentUser() user: AuthenticatedUser,
    @Param('referenceId', ParseUUIDPipe) referenceId: string,
  ) {
    return {
      data: await this.chatService.deleteDocumentReference(
        user.userId,
        referenceId,
        user.authorities,
      ),
    };
  }
}
