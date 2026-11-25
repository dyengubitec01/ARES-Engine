import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { RedisService } from './redis.service';

// Mock ioredis
jest.mock('ioredis', () => {
  return jest.fn().mockImplementation(() => ({
    get: jest.fn(),
    del: jest.fn(),
    ping: jest.fn(),
    quit: jest.fn(),
    on: jest.fn(),
  }));
});

describe('RedisService', () => {
  let service: RedisService;
  let mockRedisClient: any;

  const mockConfigService = {
    get: jest.fn((key: string) => {
      const config: Record<string, any> = {
        'external.redis.host': 'localhost',
        'external.redis.port': 6379,
      };
      return config[key];
    }),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        RedisService,
        {
          provide: ConfigService,
          useValue: mockConfigService,
        },
      ],
    }).compile();

    service = module.get<RedisService>(RedisService);
    // Get the mock client instance
    mockRedisClient = (service as any).client;
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('getSessionSummary', () => {
    it('should return cached summary for valid sessionId', async () => {
      // GIVEN: Redis has cached summary
      const sessionId = 'session-123';
      const cachedSummary = '이전 대화 요약본입니다.';
      mockRedisClient.get.mockResolvedValue(cachedSummary);

      // WHEN: Getting session summary
      const result = await service.getSessionSummary(sessionId);

      // THEN: Returns cached summary
      expect(result).toBe(cachedSummary);
      expect(mockRedisClient.get).toHaveBeenCalledWith(
        `session:${sessionId}:summary`,
      );
    });

    it('should return null when no cached summary exists', async () => {
      // GIVEN: Redis has no cached summary
      const sessionId = 'session-new';
      mockRedisClient.get.mockResolvedValue(null);

      // WHEN: Getting session summary
      const result = await service.getSessionSummary(sessionId);

      // THEN: Returns null
      expect(result).toBeNull();
      expect(mockRedisClient.get).toHaveBeenCalledWith(
        `session:${sessionId}:summary`,
      );
    });

    it('should return null on Redis error', async () => {
      // GIVEN: Redis throws error
      const sessionId = 'session-123';
      mockRedisClient.get.mockRejectedValue(new Error('Connection refused'));

      // WHEN: Getting session summary
      const result = await service.getSessionSummary(sessionId);

      // THEN: Returns null (graceful degradation)
      expect(result).toBeNull();
    });
  });

  describe('deleteSessionSummary', () => {
    it('should delete cached summary and return true', async () => {
      // GIVEN: Redis key exists
      const sessionId = 'session-123';
      mockRedisClient.del.mockResolvedValue(1);

      // WHEN: Deleting session summary
      const result = await service.deleteSessionSummary(sessionId);

      // THEN: Returns true
      expect(result).toBe(true);
      expect(mockRedisClient.del).toHaveBeenCalledWith(
        `session:${sessionId}:summary`,
      );
    });

    it('should return false when key does not exist', async () => {
      // GIVEN: Redis key does not exist
      const sessionId = 'session-nonexistent';
      mockRedisClient.del.mockResolvedValue(0);

      // WHEN: Deleting session summary
      const result = await service.deleteSessionSummary(sessionId);

      // THEN: Returns false
      expect(result).toBe(false);
    });

    it('should return false on Redis error', async () => {
      // GIVEN: Redis throws error
      const sessionId = 'session-123';
      mockRedisClient.del.mockRejectedValue(new Error('Connection refused'));

      // WHEN: Deleting session summary
      const result = await service.deleteSessionSummary(sessionId);

      // THEN: Returns false (graceful degradation)
      expect(result).toBe(false);
    });
  });

  describe('healthCheck', () => {
    it('should return true when Redis responds PONG', async () => {
      // GIVEN: Redis is healthy
      mockRedisClient.ping.mockResolvedValue('PONG');

      // WHEN: Checking health
      const result = await service.healthCheck();

      // THEN: Returns true
      expect(result).toBe(true);
    });

    it('should return false when Redis fails', async () => {
      // GIVEN: Redis is unhealthy
      mockRedisClient.ping.mockRejectedValue(new Error('Connection refused'));

      // WHEN: Checking health
      const result = await service.healthCheck();

      // THEN: Returns false
      expect(result).toBe(false);
    });
  });
});
