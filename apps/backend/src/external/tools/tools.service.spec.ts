import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { ToolsService } from './tools.service';

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

describe('ToolsService', () => {
  let service: ToolsService;

  const mockConfigService = {
    get: jest.fn((key: string) => {
      const config: Record<string, any> = {
        'external.tools.url': 'http://tools.example.com',
      };
      return config[key];
    }),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ToolsService,
        {
          provide: ConfigService,
          useValue: mockConfigService,
        },
      ],
    }).compile();

    service = module.get<ToolsService>(ToolsService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('compressSummary', () => {
    it('should return summary from Tools API', async () => {
      // GIVEN: Valid conversations and Tools API returns summary
      const sessionId = 'session-123';
      const conversations = [{ question: '안녕', answer: '안녕하세요!' }];
      const expectedSummary = 'Tools가 생성한 요약본입니다.';

      mockFetch.mockResolvedValue({
        ok: true,
        json: async () => ({ summary: expectedSummary }),
      });

      // WHEN: Calling compressSummary
      const result = await service.compressSummary(
        sessionId,
        null,
        conversations,
      );

      // THEN: Returns summary from API
      expect(result).toBe(expectedSummary);
    });

    it('should return null when Tools API returns error status', async () => {
      // GIVEN: Tools API returns error
      const sessionId = 'session-123';
      const conversations = [{ question: '안녕', answer: '안녕하세요!' }];

      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
      });

      // WHEN: Calling compressSummary
      const result = await service.compressSummary(
        sessionId,
        null,
        conversations,
      );

      // THEN: Returns null
      expect(result).toBeNull();
    });

    it('should return null when Tools API throws error', async () => {
      // GIVEN: Network error
      const sessionId = 'session-123';
      const conversations = [{ question: '안녕', answer: '안녕하세요!' }];

      mockFetch.mockRejectedValue(new Error('Network error'));

      // WHEN: Calling compressSummary
      const result = await service.compressSummary(
        sessionId,
        null,
        conversations,
      );

      // THEN: Returns null (graceful degradation)
      expect(result).toBeNull();
    });
  });

  describe('healthCheck', () => {
    it('should return true when Tools API is healthy', async () => {
      // GIVEN: Tools API is healthy
      mockFetch.mockResolvedValue({ ok: true });

      // WHEN: Checking health
      const result = await service.healthCheck();

      // THEN: Returns true
      expect(result).toBe(true);
      expect(mockFetch).toHaveBeenCalledWith('http://tools.example.com/health');
    });

    it('should return false when Tools API is unhealthy', async () => {
      // GIVEN: Tools API is unhealthy
      mockFetch.mockResolvedValue({ ok: false });

      // WHEN: Checking health
      const result = await service.healthCheck();

      // THEN: Returns false
      expect(result).toBe(false);
    });

    it('should return false when Tools API throws error', async () => {
      // GIVEN: Network error
      mockFetch.mockRejectedValue(new Error('Network error'));

      // WHEN: Checking health
      const result = await service.healthCheck();

      // THEN: Returns false
      expect(result).toBe(false);
    });
  });
});
