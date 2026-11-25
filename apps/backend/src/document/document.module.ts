import { Module, forwardRef } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { DocumentService } from './document.service';
import { DocumentController } from './document.controller';
import { DocumentTagsService } from './services/document-tags.service';
import { DocumentTagsController } from './controllers/document-tags.controller';
import { DocDocument } from './entities/doc-document.entity';
import { DocDocumentContent } from './entities/doc-document-content.entity';
import { DocDocumentFavorite } from './entities/doc-document-favorite.entity';
import { DocDocumentExclude } from './entities/doc-document-exclude.entity';
import { DocUserTag } from './entities/doc-user-tag.entity';
import { DocUserTagMapping } from './entities/doc-user-tag-mapping.entity';
import { StorageObjectFile } from '../storage/entities/storage-object-file.entity';
import { AuthUser } from '../auth/entities/auth-user.entity';
import { AuthUsersAlarm } from '../auth/entities/auth-users-alarm.entity';
import { AuthUsersDeptAuthorityPermission } from '../auth/entities/auth-users-dept-authority-permission.entity';
import { DocEmbedReview } from './entities/doc-embed-review.entity';
import { RagStatusEvent } from '../rag/entities/rag-status-event.entity';
import { MinioModule } from '../external/minio/minio.module';
import { EmbeddingModule } from '../external/embedding/embedding.module';
import { QdrantModule } from '../external/qdrant/qdrant.module';
import { AuthModule } from '../auth/auth.module';
import { EmbeddingStatusGateway } from './services/embedding-status.gateway';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      DocDocument,
      DocDocumentContent,
      DocDocumentFavorite,
      DocDocumentExclude,
      DocUserTag,
      DocUserTagMapping,
      StorageObjectFile,
      AuthUser,
      AuthUsersAlarm,
      AuthUsersDeptAuthorityPermission,
      DocEmbedReview,
      RagStatusEvent,
    ]),
    MinioModule,
    EmbeddingModule,
    QdrantModule,
    forwardRef(() => AuthModule),
  ],
  controllers: [DocumentController, DocumentTagsController],
  providers: [DocumentService, DocumentTagsService, EmbeddingStatusGateway],
  exports: [DocumentService, DocumentTagsService, EmbeddingStatusGateway],
})
export class DocumentModule {}
