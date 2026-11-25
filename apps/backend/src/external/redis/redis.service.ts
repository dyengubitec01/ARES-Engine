import {
  Injectable,
  Logger,
  OnModuleInit,
  OnModuleDestroy,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';

@Injectable()
export class RedisService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RedisService.name);
  private client: Redis | null = null;
  private readonly enabled: boolean;
  private readonly keyPrefix: string;

  constructor(private configService: ConfigService) {
    const host = this.configService.get<string>('external.redis.host');

    // 키 prefix 설정: <env>:<domain>:<app>
    const env = process.env.NODE_ENV === 'production' ? 'prod' : 'dev';
    this.keyPrefix = `${env}:rag:backend`;

    // Redis 설정이 없으면 비활성화
    if (!host) {
      this.enabled = false;
      this.logger.warn('Redis not configured - running in disabled mode');
      return;
    }

    this.enabled = true;
    const port = this.configService.get<number>('external.redis.port');
    const password = this.configService.get<string>('external.redis.password');
    const db = this.configService.get<number>('external.redis.db');

    this.client = new Redis({
      host,
      port: port || 6379,
      password: password || undefined,
      db: db || 0,
      retryStrategy: (times) => {
        const delay = Math.min(times * 100, 3000);
        return delay;
      },
      maxRetriesPerRequest: 3,
    });

    this.client.on('error', (error) => {
      this.logger.error(`Redis connection error: ${error.message}`);
    });

    this.client.on('connect', () => {
      this.logger.log(`Redis connected to ${host}:${port} (db: ${db || 0})`);
    });
  }

  async onModuleInit() {
    if (!this.enabled || !this.client) {
      return;
    }

    try {
      await this.client.ping();
      this.logger.log('Redis connection verified');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.warn(`Redis connection not available: ${message}`);
    }
  }

  async onModuleDestroy() {
    if (this.client) {
      await this.client.quit();
      this.logger.log('Redis connection closed');
    }
  }

  /**
   * Build Redis key with convention
   * Pattern: <env>:<domain>:<app>:<type>:<name>:<id>
   * Example: dev:rag:backend:cache:chat:summary:{sessionId}
   */
  private buildKey(type: string, name: string, id: string): string {
    return `${this.keyPrefix}:${type}:${name}:${id}`;
  }

  /**
   * Get session summary from Redis
   * Key pattern: {env}:rag:backend:cache:chat:summary:{sessionId}
   */
  async getSessionSummary(sessionId: string): Promise<string | null> {
    if (!this.enabled || !this.client) {
      return null;
    }

    const key = this.buildKey('cache', 'chat:summary', sessionId);
    try {
      return await this.client.get(key);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to get session summary: ${message}`);
      return null;
    }
  }

  /**
   * Set session summary to Redis with TTL (AC4: Story 2.13)
   * Key pattern: {env}:rag:backend:cache:chat:summary:{sessionId}
   * Default TTL: 1 hour (3600 seconds)
   */
  async setSessionSummary(
    sessionId: string,
    summary: string,
    ttlSeconds?: number,
  ): Promise<boolean> {
    if (!this.enabled || !this.client) {
      return false;
    }

    const key = this.buildKey('cache', 'chat:summary', sessionId);
    const ttl = ttlSeconds || 3600; // Default 1 hour

    try {
      await this.client.setex(key, ttl, summary);
      this.logger.debug(`Set Redis key: ${key} with TTL ${ttl}s`);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to set session summary: ${message}`);
      return false;
    }
  }

  /**
   * Delete session summary from Redis
   * Key pattern: {env}:rag:backend:cache:chat:summary:{sessionId}
   */
  async deleteSessionSummary(sessionId: string): Promise<boolean> {
    if (!this.enabled || !this.client) {
      return false;
    }

    const key = this.buildKey('cache', 'chat:summary', sessionId);
    try {
      const result = await this.client.del(key);
      if (result > 0) {
        this.logger.debug(`Deleted Redis key: ${key}`);
      }
      return result > 0;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to delete session summary: ${message}`);
      return false;
    }
  }

  // ============================================================
  // Session History Cache (히스토리 캐싱 - DB 조회 최소화)
  // ============================================================

  /**
   * Get cached session data (summary + history)
   * Key pattern: {env}:rag:backend:cache:chat:session:{sessionId}
   */
  async getSessionCache(sessionId: string): Promise<{
    summary: string | null;
    history: Array<{ type: 'Q' | 'A'; content: string; chatTurn: number }>;
  } | null> {
    if (!this.enabled || !this.client) {
      return null;
    }

    const key = this.buildKey('cache', 'chat:session', sessionId);
    try {
      const data = await this.client.get(key);
      if (!data) {
        return null;
      }
      return JSON.parse(data);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to get session cache: ${message}`);
      return null;
    }
  }

  /**
   * Set session cache (summary + history)
   * Key pattern: {env}:rag:backend:cache:chat:session:{sessionId}
   * Default TTL: 1 hour (3600 seconds)
   */
  async setSessionCache(
    sessionId: string,
    data: {
      summary: string | null;
      history: Array<{ type: 'Q' | 'A'; content: string; chatTurn: number }>;
    },
    ttlSeconds?: number,
  ): Promise<boolean> {
    if (!this.enabled || !this.client) {
      return false;
    }

    const key = this.buildKey('cache', 'chat:session', sessionId);
    const ttl = ttlSeconds || 3600;

    try {
      await this.client.setex(key, ttl, JSON.stringify(data));
      this.logger.debug(
        `Set session cache: ${key} (summary: ${data.summary ? 'yes' : 'no'}, history: ${data.history.length} items)`,
      );
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to set session cache: ${message}`);
      return false;
    }
  }

  /**
   * Delete session cache
   * Key pattern: {env}:rag:backend:cache:chat:session:{sessionId}
   */
  async deleteSessionCache(sessionId: string): Promise<boolean> {
    if (!this.enabled || !this.client) {
      return false;
    }

    const key = this.buildKey('cache', 'chat:session', sessionId);
    try {
      const result = await this.client.del(key);
      if (result > 0) {
        this.logger.debug(`Deleted session cache: ${key}`);
      }
      return result > 0;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to delete session cache: ${message}`);
      return false;
    }
  }

  // ============================================================
  // Token Refresh Flag (관리자 권한 변경 시 JWT 갱신 트리거)
  // ============================================================

  /**
   * 토큰 갱신 플래그 설정
   * Key pattern: {env}:rag:backend:flag:token-refresh:{userId}
   * TTL: 900초 (15분, access token 만료 주기와 동일)
   */
  async setTokenRefreshFlag(userId: string): Promise<boolean> {
    if (!this.enabled || !this.client) {
      return false;
    }

    const key = this.buildKey('flag', 'token-refresh', userId);
    try {
      await this.client.setex(key, 900, '1');
      this.logger.debug(`Token refresh flag set for user: ${userId}`);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to set token refresh flag: ${message}`);
      return false;
    }
  }

  /**
   * 토큰 갱신 플래그 확인
   */
  async getTokenRefreshFlag(userId: string): Promise<boolean> {
    if (!this.enabled || !this.client) {
      return false;
    }

    const key = this.buildKey('flag', 'token-refresh', userId);
    try {
      const result = await this.client.get(key);
      return result !== null;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to get token refresh flag: ${message}`);
      return false;
    }
  }

  /**
   * 토큰 갱신 플래그 삭제
   */
  async deleteTokenRefreshFlag(userId: string): Promise<boolean> {
    if (!this.enabled || !this.client) {
      return false;
    }

    const key = this.buildKey('flag', 'token-refresh', userId);
    try {
      await this.client.del(key);
      this.logger.debug(`Token refresh flag deleted for user: ${userId}`);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to delete token refresh flag: ${message}`);
      return false;
    }
  }

  /**
   * Check Redis connection health
   */
  async healthCheck(): Promise<boolean> {
    if (!this.enabled || !this.client) {
      return false;
    }

    try {
      const result = await this.client.ping();
      return result === 'PONG';
    } catch {
      return false;
    }
  }

  // ============================================================
  // DEV: 전체 키 조회 (디버깅용)
  // ============================================================

  /**
   * [DEV] 모든 키 조회
   * Pattern: {env}:rag:backend:*
   */
  async getAllKeys(): Promise<string[]> {
    if (!this.enabled || !this.client) {
      return [];
    }

    try {
      const pattern = `${this.keyPrefix}:*`;
      return await this.client.keys(pattern);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to get all keys: ${message}`);
      return [];
    }
  }

  /**
   * [DEV] 키로 값 조회 (원본)
   */
  async getByKey(key: string): Promise<string | null> {
    if (!this.enabled || !this.client) {
      return null;
    }

    try {
      return await this.client.get(key);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to get key ${key}: ${message}`);
      return null;
    }
  }

  /**
   * [DEV] 키의 TTL 조회
   */
  async getTTL(key: string): Promise<number> {
    if (!this.enabled || !this.client) {
      return -2;
    }

    try {
      return await this.client.ttl(key);
    } catch {
      return -2;
    }
  }
}
