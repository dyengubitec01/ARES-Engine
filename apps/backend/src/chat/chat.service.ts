import { Injectable, BadRequestException, Logger } from '@nestjs/common';
import { InjectRepository, InjectDataSource } from '@nestjs/typeorm';
import { DataSource, In, Repository } from 'typeorm';
import { BusinessException } from '../common/exceptions/business.exception';
import {
  ResponseCode,
  getHttpStatus,
} from '../common/constants/response-codes';
import { ChatSession } from './entities/chat-session.entity';
import { ChatInteraction } from './entities/chat-interaction.entity';
import { ChatDocumentReference } from './entities/chat-document-reference.entity';
import { AuthUser } from '../auth/entities/auth-user.entity';
import { DocDocumentExclude } from '../document/entities/doc-document-exclude.entity';
import { DocDocumentContent } from '../document/entities/doc-document-content.entity';

import {
  CreateChatSessionDto,
  CreateInteractionDto,
  SendPromptDto,
} from './dto/chat.dto';
import { AuthorityType } from '../common/enums';
import { RedisService } from '../external/redis/redis.service';
import { ToolsService } from '../external/tools/tools.service';

export interface SessionContext {
  summary: string | null;
  isFirstQuestion: boolean;
  source: 'redis' | 'tools' | 'none';
  // Story 2.13 Fix: Recent history pairs to maintain sliding window consistency
  recentHistory?: Array<{
    type: 'Q' | 'A';
    content: string;
    chatTurn: number;
  }>;
}

// Story 2.13: Sliding window compression constants
const COMPRESSION_TRIGGER_COUNT = 20; // Trigger compression at 20 pairs
const CACHE_TTL_SECONDS = 3600; // 1 hour TTL

@Injectable()
export class ChatService {
  private readonly logger = new Logger(ChatService.name);

  constructor(
    @InjectRepository(ChatSession)
    private sessionRepository: Repository<ChatSession>,
    @InjectRepository(ChatInteraction)
    private interactionRepository: Repository<ChatInteraction>,
    @InjectRepository(ChatDocumentReference)
    private documentRefRepository: Repository<ChatDocumentReference>,
    @InjectRepository(AuthUser)
    private authUserRepository: Repository<AuthUser>,
    @InjectRepository(DocDocumentExclude)
    private excludeRepository: Repository<DocDocumentExclude>,
    @InjectRepository(DocDocumentContent)
    private docContentRepository: Repository<DocDocumentContent>,
    @InjectDataSource()
    private dataSource: DataSource,
    private redisService: RedisService,
    private toolsService: ToolsService,
  ) {}

  /**
   * 첫 질문 기반으로 제목 자동 생성 (최대 20자)
   */
  generateTitleFromQuestion(question: string): string {
    const maxLength = 20;
    if (question.length <= maxLength) {
      return question;
    }
    return question.substring(0, maxLength - 3) + '...';
  }

  /**
   * 첫 질문 시 세션 제목 자동 설정
   */
  async setSessionTitleIfEmpty(
    userId: string,
    sessionId: string,
    firstQuestion: string,
  ) {
    const session = await this.sessionRepository.findOne({
      where: { id: sessionId, usersId: userId },
    });
    if (session && !session.title) {
      session.title = this.generateTitleFromQuestion(firstQuestion);
      await this.sessionRepository.save(session);
      return session.title;
    }
    return session?.title ?? null;
  }

  // ============================================================
  // Session Methods
  // ============================================================

  /**
   * 세션 컨텍스트 조회 (Redis 캐시 우선)
   *
   * Flow:
   * 1. Redis 캐시 확인 (summary + history)
   * 2. 캐시 hit → 바로 반환 (DB 조회 없음)
   * 3. 캐시 miss → DB 조회 후 Redis에 저장
   */
  async getSessionContext(sessionId: string): Promise<SessionContext> {
    // 1. Redis 캐시 확인 (summary + history)
    const cached = await this.redisService.getSessionCache(sessionId);

    if (cached) {
      this.logger.debug(
        `Redis cache hit for session ${sessionId}: summary=${cached.summary ? 'yes' : 'no'}, history=${cached.history.length}`,
      );
      return {
        summary: cached.summary,
        isFirstQuestion: false,
        source: 'redis',
        recentHistory: cached.history,
      };
    }

    // 2. 캐시 miss → DB 조회
    const history = await this.interactionRepository.find({
      where: { sessionId },
      order: { chatTurn: 'ASC', createdAt: 'ASC' },
    });

    // 3. 히스토리 없음 → 첫 질문
    if (history.length === 0) {
      this.logger.debug(`No history for session ${sessionId}, first question`);
      return {
        summary: null,
        isFirstQuestion: true,
        source: 'none',
      };
    }

    // 4. 히스토리 포맷팅
    const allHistoryFormatted = history.map((h) => ({
      type: h.type as 'Q' | 'A',
      content: h.content,
      chatTurn: h.chatTurn,
    }));

    // 5. DB에서 조회한 데이터를 Redis에 캐싱
    await this.redisService.setSessionCache(
      sessionId,
      { summary: null, history: allHistoryFormatted },
      CACHE_TTL_SECONDS,
    );

    this.logger.debug(
      `Cache miss for session ${sessionId}: loaded ${allHistoryFormatted.length} messages from DB and cached`,
    );

    return {
      summary: null,
      isFirstQuestion: false,
      source: 'none',
      recentHistory: allHistoryFormatted,
    };
  }

  async createSession(usersId: string, dto: CreateChatSessionDto) {
    // 사용자 정보 조회 (이름, 부서)
    const user = await this.authUserRepository.findOne({
      where: { id: usersId },
      relations: ['authDept'],
    });

    const session = this.sessionRepository.create({
      usersId,
      favorites: dto.favorites ?? 'N',
    });
    const savedSession = await this.sessionRepository.save(session);

    return {
      id: savedSession.id,
      title: savedSession.title,
      userName: user?.name ?? null,
      userDept: user?.authDept?.deptName ?? null,
      createdAt: savedSession.createdAt,
    };
  }

  async getSessions(
    usersId: string,
    cursor?: string,
    limit: number = 20,
  ): Promise<{
    items: Array<{
      id: string;
      title: string | null;
      favorites: string;
      createdAt: Date;
      messageCount: number;
    }>;
    nextCursor: string | null;
    hasMore: boolean;
  }> {
    const queryBuilder = this.sessionRepository
      .createQueryBuilder('s')
      .leftJoin('s.interactions', 'i')
      .select([
        's.id AS id',
        's.title AS title',
        's.favorites AS favorites',
        's.created_at AS "createdAt"',
        'COUNT(i.id)::int AS "messageCount"',
        'MAX(i.created_at) AS "lastMessageAt"',
      ])
      .where('s.users_id = :usersId', { usersId })
      .andWhere('s.deleted_at IS NULL')
      .groupBy('s.id')
      .orderBy('"lastMessageAt"', 'DESC', 'NULLS LAST')
      .addOrderBy('s.created_at', 'DESC');

    if (cursor) {
      // 커서 기반 페이징: 커서 세션의 lastMessageAt 이전 항목만 조회
      const cursorSession = await this.sessionRepository
        .createQueryBuilder('s')
        .leftJoin('s.interactions', 'i')
        .select(['s.id', 'MAX(i.created_at) AS "lastMessageAt"'])
        .where('s.id = :cursor', { cursor })
        .groupBy('s.id')
        .getRawOne();

      if (cursorSession) {
        queryBuilder.andWhere(
          '(MAX(i.created_at) < :cursorTime OR (MAX(i.created_at) IS NULL AND s.created_at < :cursorCreatedAt) OR (MAX(i.created_at) = :cursorTime AND s.id < :cursor))',
          {
            cursorTime: cursorSession.lastMessageAt,
            cursorCreatedAt: cursorSession.createdAt,
            cursor,
          },
        );
      }
    }

    // hasMore 판단을 위해 limit + 1 조회
    const results = await queryBuilder.limit(limit + 1).getRawMany();

    const hasMore = results.length > limit;
    const data = hasMore ? results.slice(0, limit) : results;
    const nextCursor =
      hasMore && data.length > 0 ? data[data.length - 1].id : null;

    return {
      items: data.map((row) => ({
        id: row.id,
        title: row.title,
        favorites: row.favorites,
        createdAt: row.createdAt,
        messageCount: row.messageCount ?? 0,
      })),
      nextCursor,
      hasMore,
    };
  }

  async getSession(usersId: string, sessionId: string, authorities?: string[]) {
    // 1. 세션 조회
    const session = await this.sessionRepository.findOne({
      where: { id: sessionId },
    });

    // 2. 존재 확인
    if (!session) {
      throw new BusinessException(
        ResponseCode.CHAT_SESSION_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.CHAT_SESSION_NOT_FOUND),
      );
    }

    // 3. 권한 검증 (ADMIN 또는 소유자)
    if (authorities?.includes(AuthorityType.ADMIN)) {
      return session;
    }
    if (session.usersId !== usersId) {
      throw new BusinessException(
        ResponseCode.CHAT_SESSION_FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.CHAT_SESSION_FORBIDDEN),
      );
    }

    return session;
  }

  async deleteSession(
    usersId: string,
    sessionId: string,
    authorities?: string[],
  ) {
    // 1. 채팅방 조회
    const session = await this.sessionRepository.findOne({
      where: { id: sessionId },
    });

    // 2. 존재 확인
    if (!session) {
      throw new BusinessException(
        ResponseCode.CHAT_SESSION_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.CHAT_SESSION_NOT_FOUND),
      );
    }

    // 3. 권한 검증 (ADMIN 또는 소유자)
    if (
      !authorities?.includes(AuthorityType.ADMIN) &&
      session.usersId !== usersId
    ) {
      throw new BusinessException(
        ResponseCode.CHAT_SESSION_FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.CHAT_SESSION_FORBIDDEN),
      );
    }

    // 4. Redis 캐시 삭제 (세션 삭제 시 캐시도 삭제)
    await this.redisService.deleteSessionCache(sessionId);

    // 5. Soft Delete (deleted_at 설정, DB 기록 보존)
    await this.sessionRepository.softDelete(sessionId);
    return { message: '채팅방이 삭제되었습니다' };
  }

  async toggleFavorite(
    usersId: string,
    sessionId: string,
    authorities?: string[],
  ) {
    // 1. 채팅방 조회
    const session = await this.sessionRepository.findOne({
      where: { id: sessionId },
    });

    // 2. 존재 확인
    if (!session) {
      throw new BusinessException(
        ResponseCode.CHAT_SESSION_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.CHAT_SESSION_NOT_FOUND),
      );
    }

    // 3. 권한 검증 (ADMIN 또는 소유자)
    if (
      !authorities?.includes(AuthorityType.ADMIN) &&
      session.usersId !== usersId
    ) {
      throw new BusinessException(
        ResponseCode.CHAT_SESSION_FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.CHAT_SESSION_FORBIDDEN),
      );
    }

    // 4. 토글
    session.favorites = session.favorites === 'Y' ? 'N' : 'Y';
    await this.sessionRepository.save(session);

    // 5. 메시지 결정
    const message =
      session.favorites === 'Y'
        ? '즐겨찾기에 추가되었습니다'
        : '즐겨찾기에서 제거되었습니다';

    return {
      data: {
        id: session.id,
        title: session.title,
        favorites: session.favorites,
      },
      message,
    };
  }

  async updateSession(
    usersId: string,
    sessionId: string,
    title: string,
    authorities?: string[],
  ) {
    // 1. 채팅방 조회
    const session = await this.sessionRepository.findOne({
      where: { id: sessionId },
    });

    // 2. 존재 확인
    if (!session) {
      throw new BusinessException(
        ResponseCode.CHAT_SESSION_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.CHAT_SESSION_NOT_FOUND),
      );
    }

    // 3. 권한 검증 (ADMIN 또는 소유자)
    if (
      !authorities?.includes(AuthorityType.ADMIN) &&
      session.usersId !== usersId
    ) {
      throw new BusinessException(
        ResponseCode.CHAT_SESSION_FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.CHAT_SESSION_FORBIDDEN),
      );
    }

    // 4. 제목 업데이트
    session.title = title;
    await this.sessionRepository.save(session);

    return {
      id: session.id,
      title: session.title,
    };
  }

  // ============================================================
  // Interaction Methods
  // ============================================================

  async getInteractions(usersId: string, sessionId: string) {
    await this.getSession(usersId, sessionId);

    return this.interactionRepository.find({
      where: { sessionId },
      order: { chatTurn: 'ASC', createdAt: 'ASC' },
    });
  }

  async getMessages(
    usersId: string,
    sessionId: string,
    cursor?: number,
    authorities?: string[],
  ) {
    // 1. 채팅방 조회
    const session = await this.sessionRepository.findOne({
      where: { id: sessionId },
    });

    // 2. 존재 확인
    if (!session) {
      throw new BusinessException(
        ResponseCode.CHAT_SESSION_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.CHAT_SESSION_NOT_FOUND),
      );
    }

    // 3. 권한 검증 (ADMIN 또는 소유자)
    if (
      !authorities?.includes(AuthorityType.ADMIN) &&
      session.usersId !== usersId
    ) {
      throw new BusinessException(
        ResponseCode.CHAT_SESSION_FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.CHAT_SESSION_FORBIDDEN),
      );
    }

    // 4. Q/A 쌍 10개 조회 (chat_turn 기준)
    const pairCount = 10;

    // chat_turn distinct 값 기준으로 10개 조회
    const queryBuilder = this.interactionRepository
      .createQueryBuilder('i')
      .select('DISTINCT i.chat_turn', 'chatTurn')
      .where('i.session_id = :sessionId', { sessionId })
      .orderBy('i.chat_turn', 'DESC')
      .limit(pairCount + 1);

    if (cursor) {
      queryBuilder.andWhere('i.chat_turn < :cursor', { cursor });
    }

    const distinctTurns = await queryBuilder.getRawMany();

    const hasMore = distinctTurns.length > pairCount;
    const targetTurns = distinctTurns
      .slice(0, pairCount)
      .map((t) => t.chatTurn);

    // 빈 히스토리 처리
    if (targetTurns.length === 0) {
      return {
        items: [],
        nextCursor: null,
        hasMore: false,
      };
    }

    // 해당 turn의 모든 메시지 조회
    const messages = await this.interactionRepository
      .createQueryBuilder('i')
      .where('i.session_id = :sessionId', { sessionId })
      .andWhere('i.chat_turn IN (:...turns)', { turns: targetTurns })
      .orderBy('i.chat_turn', 'ASC')
      .addOrderBy('i.type', 'DESC')
      .getMany();

    // nextCursor 계산
    const nextCursor =
      hasMore && targetTurns.length > 0 ? Math.min(...targetTurns) : null;

    return {
      items: messages.map((m) => ({
        id: m.id,
        type: m.type,
        content: m.content,
        chatTurn: m.chatTurn,
        feedback: m.feedback,
        createdAt: m.createdAt,
      })),
      nextCursor,
      hasMore,
    };
  }

  async createInteraction(sessionId: string, dto: CreateInteractionDto) {
    // 마지막 chatTurn 조회
    let chatTurn = dto.chatTurn;
    if (chatTurn === undefined) {
      const lastInteraction = await this.interactionRepository.findOne({
        where: { sessionId },
        order: { chatTurn: 'DESC' },
      });
      chatTurn = lastInteraction ? lastInteraction.chatTurn + 1 : 1;
    }

    const interaction = this.interactionRepository.create({
      sessionId,
      type: dto.type ?? 'Q',
      content: dto.content,
      chatTurn,
    });
    return this.interactionRepository.save(interaction);
  }

  /**
   * 답변 저장 (토큰 사용량 + self/other 인용 카운트 포함)
   * - usage: agent 응답의 usage.input_tokens / output_tokens
   * - sourceDocIds: agent 응답의 sources[].doc_id 목록
   * - userId: 질문한 사용자 (본인/타인 인용 구분 기준)
   */
  async createAnswerInteraction(params: {
    sessionId: string;
    chatTurn: number;
    content: string;
    inputTokens?: number;
    outputTokens?: number;
    sourceDocIds: string[];
    userId: string;
  }) {
    let selfCount = 0;
    let otherCount = 0;

    if (params.sourceDocIds.length > 0) {
      const docs = await this.docContentRepository.find({
        select: ['uploaderId'],
        where: { id: In(params.sourceDocIds) },
      });
      for (const doc of docs) {
        if (doc.uploaderId === params.userId) selfCount++;
        else otherCount++;
      }
    }

    const interaction = this.interactionRepository.create({
      sessionId: params.sessionId,
      type: 'A',
      content: params.content,
      chatTurn: params.chatTurn,
      inputTokens: params.inputTokens ?? null,
      outputTokens: params.outputTokens ?? null,
      selfCitationCount: selfCount,
      otherCitationCount: otherCount,
    });

    return this.interactionRepository.save(interaction);
  }

  async getInteraction(interactionId: string) {
    const interaction = await this.interactionRepository.findOne({
      where: { id: interactionId },
      relations: ['session'],
    });

    if (!interaction) {
      throw new BusinessException(
        ResponseCode.CHAT_INTERACTION_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.CHAT_INTERACTION_NOT_FOUND),
      );
    }

    return interaction;
  }

  // ============================================================
  // Feedback Methods
  // ============================================================

  async setFeedback(
    usersId: string,
    interactionId: string,
    feedback: string | null,
    authorities?: string[],
  ) {
    // 1. interaction 조회 (세션 정보 포함)
    const interaction = await this.interactionRepository.findOne({
      where: { id: interactionId },
      relations: ['session'],
    });

    // 2. 존재 확인
    if (!interaction) {
      throw new BusinessException(
        ResponseCode.CHAT_INTERACTION_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.CHAT_INTERACTION_NOT_FOUND),
      );
    }

    // 3. type='A' 검증 (답변만 피드백 가능)
    if (interaction.type !== 'A') {
      throw new BadRequestException('답변에만 피드백을 남길 수 있습니다');
    }

    // 4. 권한 검증 (ADMIN 또는 소유자)
    if (
      !authorities?.includes(AuthorityType.ADMIN) &&
      interaction.session.usersId !== usersId
    ) {
      throw new BusinessException(
        ResponseCode.CHAT_INTERACTION_FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.CHAT_INTERACTION_FORBIDDEN),
      );
    }

    // 5. 피드백 값 저장 (같은 값 재전송 시 null로 토글)
    interaction.feedback = interaction.feedback === feedback ? null : feedback;
    await this.interactionRepository.save(interaction);

    return {
      data: {
        interactionId: interaction.id,
        feedback: interaction.feedback,
      },
      message: '피드백이 저장되었습니다',
    };
  }

  // ============================================================
  // Document Reference Methods
  // ============================================================

  async addDocumentReference(
    chatInteractionId: string,
    documentContentId: string,
    relevance?: number,
    location?: string | null,
  ) {
    // 중복 체크
    const existingRef = await this.documentRefRepository.findOne({
      where: { chatInteractionId, documentContentId },
    });

    if (existingRef) {
      // Update relevance/location if provided
      let updated = false;
      if (relevance !== undefined && existingRef.relevance !== relevance) {
        existingRef.relevance = relevance;
        updated = true;
      }
      if (location !== undefined && existingRef.location !== location) {
        existingRef.location = location;
        updated = true;
      }
      return updated
        ? this.documentRefRepository.save(existingRef)
        : existingRef;
    }

    const ref = this.documentRefRepository.create({
      chatInteractionId,
      documentContentId,
      relevance: relevance ?? null,
      location: location ?? null,
    });
    return this.documentRefRepository.save(ref);
  }

  /**
   * Add multiple document references with relevance scores and location
   */
  async addDocumentReferences(
    chatInteractionId: string,
    references: Array<{
      documentContentId: string;
      relevance: number;
      location?: string | null;
    }>,
  ) {
    const results: ChatDocumentReference[] = [];
    for (const ref of references) {
      const saved = await this.addDocumentReference(
        chatInteractionId,
        ref.documentContentId,
        ref.relevance,
        ref.location,
      );
      results.push(saved);
    }
    return results;
  }

  async getDocumentReferences(chatInteractionId: string) {
    return this.documentRefRepository.find({
      where: { chatInteractionId },
      relations: ['docContent'],
    });
  }

  async deleteDocumentReference(
    usersId: string,
    referenceId: string,
    authorities?: string[],
  ) {
    const ref = await this.documentRefRepository.findOne({
      where: { id: referenceId },
      relations: ['interaction', 'interaction.session'],
    });

    if (!ref) {
      throw new BusinessException(
        ResponseCode.CHAT_DOC_REF_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.CHAT_DOC_REF_NOT_FOUND),
      );
    }

    if (
      !authorities?.includes(AuthorityType.ADMIN) &&
      ref.interaction.session.usersId !== usersId
    ) {
      throw new BusinessException(
        ResponseCode.CHAT_DOC_REF_FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.CHAT_DOC_REF_FORBIDDEN),
      );
    }

    await this.documentRefRepository.remove(ref);
    return { message: 'Document reference deleted' };
  }

  // ============================================================
  // Story 2.13: Conversation Compression Methods
  // ============================================================

  /**
   * Get Q/A pair count for a session (AC1)
   * Counts distinct chatTurn values (each turn = 1 Q/A pair)
   */
  async getSessionPairCount(sessionId: string): Promise<number> {
    const result = await this.interactionRepository
      .createQueryBuilder('i')
      .select('COUNT(DISTINCT i.chat_turn)', 'count')
      .where('i.session_id = :sessionId', { sessionId })
      .getRawOne();

    return parseInt(result?.count || '0', 10);
  }

  /**
   * Story 2.13: Update session cache with sliding window compression
   *
   * Sliding Window Algorithm:
   * - Under 20 pairs: Store all as original history
   * - 20+ pairs: Compress oldest, keep 10~19 pairs as original
   *   - 20 pairs: 10 summary + 10 history
   *   - 29 pairs: 10 summary + 19 history
   *   - 30 pairs: 20 summary + 10 history
   *   - 32 pairs: 20 summary + 12 history
   *
   * Flow:
   * 1. Get current cache from Redis
   * 2. Add new Q/A to history
   * 3. If 20+ pairs and hit compression trigger → compress 10 pairs
   * 4. Save updated cache to Redis
   */
  async updateSessionCache(
    sessionId: string,
    newQuestion: { content: string; chatTurn: number },
    newAnswer: { content: string; chatTurn: number },
  ): Promise<void> {
    try {
      // 1. Get current cache
      const cached = await this.redisService.getSessionCache(sessionId);
      let summary = cached?.summary || null;
      let history = cached?.history || [];

      // 2. Add new Q/A to history
      history.push(
        {
          type: 'Q',
          content: newQuestion.content,
          chatTurn: newQuestion.chatTurn,
        },
        { type: 'A', content: newAnswer.content, chatTurn: newAnswer.chatTurn },
      );

      // 3. Count pairs (각 chatTurn = 1쌍)
      const pairCount = Math.max(...history.map((h) => h.chatTurn));

      this.logger.debug(
        `Session ${sessionId}: ${pairCount} pairs, history=${history.length} items`,
      );

      // 4. Compression trigger logic (Story 2.13 Fix)
      // Invariant: Always maintain 10~19 pairs of history
      // Compression is always in multiples of 10
      // Examples:
      //   20 pairs → compress 10 → 10 history
      //   29 pairs → compress 10 → 19 history
      //   30 pairs → compress 20 → 10 history
      //   58 pairs → compress 40 → 18 history
      //   66 pairs → compress 50 → 16 history
      const uniqueTurns = [...new Set(history.map((h) => h.chatTurn))].sort(
        (a, b) => a - b,
      );
      const historyPairCount = uniqueTurns.length;

      // Compression trigger: 20개 이상이면 압축 필요
      if (historyPairCount >= COMPRESSION_TRIGGER_COUNT) {
        // 압축할 쌍 수 = 10단위로 맞춤, 10~19개 히스토리 남기기
        // 공식: Math.floor(historyPairCount / 10) * 10 - 10
        const pairsToCompressCount =
          Math.floor(historyPairCount / 10) * 10 - 10;

        if (pairsToCompressCount > 0) {
          this.logger.debug(
            `Session ${sessionId}: compression needed (${historyPairCount} pairs), compressing ${pairsToCompressCount} pairs, leaving ${historyPairCount - pairsToCompressCount} pairs`,
          );

          // 압축할 쌍 선택 (가장 오래된 N쌍)
          const pairsToCompress: Array<{ question: string; answer: string }> =
            [];
          const turnsToCompress = new Set<number>();
          const compressTurns = uniqueTurns.slice(0, pairsToCompressCount);

          for (const turn of compressTurns) {
            turnsToCompress.add(turn);
            const q = history.find(
              (h) => h.chatTurn === turn && h.type === 'Q',
            );
            const a = history.find(
              (h) => h.chatTurn === turn && h.type === 'A',
            );
            if (q && a) {
              pairsToCompress.push({ question: q.content, answer: a.content });
            }
          }

          // Tools API로 압축
          const newSummary = await this.toolsService.compressSummary(
            sessionId,
            summary,
            pairsToCompress,
          );

          if (newSummary) {
            summary = newSummary;
            // 압축된 쌍들을 히스토리에서 제거
            history = history.filter((h) => !turnsToCompress.has(h.chatTurn));
            this.logger.log(
              `Session ${sessionId}: compressed ${compressTurns.length} pairs, remaining ${history.length} items`,
            );
          } else {
            this.logger.warn(
              `Session ${sessionId}: compression failed, keeping original history`,
            );
          }
        }
      }

      // 5. Save to Redis
      await this.redisService.setSessionCache(
        sessionId,
        { summary, history },
        CACHE_TTL_SECONDS,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.warn(
        `Failed to update session cache for ${sessionId}: ${message}`,
      );
    }
  }

  // ============================================================
  // AI Prompt Methods
  // ============================================================

  async sendPrompt(usersId: string, sessionId: string, dto: SendPromptDto) {
    // 세션 확인
    const session = await this.getSession(usersId, sessionId);

    // 마지막 chatTurn 조회
    const lastInteraction = await this.interactionRepository.findOne({
      where: { sessionId },
      order: { chatTurn: 'DESC' },
    });
    const currentTurn = lastInteraction ? lastInteraction.chatTurn + 1 : 1;

    // 첫 질문인 경우 제목 자동 생성
    if (!session.title && currentTurn === 1) {
      session.title = this.generateTitleFromQuestion(dto.prompt);
      await this.sessionRepository.save(session);
    }

    // 질문 저장
    const questionInteraction = await this.interactionRepository.save(
      this.interactionRepository.create({
        sessionId,
        type: 'Q',
        content: dto.prompt,
        chatTurn: currentTurn,
      }),
    );

    // TODO: AI 서비스 호출하여 응답 생성
    const aiResponse = `[AI 응답 placeholder] 질문: ${dto.prompt}`;

    // 답변 저장
    const answerInteraction = await this.interactionRepository.save(
      this.interactionRepository.create({
        sessionId,
        type: 'A',
        content: aiResponse,
        chatTurn: currentTurn,
      }),
    );

    // Story 2.13: Update Redis cache with new Q/A (sliding window)
    // Run asynchronously to not block the response
    this.updateSessionCache(
      sessionId,
      { content: dto.prompt, chatTurn: currentTurn },
      { content: aiResponse, chatTurn: currentTurn },
    ).catch((error) => {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.warn(`Background cache update failed: ${message}`);
    });

    return {
      question: questionInteraction,
      answer: answerInteraction,
    };
  }

  /**
   * 사용자의 RAG 제외 문서 content ID 목록 조회
   */
  async getExcludedDocIds(userId: string): Promise<string[]> {
    const excludes = await this.excludeRepository.find({
      where: { userId },
      select: ['documentContentId'],
    });
    return excludes.map((e) => e.documentContentId);
  }
}
