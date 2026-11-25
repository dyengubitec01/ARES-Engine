import { Controller, Get } from '@nestjs/common';
import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
import { Public } from '../../auth/decorators/public.decorator';
import { EmbeddingService, EmbeddingHealthResponse } from './embedding.service';

@ApiTags('Health')
@Controller('embedding')
export class EmbeddingController {
  constructor(private readonly embeddingService: EmbeddingService) {}

  @Get('health')
  @Public()
  @ApiOperation({ summary: '임베딩 서버 헬스체크' })
  @ApiResponse({
    status: 200,
    description: '임베딩 서버 상태',
    schema: {
      type: 'object',
      properties: {
        status: { type: 'string', enum: ['healthy', 'unhealthy'] },
        url: { type: 'string' },
        responseTime: { type: 'number', description: '응답 시간 (ms)' },
        error: { type: 'string', nullable: true },
      },
    },
  })
  async checkHealth(): Promise<EmbeddingHealthResponse> {
    return this.embeddingService.checkHealth();
  }
}
