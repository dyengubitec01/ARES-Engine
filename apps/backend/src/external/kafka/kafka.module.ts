import { Module, forwardRef } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ConfigModule } from '@nestjs/config';
import { EmbeddingStatusConsumer } from './embedding-status.consumer';
import { DocumentModule } from '../../document/document.module';
import { DocDocument } from '../../document/entities/doc-document.entity';
import { AuthUsersAlarm } from '../../auth/entities/auth-users-alarm.entity';

@Module({
  imports: [
    ConfigModule,
    forwardRef(() => DocumentModule),
    TypeOrmModule.forFeature([DocDocument, AuthUsersAlarm]),
  ],
  providers: [EmbeddingStatusConsumer],
  exports: [EmbeddingStatusConsumer],
})
export class KafkaModule {}
