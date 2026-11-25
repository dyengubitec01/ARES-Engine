import { Module } from '@nestjs/common';
import { HealthController } from './health.controller';
import { RedisModule } from '../external/redis/redis.module';
import { MinioModule } from '../external/minio/minio.module';
import { ChatbotModule } from '../external/chatbot/chatbot.module';
import { EmbeddingModule } from '../external/embedding/embedding.module';
import { QdrantModule } from '../external/qdrant/qdrant.module';

@Module({
  imports: [
    RedisModule,
    MinioModule,
    ChatbotModule,
    EmbeddingModule,
    QdrantModule,
  ],
  controllers: [HealthController],
})
export class HealthModule {}
