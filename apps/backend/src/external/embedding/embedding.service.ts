import {
  Injectable,
  Logger,
  ServiceUnavailableException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

/**
 * New embedding request format for Embedding Request Server
 * POST /embedding-requests
 */
export interface EmbeddingRequest {
  docContentId: string;
  requestedBy: string;
  authDeptId: string;
  minioBucket: string;
  minioObjectKey: string;
  embeddingProfile: string;
  extractionVersion: string;
}

export interface ReEmbeddingRequest {
  docContentId: string;
  requestedBy: string;
  embeddingProfile: string;
}

export interface EmbeddingResponse {
  success: boolean;
  message?: string;
}

export interface EmbeddingHealthResponse {
  status: 'healthy' | 'unhealthy';
  url: string;
  responseTime?: number;
  error?: string;
}

@Injectable()
export class EmbeddingService {
  private readonly logger = new Logger(EmbeddingService.name);
  private readonly baseUrl: string;
  private readonly chunkingProfile: string;
  private readonly embeddingProfile: string;

  constructor(private configService: ConfigService) {
    this.baseUrl =
      this.configService.get<string>('external.embedding.url') || '';
    this.chunkingProfile =
      this.configService.get<string>('external.embedding.chunkingProfile') ||
      'default_v1';
    this.embeddingProfile =
      this.configService.get<string>('external.embedding.embeddingProfile') ||
      'bge_m3_v1';
  }

  /**
   * Request embedding processing for a document
   * POST /embedding-requests (new endpoint)
   */
  async requestEmbedding(
    request: EmbeddingRequest,
  ): Promise<EmbeddingResponse> {
    const url = `${this.baseUrl}/embedding-requests`;

    // Build payload with snake_case for Python server
    const payload = {
      doc_content_id: request.docContentId,
      requested_by: request.requestedBy,
      auth_dept_id: request.authDeptId,
      minio_bucket: request.minioBucket,
      minio_object_key: request.minioObjectKey,
      embedding_profile: request.embeddingProfile,
      extraction_version: request.extractionVersion,
      enable_ocr: true,
    };

    try {
      this.logger.debug(
        `Requesting embedding for content ${request.docContentId}`,
      );
      this.logger.debug(`Payload: ${JSON.stringify(payload)}`);

      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.logger.error(
          `Embedding server returned ${response.status}: ${errorText}`,
        );
        throw new ServiceUnavailableException(
          `Embedding server error ${response.status}: ${errorText}`,
        );
      }

      this.logger.log(
        `Embedding request sent for content ${request.docContentId}`,
      );

      return { success: true };
    } catch (error) {
      if (error instanceof ServiceUnavailableException) {
        throw error;
      }

      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to request embedding: ${message}`);
      throw new ServiceUnavailableException(
        `Failed to connect to embedding server: ${message}`,
      );
    }
  }

  /**
   * Get default chunking profile
   */
  getChunkingProfile(): string {
    return this.chunkingProfile;
  }

  /**
   * Get default embedding profile
   */
  getEmbeddingProfile(): string {
    return this.embeddingProfile;
  }

  /**
   * Request re-embedding for a document (COMPLETED/FAILED → re-embed)
   * POST /re-embedding-requests
   */
  async requestReEmbedding(
    request: ReEmbeddingRequest,
  ): Promise<EmbeddingResponse> {
    const url = `${this.baseUrl}/re-embedding-requests`;

    const payload = {
      doc_content_id: request.docContentId,
      requested_by: request.requestedBy,
      embedding_profile: request.embeddingProfile,
      enable_ocr: true,
    };

    try {
      this.logger.debug(
        `Requesting re-embedding for content ${request.docContentId}`,
      );

      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorText = await response.text();
        this.logger.error(
          `Embedding server returned ${response.status}: ${errorText}`,
        );
        throw new ServiceUnavailableException(
          `Embedding server error ${response.status}: ${errorText}`,
        );
      }

      this.logger.log(
        `Re-embedding request sent for content ${request.docContentId}`,
      );

      return { success: true };
    } catch (error) {
      if (error instanceof ServiceUnavailableException) {
        throw error;
      }

      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to request re-embedding: ${message}`);
      throw new ServiceUnavailableException(
        `Failed to connect to embedding server: ${message}`,
      );
    }
  }

  /**
   * Check embedding server health
   * GET /health
   */
  async checkHealth(): Promise<EmbeddingHealthResponse> {
    const url = `${this.baseUrl}/health`;
    const startTime = Date.now();

    try {
      const response = await fetch(url, {
        method: 'GET',
        signal: AbortSignal.timeout(5000), // 5초 타임아웃
      });

      const responseTime = Date.now() - startTime;

      if (response.ok) {
        this.logger.debug(
          `Embedding server health check OK (${responseTime}ms)`,
        );
        return {
          status: 'healthy',
          url: this.baseUrl,
          responseTime,
        };
      }

      const errorText = await response.text();
      this.logger.warn(
        `Embedding server health check failed: ${response.status} - ${errorText}`,
      );
      return {
        status: 'unhealthy',
        url: this.baseUrl,
        responseTime,
        error: `HTTP ${response.status}: ${errorText}`,
      };
    } catch (error) {
      const responseTime = Date.now() - startTime;
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Embedding server health check error: ${message}`);
      return {
        status: 'unhealthy',
        url: this.baseUrl,
        responseTime,
        error: message,
      };
    }
  }
}
