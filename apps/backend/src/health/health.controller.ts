import { Controller, Get, Logger } from '@nestjs/common';
import { InjectDataSource } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';
import { Public } from '../auth/decorators/public.decorator';
import { RedisService } from '../external/redis/redis.service';
import { MinioService } from '../external/minio/minio.service';
import { ChatbotService } from '../external/chatbot/chatbot.service';
import { EmbeddingService } from '../external/embedding/embedding.service';
import { QdrantService } from '../external/qdrant/qdrant.service';
import { ResponseCode } from '../common/decorators/response-code.decorator';
import { ResponseCode as RC } from '../common/constants/response-codes';

interface ServiceHealth {
  status: 'up' | 'down';
  responseTime?: number;
  error?: string;
}

interface HealthResponse {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  services: {
    database: ServiceHealth;
    redis: ServiceHealth;
    minio: ServiceHealth;
    chatbot: ServiceHealth;
    embedding: ServiceHealth;
    qdrant: ServiceHealth;
  };
}

@Controller('health')
export class HealthController {
  private readonly logger = new Logger(HealthController.name);

  constructor(
    @InjectDataSource() private dataSource: DataSource,
    private redisService: RedisService,
    private minioService: MinioService,
    private chatbotService: ChatbotService,
    private embeddingService: EmbeddingService,
    private qdrantService: QdrantService,
  ) {}

  @Public()
  @Get()
  @ResponseCode(RC.HEALTH_CHECK_SUCCESS)
  async check(): Promise<HealthResponse> {
    const startTime = Date.now();

    const [database, redis, minio, chatbot, embedding, qdrant] =
      await Promise.all([
        this.checkDatabase(),
        this.checkRedis(),
        this.checkMinio(),
        this.checkChatbot(),
        this.checkEmbedding(),
        this.checkQdrant(),
      ]);

    const services = { database, redis, minio, chatbot, embedding, qdrant };

    // 전체 상태 판단
    const allUp = Object.values(services).every((s) => s.status === 'up');
    const allDown = Object.values(services).every((s) => s.status === 'down');
    const criticalDown =
      services.database.status === 'down' || services.minio.status === 'down';

    let status: 'healthy' | 'degraded' | 'unhealthy';
    if (allUp) {
      status = 'healthy';
    } else if (allDown || criticalDown) {
      status = 'unhealthy';
    } else {
      status = 'degraded';
    }

    const response: HealthResponse = {
      status,
      timestamp: new Date().toISOString(),
      services,
    };

    // 상태별 로깅
    if (status === 'unhealthy') {
      this.logger.error(`Health check: ${status}`, JSON.stringify(services));
    } else if (status === 'degraded') {
      this.logger.warn(`Health check: ${status}`, JSON.stringify(services));
    } else {
      this.logger.debug(
        `Health check: ${status} (${Date.now() - startTime}ms)`,
      );
    }

    return response;
  }

  @Public()
  @Get('live')
  async liveness(): Promise<{ status: string }> {
    return { status: 'ok' };
  }

  @Public()
  @Get('ready')
  async readiness(): Promise<{ status: string; database: boolean }> {
    const dbHealth = await this.checkDatabase();
    return {
      status: dbHealth.status === 'up' ? 'ok' : 'not ready',
      database: dbHealth.status === 'up',
    };
  }

  private async checkDatabase(): Promise<ServiceHealth> {
    const start = Date.now();
    try {
      await this.dataSource.query('SELECT 1');
      return {
        status: 'up',
        responseTime: Date.now() - start,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Database health check failed: ${message}`);
      return {
        status: 'down',
        responseTime: Date.now() - start,
        error: message,
      };
    }
  }

  private async checkRedis(): Promise<ServiceHealth> {
    const start = Date.now();
    try {
      const isHealthy = await this.redisService.healthCheck();
      return {
        status: isHealthy ? 'up' : 'down',
        responseTime: Date.now() - start,
        error: isHealthy ? undefined : 'Redis not available or disabled',
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      return {
        status: 'down',
        responseTime: Date.now() - start,
        error: message,
      };
    }
  }

  private async checkMinio(): Promise<ServiceHealth> {
    const start = Date.now();
    try {
      const isHealthy = await this.minioService.healthCheck();
      return {
        status: isHealthy ? 'up' : 'down',
        responseTime: Date.now() - start,
        error: isHealthy ? undefined : 'MinIO not reachable',
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      return {
        status: 'down',
        responseTime: Date.now() - start,
        error: message,
      };
    }
  }

  private async checkChatbot(): Promise<ServiceHealth> {
    const start = Date.now();
    try {
      const isHealthy = await this.chatbotService.healthCheck();
      return {
        status: isHealthy ? 'up' : 'down',
        responseTime: Date.now() - start,
        error: isHealthy ? undefined : 'Chatbot service not reachable',
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      return {
        status: 'down',
        responseTime: Date.now() - start,
        error: message,
      };
    }
  }

  private async checkEmbedding(): Promise<ServiceHealth> {
    const start = Date.now();
    try {
      const result = await this.embeddingService.checkHealth();
      return {
        status: result.status === 'healthy' ? 'up' : 'down',
        responseTime: result.responseTime ?? Date.now() - start,
        error: result.status === 'healthy' ? undefined : result.error,
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      return {
        status: 'down',
        responseTime: Date.now() - start,
        error: message,
      };
    }
  }

  private async checkQdrant(): Promise<ServiceHealth> {
    const start = Date.now();
    try {
      const isHealthy = await this.qdrantService.healthCheck();
      return {
        status: isHealthy ? 'up' : 'down',
        responseTime: Date.now() - start,
        error: isHealthy ? undefined : 'Qdrant not available or disabled',
      };
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      return {
        status: 'down',
        responseTime: Date.now() - start,
        error: message,
      };
    }
  }
}
