/**
 * ⚠️ DEV ONLY - Redis 디버깅용 컨트롤러
 * 프로덕션 배포 시 비활성화 또는 제거 필요
 */
import {
  Controller,
  Get,
  Param,
  Delete,
  Logger,
  UseGuards,
} from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse, ApiParam } from '@nestjs/swagger';
import { RedisService } from './redis.service';
import { ResponseCode } from '../../common/decorators/response-code.decorator';
import { ResponseCode as RC } from '../../common/constants/response-codes';
import { DevOnlyGuard } from '../../common/guards/dev-only.guard';

@ApiTags('🔧 [DEV] Redis Debug')
@UseGuards(DevOnlyGuard)
@Controller('dev/redis')
export class RedisController {
  private readonly logger = new Logger(RedisController.name);

  constructor(private readonly redisService: RedisService) {}

  /**
   * Redis 연결 상태 확인
   */
  @Get('health')
  @ResponseCode(RC.DEV_REDIS_HEALTH_SUCCESS)
  @ApiOperation({
    summary: '[DEV] Redis 연결 상태 확인',
    description: '⚠️ 개발용 API - Redis 서버 연결 상태를 확인합니다.',
  })
  @ApiResponse({ status: 200, description: 'Redis 연결 상태' })
  async healthCheck() {
    const isConnected = await this.redisService.healthCheck();
    return {
      _dev: '⚠️ 개발용 API',
      redis: {
        connected: isConnected,
        status: isConnected ? '✅ Connected' : '❌ Disconnected',
      },
    };
  }

  /**
   * 모든 키 목록 조회
   */
  @Get('keys')
  @ResponseCode(RC.DEV_REDIS_KEYS_SUCCESS)
  @ApiOperation({
    summary: '[DEV] 모든 Redis 키 조회',
    description: '⚠️ 개발용 API - 저장된 모든 Redis 키 목록을 조회합니다.',
  })
  @ApiResponse({ status: 200, description: 'Redis 키 목록' })
  async getAllKeys() {
    const keys = await this.redisService.getAllKeys();

    // 키별 정보 수집
    const keyDetails = await Promise.all(
      keys.map(async (key) => {
        const ttl = await this.redisService.getTTL(key);
        const value = await this.redisService.getByKey(key);

        // 세션 ID 추출 (키 패턴에서)
        const sessionIdMatch = key.match(/:session:([^:]+)$/);
        const sessionId = sessionIdMatch ? sessionIdMatch[1] : null;

        // 값 파싱 시도
        let parsed = null;
        let pairCount = 0;
        let hasSummary = false;
        try {
          if (value) {
            parsed = JSON.parse(value);
            if (parsed.history) {
              const uniqueTurns = [
                ...new Set(
                  parsed.history.map((h: { chatTurn: number }) => h.chatTurn),
                ),
              ];
              pairCount = uniqueTurns.length;
            }
            hasSummary = !!parsed.summary;
          }
        } catch {
          // JSON 파싱 실패
        }

        return {
          key,
          sessionId,
          ttl: ttl === -1 ? '무제한' : ttl === -2 ? '만료됨' : `${ttl}초`,
          stats: parsed
            ? {
                pairCount,
                historyItems: parsed.history?.length || 0,
                hasSummary,
              }
            : null,
        };
      }),
    );

    return {
      _dev: '⚠️ 개발용 API',
      totalKeys: keys.length,
      keyPrefix: 'dev:rag:backend:*',
      keys: keyDetails,
    };
  }

  /**
   * 특정 세션의 캐시 데이터 조회
   */
  @Get('session/:sessionId')
  @ResponseCode(RC.DEV_REDIS_SESSION_SUCCESS)
  @ApiOperation({
    summary: '[DEV] 세션 캐시 데이터 조회',
    description: '⚠️ 개발용 API - 특정 세션의 Redis 캐시 데이터를 조회합니다.',
  })
  @ApiParam({ name: 'sessionId', description: '세션 ID' })
  @ApiResponse({ status: 200, description: '세션 캐시 데이터' })
  async getSessionCache(@Param('sessionId') sessionId: string) {
    const cached = await this.redisService.getSessionCache(sessionId);

    if (!cached) {
      return {
        _dev: '⚠️ 개발용 API',
        sessionId,
        status: '❌ Cache not found',
        data: null,
      };
    }

    // 히스토리 쌍 개수 계산
    const uniqueTurns = [...new Set(cached.history.map((h) => h.chatTurn))];
    const pairCount = uniqueTurns.length;

    // 히스토리 요약 (긴 내용은 잘라서 표시)
    const historySummary = cached.history.map((h) => ({
      type: h.type,
      chatTurn: h.chatTurn,
      contentPreview:
        h.content.length > 50 ? h.content.substring(0, 50) + '...' : h.content,
      contentLength: h.content.length,
    }));

    return {
      _dev: '⚠️ 개발용 API',
      sessionId,
      status: '✅ Cache found',
      stats: {
        pairCount,
        historyItems: cached.history.length,
        hasSummary: !!cached.summary,
        summaryLength: cached.summary?.length || 0,
        compressionStatus:
          pairCount < 20
            ? `📝 원본 유지 (${pairCount}/20쌍)`
            : `🗜️ 압축됨 (요약 + ${pairCount}쌍 원본)`,
      },
      data: {
        summary: cached.summary
          ? {
              preview:
                cached.summary.length > 200
                  ? cached.summary.substring(0, 200) + '...'
                  : cached.summary,
              fullLength: cached.summary.length,
            }
          : null,
        history: historySummary,
      },
    };
  }

  /**
   * 특정 세션의 캐시 삭제
   */
  @Delete('session/:sessionId')
  @ResponseCode(RC.DEV_REDIS_SESSION_DELETED)
  @ApiOperation({
    summary: '[DEV] 세션 캐시 삭제',
    description: '⚠️ 개발용 API - 특정 세션의 Redis 캐시를 삭제합니다.',
  })
  @ApiParam({ name: 'sessionId', description: '세션 ID' })
  @ApiResponse({ status: 200, description: '삭제 결과' })
  async deleteSessionCache(@Param('sessionId') sessionId: string) {
    const deleted = await this.redisService.deleteSessionCache(sessionId);

    this.logger.warn(`[DEV] Session cache deleted: ${sessionId}`);

    return {
      _dev: '⚠️ 개발용 API',
      sessionId,
      deleted,
      status: deleted ? '✅ Deleted' : '❌ Not found or already deleted',
    };
  }

  /**
   * 특정 세션의 전체 캐시 데이터 (원본) 조회
   */
  @Get('session/:sessionId/raw')
  @ResponseCode(RC.DEV_REDIS_SESSION_RAW_SUCCESS)
  @ApiOperation({
    summary: '[DEV] 세션 캐시 원본 데이터 조회',
    description:
      '⚠️ 개발용 API - 특정 세션의 Redis 캐시 원본 데이터를 조회합니다.',
  })
  @ApiParam({ name: 'sessionId', description: '세션 ID' })
  @ApiResponse({ status: 200, description: '세션 캐시 원본 데이터' })
  async getSessionCacheRaw(@Param('sessionId') sessionId: string) {
    const cached = await this.redisService.getSessionCache(sessionId);

    return {
      _dev: '⚠️ 개발용 API - 원본 데이터',
      sessionId,
      data: cached,
    };
  }
}
