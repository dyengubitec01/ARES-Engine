import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { APP_FILTER, APP_GUARD, APP_INTERCEPTOR } from '@nestjs/core';

import { LoggerModule } from 'nestjs-pino';
import {
  databaseConfig,
  authConfig,
  externalConfig,
  departmentConfig,
} from './config';
import loggerConfig, { createLoggerConfig } from './config/logger.config';
import { LogFileRotator } from './config/log-file-rotator';
import { GlobalExceptionFilter } from './common/filters/http-exception.filter';
import { ResponseInterceptor } from './common/interceptors/response.interceptor';
import {
  AccessLogInterceptor,
  LOG_FILE_ROTATOR,
} from './common/interceptors/access-log.interceptor';
import { ThrottlerModule, ThrottlerGuard } from '@nestjs/throttler';
import { ScheduleModule } from '@nestjs/schedule';
import { JwtAuthGuard } from './auth/guards/jwt-auth.guard';
import { AuthoritiesGuard } from './auth/guards/authorities.guard';

import { CommonModule } from './common/common.module';
import { AuthModule } from './auth/auth.module';
import { AdminModule } from './admin/admin.module';
import { ChatModule } from './chat/chat.module';
import { ChatbotModule } from './external/chatbot/chatbot.module';
import { MinioModule } from './external/minio/minio.module';
import { KafkaModule } from './external/kafka/kafka.module';
import { RedisModule } from './external/redis/redis.module';
import { DocumentModule } from './document/document.module';
import { AlarmModule } from './alarm/alarm.module';
import { BoardModule } from './board/board.module';
import { HealthModule } from './health/health.module';

// 인프라 엔티티 (Embedding Worker 가 쓰는 테이블 — 우리 측 forFeature 미등록이라 명시 유지)
import { VecQdrantCollection } from './storage/entities/vec-qdrant-collection.entity';
import { RagEmbeddingJob } from './rag/entities/rag-embedding-job.entity';
import { RagChunk } from './rag/entities/rag-chunk.entity';
import { RagEmbeddingsIndex } from './rag/entities/rag-embeddings-index.entity';
import { RagUpsertHistory } from './rag/entities/rag-upsert-history.entity';
import { RagProcessingStats } from './rag/entities/rag-processing-stats.entity';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      envFilePath: `.env.${process.env.NODE_ENV || 'development'}`,
      load: [
        databaseConfig,
        authConfig,
        externalConfig,
        loggerConfig,
        departmentConfig,
      ],
    }),
    ScheduleModule.forRoot(),
    LoggerModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => {
        const isProduction =
          configService.get<boolean>('logger.isProduction') ?? false;
        const logLevel =
          configService.get<string>('logger.logLevel') ?? 'debug';
        const logDir = configService.get<string>('logger.logDir') ?? './logs';
        return createLoggerConfig(isProduction, logLevel, logDir);
      },
    }),
    TypeOrmModule.forRootAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        type: 'postgres',
        host: configService.get<string>('database.host'),
        port: configService.get<number>('database.port'),
        username: configService.get<string>('database.username'),
        password: configService.get<string>('database.password'),
        database: configService.get<string>('database.database'),
        schema: configService.get<string>('database.schema'),
        // Connection retry configuration
        retryAttempts: 10, // 최대 10회 재시도
        retryDelay: 3000, // 재시도 간격 3초
        // Connection pool configuration
        extra: {
          max: 20, // 최대 커넥션 수
          connectionTimeoutMillis: 10000, // 커넥션 타임아웃 10초
          idleTimeoutMillis: 30000, // 유휴 커넥션 타임아웃 30초
        },
        // 도메인 엔티티는 모듈별 forFeature 등록분을 자동 수집 (autoLoadEntities)
        // entities[] 는 forFeature 미등록인 인프라 엔티티(Embedding Worker 가 쓰는 테이블)만 명시
        autoLoadEntities: true,
        entities: [
          VecQdrantCollection,
          RagEmbeddingJob,
          RagChunk,
          RagEmbeddingsIndex,
          RagUpsertHistory,
          RagProcessingStats,
        ],
        synchronize: false,
        logging: process.env.NODE_ENV === 'development',
      }),
      inject: [ConfigService],
    }),
    ThrottlerModule.forRoot([
      {
        ttl: 60000,
        limit: 1000,
      },
    ]),
    CommonModule,
    AuthModule,
    AdminModule,
    ChatModule,
    ChatbotModule,
    MinioModule,
    KafkaModule,
    RedisModule,
    DocumentModule,
    AlarmModule,
    BoardModule,
    HealthModule,
  ],
  providers: [
    {
      provide: LOG_FILE_ROTATOR,
      useFactory: (configService: ConfigService) => {
        const logDir = configService.get<string>('logger.logDir') ?? './logs';
        return new LogFileRotator(logDir);
      },
      inject: [ConfigService],
    },
    {
      provide: APP_FILTER,
      useClass: GlobalExceptionFilter,
    },
    {
      provide: APP_INTERCEPTOR,
      useClass: AccessLogInterceptor,
    },
    {
      provide: APP_INTERCEPTOR,
      useClass: ResponseInterceptor,
    },
    // TODO: 인증 임시 비활성화 - Azure AD 로그인 대신 "홍길동" 목 로그인 사용 중
    {
      provide: APP_GUARD,
      useClass: ThrottlerGuard,
    },
    {
      provide: APP_GUARD,
      useClass: JwtAuthGuard,
    },
    {
      provide: APP_GUARD,
      useClass: AuthoritiesGuard,
    },
  ],
})
export class AppModule {}
