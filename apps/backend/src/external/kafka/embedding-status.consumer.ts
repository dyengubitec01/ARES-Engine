import {
  Injectable,
  Logger,
  OnModuleInit,
  OnModuleDestroy,
  Inject,
  forwardRef,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Kafka, Consumer, EachMessagePayload } from 'kafkajs';
import { EmbeddingStatusGateway } from '../../document/services/embedding-status.gateway';
import { DocDocument } from '../../document/entities/doc-document.entity';
import { AuthUsersAlarm } from '../../auth/entities/auth-users-alarm.entity';

/**
 * Kafka 메시지 형식
 * 임베딩 서버가 DB 업데이트를 직접 수행하고 Kafka로 상태를 발행
 * 백엔드는 이 메시지를 받아 SSE로 클라이언트에게 전달만 함
 */
export interface EmbeddingStatusMessage {
  documentId: string;
  versionId: string;
  status: string;
  message?: string;
  metadata?: Record<string, unknown>;
  timestamp?: string;
}

/**
 * Valid status values from embedding server
 */
const VALID_STATUSES = [
  'parsing',
  'chunking',
  'embedding',
  'upserting',
  'completed',
  'failed',
];

@Injectable()
export class EmbeddingStatusConsumer implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(EmbeddingStatusConsumer.name);
  private consumer: Consumer | null = null;
  private readonly failureThreshold = 10;
  private failureCount = 0;
  private lastFailureTime: Date | null = null;
  private readonly failureWindowMs = 60000; // 1분 윈도우

  constructor(
    private readonly configService: ConfigService,
    @Inject(forwardRef(() => EmbeddingStatusGateway))
    private readonly embeddingStatusGateway: EmbeddingStatusGateway,
    @InjectRepository(DocDocument)
    private readonly documentRepository: Repository<DocDocument>,
    @InjectRepository(AuthUsersAlarm)
    private readonly alarmRepository: Repository<AuthUsersAlarm>,
  ) {}

  async onModuleInit() {
    const enabled = this.configService.get<string>('KAFKA_ENABLED') !== 'false';
    if (!enabled) {
      this.logger.log('Kafka consumer disabled (KAFKA_ENABLED=false)');
      return;
    }

    const brokers = (
      this.configService.get<string>('KAFKA_BROKERS') || 'localhost:9092'
    ).split(',');
    const clientId =
      this.configService.get<string>('KAFKA_CLIENT_ID') || 'backend';
    const groupId =
      this.configService.get<string>('KAFKA_CONSUMER_GROUP') ||
      'rag-backend-status';
    const topic =
      this.configService.get<string>('KAFKA_STATUS_TOPIC') ||
      'dev.embeddings.status';
    const username = this.configService.get<string>('KAFKA_SASL_USERNAME');
    const password =
      this.configService.get<string>('KAFKA_SASL_PASSWORD') || '';

    const kafka = new Kafka({
      clientId,
      brokers,
      ssl: false,
      sasl: username
        ? { mechanism: 'scram-sha-256' as const, username, password }
        : undefined,
      retry: { initialRetryTime: 3000, retries: 10 },
    });

    this.consumer = kafka.consumer({ groupId });

    try {
      await this.consumer.connect();
      await this.consumer.subscribe({ topic, fromBeginning: false });
      await this.consumer.run({
        eachMessage: async (payload: EachMessagePayload) => {
          await this.onMessage(payload);
        },
      });
      this.logger.log(
        `Kafka consumer connected: topic=${topic}, groupId=${groupId}`,
      );
    } catch (error) {
      const err = error as Error;
      this.logger.error(`Kafka consumer failed to start: ${err.message}`);
    }
  }

  async onModuleDestroy() {
    if (this.consumer) {
      await this.consumer.disconnect();
      this.logger.log('Kafka consumer disconnected');
    }
  }

  private async onMessage({ topic, partition, message }: EachMessagePayload) {
    this.logger.debug(
      `Received message from topic=${topic}, partition=${partition}, offset=${message.offset}`,
    );

    try {
      const value = message.value?.toString();
      if (!value) return;

      const parsed: EmbeddingStatusMessage = JSON.parse(value);
      await this.handleStatusEvent(parsed);
      this.failureCount = 0;
    } catch (error) {
      const err = error as Error;
      this.logger.error(`Failed to handle message: ${err.message}`, err.stack);

      const now = new Date();
      if (
        this.lastFailureTime &&
        now.getTime() - this.lastFailureTime.getTime() > this.failureWindowMs
      ) {
        this.failureCount = 0;
      }

      this.failureCount++;
      this.lastFailureTime = now;

      if (this.failureCount >= this.failureThreshold) {
        this.logger.warn(
          `⚠️ Kafka 메시지 처리 실패 ${this.failureCount}회 (1분 내). 시스템 점검 필요!`,
        );
      }
    }
  }

  /**
   * Handle embedding status event from Kafka
   * 임베딩 서버가 DB 업데이트를 직접 수행하므로 백엔드는 SSE 전달만 담당
   */
  async handleStatusEvent(message: EmbeddingStatusMessage): Promise<void> {
    this.logger.log(
      `Received status event: documentId=${message.documentId}, versionId=${message.versionId}, status=${message.status}`,
    );

    // Validate message
    if (!message.documentId || !message.versionId || !message.status) {
      this.logger.warn(
        'Invalid message: missing documentId, versionId or status',
      );
      return;
    }

    // Validate status
    const normalizedStatus = message.status.toLowerCase();
    if (!VALID_STATUSES.includes(normalizedStatus)) {
      this.logger.warn(`Unknown status: ${message.status}`);
      return;
    }

    // Story 4.10 AC2: SSE로 구독 중인 클라이언트에게 이벤트 전송
    this.embeddingStatusGateway.emit({
      documentId: message.documentId,
      versionId: message.versionId,
      status: normalizedStatus,
      message: message.message,
      metadata: message.metadata,
      timestamp: message.timestamp || new Date().toISOString(),
    });

    this.logger.log(
      `SSE event emitted: documentId=${message.documentId}, versionId=${message.versionId}, status=${normalizedStatus}`,
    );

    // completed/failed 시 알람 생성 (백그라운드)
    if (normalizedStatus === 'completed' || normalizedStatus === 'failed') {
      this.createAlarm(
        message.documentId,
        normalizedStatus,
        message.message,
      ).catch((e: Error) => {
        this.logger.warn(`Alarm creation failed: ${e.message || 'Unknown'}`);
      });
    }
  }

  private async createAlarm(
    documentId: string,
    status: string,
    _errorMessage?: string,
  ): Promise<void> {
    const document = await this.documentRepository.findOne({
      where: { id: documentId },
    });
    if (!document) return;

    const alarmMessage =
      status === 'completed'
        ? 'AI 지식 추가가 완료되었습니다.'
        : 'AI 지식 추가에 실패했습니다. 문서함에서 상태를 확인하세요.';

    await this.alarmRepository.save(
      this.alarmRepository.create({
        usersId: document.createdBy,
        documentId,
        message: alarmMessage,
      }),
    );
  }
}
