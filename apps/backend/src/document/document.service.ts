import {
  Injectable,
  Logger,
  InternalServerErrorException,
  Inject,
  forwardRef,
} from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { DataSource, Repository, IsNull } from 'typeorm';
import { DocDocument } from './entities/doc-document.entity';
import { DocDocumentContent } from './entities/doc-document-content.entity';
import { DocDocumentFavorite } from './entities/doc-document-favorite.entity';
import { DocDocumentExclude } from './entities/doc-document-exclude.entity';
import { DocEmbedReview } from './entities/doc-embed-review.entity';
import { RagStatusEvent } from '../rag/entities/rag-status-event.entity';
import { StorageObjectFile } from '../storage/entities/storage-object-file.entity';
import { AuthUser } from '../auth/entities/auth-user.entity';
import { AuthUsersAlarm } from '../auth/entities/auth-users-alarm.entity';
import { MinioService } from '../external/minio/minio.service';
import { EmbeddingService } from '../external/embedding/embedding.service';
import { QdrantService } from '../external/qdrant/qdrant.service';
import { CreateUploadSessionDto } from './dto/create-upload-session.dto';
import {
  DocumentListQueryDto,
  DocumentListResponseDto,
  DocumentListItemDto,
} from './dto/document-list.dto';
import { DocumentTagsService } from './services/document-tags.service';
import { AuthService } from '../auth/auth.service';
import { DocumentDetailDto, VersionDetailDto } from './dto/document-detail.dto';
import { DocStatus, ObjectKind, AuthorityType } from '../common/enums';
import { BusinessException } from '../common/exceptions/business.exception';
import {
  ResponseCode,
  getHttpStatus,
} from '../common/constants/response-codes';

export interface UploadInfo {
  filename: string;
  versionId: string;
  uploadUrl: string;
  objectKey: string;
  expiresIn: number;
}

export interface UploadSessionResponse {
  documentId: string;
  uploads: UploadInfo[];
}

export interface CompleteUploadResponse {
  documentId: string;
  versionId: string;
  status: DocStatus;
}

export interface DownloadUrlResponse {
  downloadUrl: string;
  expiresIn: number;
}

/**
 * Manifest JSON structure for uploaded files
 * Stored alongside the original file in MinIO
 */
export interface ManifestJson {
  documentId: string;
  filename: string;
  fileType: string;
  fileSize: number;
  hash: string | null; // null at upload time, filled by Embedding Worker
  uploader: {
    id: string;
    name: string | null;
    deptId: string | null;
    email: string;
  };
  uploadedAt: string; // ISO 8601 format
  title: string;
  is_active: string; // 'Y' or 'N'
}

@Injectable()
export class DocumentService {
  private readonly logger = new Logger(DocumentService.name);
  private readonly URL_EXPIRY_SECONDS = 3600; // 1 hour

  constructor(
    @InjectRepository(DocDocument)
    private readonly documentRepository: Repository<DocDocument>,
    @InjectRepository(DocDocumentContent)
    private readonly contentRepository: Repository<DocDocumentContent>,
    @InjectRepository(DocDocumentFavorite)
    private readonly favoriteRepository: Repository<DocDocumentFavorite>,
    @InjectRepository(DocDocumentExclude)
    private readonly excludeRepository: Repository<DocDocumentExclude>,
    @InjectRepository(StorageObjectFile)
    private readonly storageFileRepository: Repository<StorageObjectFile>,
    @InjectRepository(AuthUser)
    private readonly userRepository: Repository<AuthUser>,
    @InjectRepository(AuthUsersAlarm)
    private readonly alarmRepository: Repository<AuthUsersAlarm>,
    @InjectRepository(DocEmbedReview)
    private readonly embedReviewRepository: Repository<DocEmbedReview>,
    @InjectRepository(RagStatusEvent)
    private readonly statusEventRepository: Repository<RagStatusEvent>,
    private readonly minioService: MinioService,
    private readonly embeddingService: EmbeddingService,
    private readonly qdrantService: QdrantService,
    private readonly documentTagsService: DocumentTagsService,
    private readonly dataSource: DataSource,
    @Inject(forwardRef(() => AuthService))
    private readonly authService: AuthService,
  ) {}

  /**
   * Validate file metadata (size and MIME type)
   */
  /**
   * Generate object key for MinIO storage
   * Pattern: raw/{deptId}/{year}/{month}/{documentId}/{filename}
   * Note: Must use 'raw/' prefix due to MinIO IAM policy restrictions
   */
  private generateObjectKey(
    deptId: string,
    year: number,
    month: number,
    documentId: string,
    filename: string,
  ): string {
    const monthStr = month.toString().padStart(2, '0');
    return `raw/${deptId}/${year}/${monthStr}/${documentId}/${filename}`;
  }

  /**
   * Generate base path (directory) for MinIO storage
   * Pattern: raw/{deptId}/{year}/{month}/{documentId}/
   */
  private generateBasePath(
    deptId: string,
    year: number,
    month: number,
    documentId: string,
  ): string {
    const monthStr = month.toString().padStart(2, '0');
    return `raw/${deptId}/${year}/${monthStr}/${documentId}/`;
  }

  /**
   * Create upload session with pre-signed URLs
   * AC1: Pre-signed URL 생성
   * AC2: 파일 크기 제한 (100MB)
   * AC3: 파일 형식 제한
   * AC4: 응답 형식
   */
  async createUploadSession(
    userId: string,
    dto: CreateUploadSessionDto,
  ): Promise<UploadSessionResponse> {
    // Fetch user info to get deptId
    const user = await this.userRepository.findOne({
      where: { id: userId },
    });

    if (!user) {
      throw new InternalServerErrorException('User not found');
    }

    const deptId = user.authDeptId || 'unknown';
    const now = new Date();
    const year = now.getFullYear();
    const month = now.getMonth() + 1; // 0-indexed

    // Check for duplicate files by sha256 (exclude soft-deleted records)
    for (const file of dto.files) {
      const normalizedSha256 = file.sha256.toLowerCase();
      const existing = await this.contentRepository.findOne({
        where: { sha256: normalizedSha256, deletedAt: IsNull() },
      });
      if (existing) {
        throw new BusinessException(
          ResponseCode.DOC_UPLOAD_DUPLICATE,
          undefined,
          getHttpStatus(ResponseCode.DOC_UPLOAD_DUPLICATE),
        );
      }
    }

    // Use the first file's name as document title (without extension)
    const firstFile = dto.files[0];
    const title = firstFile.filename.replace(/\.[^/.]+$/, '');

    // Create document record
    const document = this.documentRepository.create({
      title,
      minioUrl: '', // Will be updated after we have the document ID
      createdBy: userId,
    });
    const savedDocument = await this.documentRepository.save(document);

    // Update minioUrl with new path structure (raw/{deptId}/{year}/{month}/{documentId}/)
    savedDocument.minioUrl = this.generateBasePath(
      deptId,
      year,
      month,
      savedDocument.id,
    );
    await this.documentRepository.save(savedDocument);

    // Create version record and pre-signed URL for each file
    const uploads: UploadInfo[] = [];

    for (const file of dto.files) {
      // Create version for this file (versionNo defaults to 1)
      const version = this.contentRepository.create({
        documentId: savedDocument.id,
        versionNo: 1,
        originalFilename: file.filename,
        uploaderId: userId,
        authDeptId: user.authDeptId,
        sha256: file.sha256.toLowerCase(), // From frontend, normalized to lowercase
        fileSize: file.size,
        mimeType: file.mimeType,
        status: DocStatus.UPLOADING,
        fileModifiedAt: new Date(file.fileModifiedAt),
      });
      const savedVersion = await this.contentRepository.save(version);

      // Generate object key and pre-signed URL with new path structure
      const objectKey = this.generateObjectKey(
        deptId,
        year,
        month,
        savedDocument.id,
        file.filename,
      );

      const uploadUrl = await this.minioService.generatePresignedPutUrl(
        objectKey,
        this.URL_EXPIRY_SECONDS,
      );

      uploads.push({
        filename: file.filename,
        versionId: savedVersion.id,
        uploadUrl,
        objectKey,
        expiresIn: this.URL_EXPIRY_SECONDS,
      });
    }

    return {
      documentId: savedDocument.id,
      uploads,
    };
  }

  /**
   * Complete upload - sets status to 'uploaded'
   * AC1: 업로드 완료 처리
   * AC2: storage_object_files 레코드 생성
   * AC3: manifest.json 생성 및 MinIO 업로드 (Story 4.4)
   * Note: 임베딩 요청은 별도 API로 분리됨 (Story 4.4.1)
   * Note: MinIO file verification removed due to HeadObject permission restriction
   */
  async completeUpload(
    userId: string,
    documentId: string,
    versionId: string,
  ): Promise<CompleteUploadResponse> {
    // Find document and verify ownership
    const document = await this.documentRepository.findOne({
      where: { id: documentId },
    });

    if (!document) {
      throw new BusinessException(
        ResponseCode.DOC_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.DOC_NOT_FOUND),
      );
    }

    if (document.createdBy !== userId) {
      throw new BusinessException(
        ResponseCode.DOC_FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.DOC_FORBIDDEN),
      );
    }

    // Find version (completeUpload)
    const version = await this.contentRepository.findOne({
      where: { id: versionId, documentId },
    });

    if (!version) {
      throw new BusinessException(
        ResponseCode.DOC_REFERENCE_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.DOC_REFERENCE_NOT_FOUND),
      );
    }

    // Fetch user info for manifest.json
    const user = await this.userRepository.findOne({
      where: { id: userId },
    });

    if (!user) {
      throw new InternalServerErrorException('User not found');
    }

    // Generate object key using document's minioUrl (base path)
    // minioUrl format: raw/{deptId}/{year}/{month}/{documentId}/
    const objectKey = `${document.minioUrl}${version.originalFilename}`;

    // MinIO에 파일이 실제 업로드되었는지 검증
    const exists = await this.minioService.objectExists(objectKey);
    if (!exists) {
      throw new BusinessException(
        ResponseCode.DOC_UPLOAD_NOT_FOUND_IN_STORAGE,
        undefined,
        getHttpStatus(ResponseCode.DOC_UPLOAD_NOT_FOUND_IN_STORAGE),
      );
    }

    // Update version status to uploaded (AC1)
    version.status = DocStatus.UPLOADED;
    await this.contentRepository.save(version);

    // Create storage_object_files record (AC2)
    const storageFile = this.storageFileRepository.create({
      docContentId: versionId,
      kind: ObjectKind.RAW,
      bucket: this.minioService.getBucket(),
      objectKey,
      sizeBytes: version.fileSize,
      metadata: {},
      createdBy: userId,
    });
    await this.storageFileRepository.save(storageFile);

    // Generate and upload manifest.json (AC3 - Story 4.4)
    const manifest: ManifestJson = {
      documentId,
      filename: version.originalFilename,
      fileType: version.mimeType,
      fileSize: Number(version.fileSize),
      hash: null, // Will be computed by Embedding Worker
      uploader: {
        id: user.id,
        name: user.name,
        deptId: user.authDeptId,
        email: user.email,
      },
      uploadedAt: new Date().toISOString(),
      title: document.title,
      is_active: 'Y',
    };

    const manifestKey = `${document.minioUrl}manifest.json`;
    const manifestBuffer = Buffer.from(JSON.stringify(manifest, null, 2));

    try {
      await this.minioService.uploadBuffer(
        manifestKey,
        manifestBuffer,
        'application/json',
      );
      this.logger.debug(`Uploaded manifest.json: ${manifestKey}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.warn(
        `Failed to upload manifest.json: ${manifestKey} - ${message}. Continuing without manifest.`,
      );
      // Don't fail the upload if manifest creation fails
    }

    return {
      documentId,
      versionId,
      status: DocStatus.UPLOADED,
    };
  }

  /**
   * Request embedding approval for a document (Story 4.15)
   * uploader/embedding/admin → pending_approval 상태로 변경
   */
  async bulkRequestEmbeddingApproval(
    versionIds: string[],
    requesterId: string,
    authorities: AuthorityType[],
  ): Promise<{
    results: {
      versionId: string;
      documentId?: string;
      status: string;
      error?: string;
    }[];
  }> {
    const isAdmin = authorities.includes(AuthorityType.ADMIN);
    const results: {
      versionId: string;
      documentId?: string;
      status: string;
      error?: string;
    }[] = [];

    for (const versionId of versionIds) {
      try {
        const content = await this.contentRepository.findOne({
          where: { id: versionId },
          relations: ['document'],
        });

        if (!content) {
          results.push({
            versionId,
            status: 'error',
            error: '버전을 찾을 수 없습니다',
          });
          continue;
        }

        if (!isAdmin && content.uploaderId !== requesterId) {
          results.push({
            versionId,
            status: 'error',
            error: '본인이 업로드한 문서만 요청할 수 있습니다',
          });
          continue;
        }

        if (content.deletedAt || content.status === DocStatus.DELETED) {
          results.push({
            versionId,
            status: 'error',
            error: '삭제된 문서입니다',
          });
          continue;
        }

        const allowedStatuses = [DocStatus.UPLOADED, DocStatus.REJECTED];
        if (!allowedStatuses.includes(content.status)) {
          results.push({
            versionId,
            status: 'error',
            error:
              '현재 상태에서는 임베딩을 요청할 수 없습니다 (uploaded/rejected만 가능)',
          });
          continue;
        }

        // ⚠️ 임시: 승인 절차 스킵 → 요청과 동시에 자동 승인 처리
        // 원래 status 백업 (실패 시 롤백)
        const originalStatus = content.status;

        // 1단계: pending_approval 로 변경
        content.status = DocStatus.PENDING_APPROVAL;
        content.statusReason = null;
        content.requestedAt = new Date();
        await this.contentRepository.save(content);

        // 2단계: 자동 승인 (Embedding Server 호출)
        try {
          const document = content.document;
          const objectKey = `${document.minioUrl}${content.originalFilename}`;

          await this.embeddingService.requestEmbedding({
            docContentId: content.id,
            requestedBy: requesterId,
            authDeptId: content.authDeptId || '',
            minioBucket: this.minioService.getBucket(),
            minioObjectKey: objectKey,
            embeddingProfile: 'bge_m3_v1',
            extractionVersion: 'v1.0.1',
          });

          // 성공: queued
          content.status = DocStatus.QUEUED;
          content.queuedAt = new Date();
          await this.contentRepository.save(content);

          // review 이력 (자동 승인)
          await this.embedReviewRepository.save(
            this.embedReviewRepository.create({
              docContentId: content.id,
              reviewerId: requesterId,
              action: 'approve',
              reason: 'AUTO_APPROVED',
            }),
          );

          // 알림
          await this.alarmRepository
            .save(
              this.alarmRepository.create({
                usersId: document.createdBy,
                documentId: document.id,
                message: 'AI 지식 추가 요청이 승인되었습니다.',
              }),
            )
            .catch((e: Error) =>
              this.logger.error(`알림 생성 실패: ${e.message}`),
            );

          results.push({
            versionId,
            documentId: content.documentId,
            status: content.status,
          });
        } catch (embedErr) {
          // 실패: 원래 status 로 롤백 + 에러 메시지 저장
          const errorMessage =
            embedErr instanceof Error
              ? embedErr.message
              : '처리 중 오류가 발생했습니다';
          content.status = originalStatus;
          content.statusReason = errorMessage;
          await this.contentRepository.save(content);

          this.logger.error(
            `자동 승인 실패: versionId=${versionId}, error=${errorMessage}`,
          );
          results.push({
            versionId,
            status: 'error',
            error: errorMessage,
          });
        }
      } catch (err) {
        this.logger.error(`임베딩 승인 요청 실패: versionId=${versionId}`, err);
        results.push({
          versionId,
          status: 'error',
          error: '처리 중 오류가 발생했습니다',
        });
      }
    }

    return { results };
  }

  /**
   * 재임베딩 일괄 요청 (failed/completed → 바로 Embedding Server 호출, 승인 불필요)
   */
  async bulkRequestReEmbedding(
    versionIds: string[],
    requesterId: string,
    authorities: AuthorityType[],
  ): Promise<{
    results: {
      versionId: string;
      documentId?: string;
      status: string;
      error?: string;
    }[];
  }> {
    const isAdmin = authorities.includes(AuthorityType.ADMIN);
    const results: {
      versionId: string;
      documentId?: string;
      status: string;
      error?: string;
    }[] = [];

    for (const versionId of versionIds) {
      try {
        const content = await this.contentRepository.findOne({
          where: { id: versionId },
          relations: ['document'],
        });

        if (!content) {
          results.push({
            versionId,
            status: 'error',
            error: '버전을 찾을 수 없습니다',
          });
          continue;
        }

        if (!isAdmin && content.uploaderId !== requesterId) {
          results.push({
            versionId,
            status: 'error',
            error: '본인이 업로드한 문서만 요청할 수 있습니다',
          });
          continue;
        }

        if (content.deletedAt || content.status === DocStatus.DELETED) {
          results.push({
            versionId,
            status: 'error',
            error: '삭제된 문서입니다',
          });
          continue;
        }

        if (
          content.status !== DocStatus.FAILED &&
          content.status !== DocStatus.COMPLETED
        ) {
          results.push({
            versionId,
            status: 'error',
            error: '재임베딩은 failed/completed 상태에서만 가능합니다',
          });
          continue;
        }

        await this.embeddingService.requestReEmbedding({
          docContentId: content.id,
          requestedBy: requesterId,
          embeddingProfile: 'bge_m3_v1',
        });

        content.requestedAt = new Date();
        await this.contentRepository.save(content);

        results.push({
          versionId,
          documentId: content.documentId,
          status: content.status,
        });
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : '처리 중 오류가 발생했습니다';
        this.logger.error(`재임베딩 요청 실패: versionId=${versionId}`, err);
        results.push({ versionId, status: 'error', error: errorMessage });
      }
    }

    return { results };
  }

  /**
   * Story 4.15: 임베딩 승인 대기 목록 조회 (embedding/admin)
   * - ADMIN: 전체 조회
   * - EMBEDDING: 접근 가능한 부서(authDeptId + deptPermissions)에 속한 문서만 조회
   */
  async getEmbedRequests(
    isAdmin: boolean,
    accessibleDeptIds: string[],
    page: number = 1,
    limit: number = 20,
    type: 'pending' | 'approved' | 'rejected' = 'pending',
    deptIds?: string[],
  ) {
    const skip = (page - 1) * limit;

    const APPROVED_STATUSES = [
      DocStatus.QUEUED,
      DocStatus.PARSING,
      DocStatus.CHUNKING,
      DocStatus.EMBEDDING,
      DocStatus.UPSERTING,
      DocStatus.COMPLETED,
      DocStatus.FAILED,
    ];

    const qb = this.contentRepository
      .createQueryBuilder('c')
      .leftJoinAndSelect('c.document', 'd');

    if (type === 'pending') {
      qb.where('c.status = :status', { status: DocStatus.PENDING_APPROVAL });
    } else if (type === 'approved') {
      qb.where('c.status IN (:...approvedStatuses)', {
        approvedStatuses: APPROVED_STATUSES,
      });
    } else {
      qb.where('c.status = :status', { status: DocStatus.REJECTED });
    }

    qb.andWhere('c.deletedAt IS NULL');

    // 부서 필터: deptIds 지정 시 해당 부서만, 아니면 접근 가능한 부서 전체
    if (!isAdmin) {
      if (accessibleDeptIds.length === 0) {
        return { items: [], meta: { total: 0, page, limit, totalPages: 0 } };
      }
      const targetDeptIds =
        deptIds && deptIds.length > 0
          ? deptIds.filter((id) => accessibleDeptIds.includes(id))
          : accessibleDeptIds;
      if (targetDeptIds.length === 0) {
        return { items: [], meta: { total: 0, page, limit, totalPages: 0 } };
      }
      qb.andWhere('c.authDeptId IN (:...targetDeptIds)', { targetDeptIds });
    } else if (deptIds && deptIds.length > 0) {
      qb.andWhere('c.authDeptId IN (:...deptIds)', { deptIds });
    }

    const [contents, total] = await qb
      .orderBy('c.requestedAt', 'ASC')
      .skip(skip)
      .take(limit)
      .getManyAndCount();

    if (contents.length === 0) {
      return { items: [], meta: { total: 0, page, limit, totalPages: 0 } };
    }

    // 업로더 정보 조회 (이름, 부서명)
    // 업로더 이름 조회
    const uploaderIds = [...new Set(contents.map((c) => c.uploaderId))];
    const uploaders = await this.userRepository
      .createQueryBuilder('u')
      .select('u.id', 'id')
      .addSelect('u.name', 'name')
      .whereInIds(uploaderIds)
      .getRawMany();
    const uploaderMap = new Map(uploaders.map((u) => [u.id, { name: u.name }]));

    // content의 authDeptId로 부서명 조회
    const embedDeptIdSet = new Set(
      contents.map((c) => c.authDeptId).filter(Boolean) as string[],
    );
    let embedDeptNameMap = new Map<string, string>();
    if (embedDeptIdSet.size > 0) {
      const depts = await this.userRepository.manager
        .createQueryBuilder()
        .select('d.id', 'id')
        .addSelect('d.dept_name', 'deptName')
        .from('auth_users_dept', 'd')
        .where('d.id IN (:...ids)', { ids: [...embedDeptIdSet] })
        .getRawMany();
      embedDeptNameMap = new Map(depts.map((d) => [d.id, d.deptName]));
    }

    // 심사 이력 조회 (reviewer 이름 포함)
    const contentIds = contents.map((c) => c.id);
    const reviews = await this.embedReviewRepository
      .createQueryBuilder('r')
      .leftJoin('auth_users', 'ru', 'ru.id = r.reviewerId')
      .select('r.docContentId', 'docContentId')
      .addSelect('r.action', 'action')
      .addSelect('r.reason', 'reason')
      .addSelect('r.createdAt', 'reviewedAt')
      .addSelect('ru.name', 'reviewerName')
      .where('r.docContentId IN (:...contentIds)', { contentIds })
      .orderBy('r.createdAt', 'DESC')
      .getRawMany();

    // contentId별 이력 그룹핑
    const reviewMap = new Map<
      string,
      {
        reviewerName: string | null;
        action: string;
        reason: string | null;
        reviewedAt: Date;
      }[]
    >();
    for (const r of reviews) {
      const list = reviewMap.get(r.docContentId) ?? [];
      list.push({
        reviewerName: r.reviewerName ?? null,
        action: r.action,
        reason: r.reason ?? null,
        reviewedAt: r.reviewedAt,
      });
      reviewMap.set(r.docContentId, list);
    }

    return {
      items: contents.map((c) => {
        const uploader = uploaderMap.get(c.uploaderId);
        const reviewHistory = reviewMap.get(c.id) ?? [];
        const latestReview = reviewHistory[0] ?? null;
        return {
          versionId: c.id,
          documentId: c.documentId,
          title: c.document?.title ?? null,
          versionNo: c.versionNo,
          filename: c.originalFilename,
          fileSize: Number(c.fileSize),
          mimeType: c.mimeType,
          status: c.status,
          statusReason: c.statusReason || null,
          uploaderName: uploader?.name ?? null,
          uploaderDepartment: c.authDeptId
            ? (embedDeptNameMap.get(c.authDeptId) ?? null)
            : null,
          reviewerName: latestReview?.reviewerName ?? null,
          requestedAt: c.requestedAt,
          createdAt: c.createdAt,
          reviewHistory,
        };
      }),
      meta: { total, page, limit, totalPages: Math.ceil(total / limit) },
    };
  }

  /**
   * Story 4.15: 임베딩 일괄 승인 (embedding/admin)
   */
  async bulkApproveEmbedding(versionIds: string[], reviewerId: string) {
    const results: { versionId: string; status: string; error?: string }[] = [];

    for (const versionId of versionIds) {
      try {
        const content = await this.contentRepository.findOne({
          where: { id: versionId },
          relations: ['document'],
        });

        if (!content) {
          results.push({
            versionId,
            status: 'error',
            error: '요청을 찾을 수 없습니다',
          });
          continue;
        }

        const approvalStatuses = [
          DocStatus.PENDING_APPROVAL,
          DocStatus.FAILED,
          DocStatus.COMPLETED,
        ];
        if (!approvalStatuses.includes(content.status)) {
          results.push({
            versionId,
            status: 'error',
            error: '승인할 수 없는 상태입니다',
          });
          continue;
        }

        const document = content.document;
        const objectKey = `${document.minioUrl}${content.originalFilename}`;

        // 첫 임베딩 요청
        await this.embeddingService.requestEmbedding({
          docContentId: content.id,
          requestedBy: reviewerId,
          authDeptId: content.authDeptId || '',
          minioBucket: this.minioService.getBucket(),
          minioObjectKey: objectKey,
          embeddingProfile: 'bge_m3_v1',
          extractionVersion: 'v1.0.1',
        });

        content.status = DocStatus.QUEUED;
        content.queuedAt = new Date();
        await this.contentRepository.save(content);

        await this.embedReviewRepository.save(
          this.embedReviewRepository.create({
            docContentId: content.id,
            reviewerId,
            action: 'approve',
            reason: null,
          }),
        );

        await this.alarmRepository
          .save(
            this.alarmRepository.create({
              usersId: document.createdBy,
              documentId: document.id,
              message: 'AI 지식 추가 요청이 승인되었습니다.',
            }),
          )
          .catch((err) => this.logger.error('알림 생성 실패', err));

        results.push({ versionId, status: content.status });
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : '처리 중 오류가 발생했습니다';
        this.logger.error(`임베딩 승인 실패: versionId=${versionId}`, err);
        results.push({ versionId, status: 'error', error: errorMessage });
      }
    }

    return { results };
  }

  /**
   * Story 4.15: 임베딩 일괄 거절 (embedding/admin)
   */
  async bulkRejectEmbedding(
    items: { versionId: string; reason?: string }[],
    reviewerId: string,
  ) {
    const results: { versionId: string; status: string; error?: string }[] = [];

    for (const item of items) {
      try {
        const content = await this.contentRepository.findOne({
          where: { id: item.versionId },
          relations: ['document'],
        });

        if (!content) {
          results.push({
            versionId: item.versionId,
            status: 'error',
            error: '요청을 찾을 수 없습니다',
          });
          continue;
        }

        if (content.status !== DocStatus.PENDING_APPROVAL) {
          results.push({
            versionId: item.versionId,
            status: 'error',
            error: '대기 중인 임베딩 요청이 아닙니다',
          });
          continue;
        }

        content.status = DocStatus.REJECTED;
        content.statusReason = item.reason ?? null;
        await this.contentRepository.save(content);

        await this.embedReviewRepository.save(
          this.embedReviewRepository.create({
            docContentId: content.id,
            reviewerId,
            action: 'reject',
            reason: item.reason ?? null,
          }),
        );

        const alarmMessage =
          'AI 지식 추가 요청이 반려되었습니다. 문서함에서 반려사유를 확인하세요.';
        await this.alarmRepository
          .save(
            this.alarmRepository.create({
              usersId: content.document.createdBy,
              documentId: content.document.id,
              message: alarmMessage,
            }),
          )
          .catch((err) => this.logger.error('알림 생성 실패', err));

        results.push({ versionId: item.versionId, status: content.status });
      } catch (err) {
        this.logger.error(`임베딩 거절 실패: versionId=${item.versionId}`, err);
        results.push({
          versionId: item.versionId,
          status: 'error',
          error: '처리 중 오류가 발생했습니다',
        });
      }
    }

    return { results };
  }

  /**
   * Request embedding for a document (Story 4.4.1)
   * AC1: 임베딩 요청
   * AC2: 상태 검증 (uploaded 상태만 가능)
   * AC3: 권한 검증 (admin 또는 uploader)
   * AC4: 존재하지 않는 문서
   */
  /**
   * Find documents with pagination and filtering
   * AC1: 문서 목록 조회
   * AC2: 페이지네이션
   * AC3: 상태 필터링
   * AC4: 응답 형식 (latestContent, isFavorite)
   */
  async getDocumentSummary(userId: string, accessibleDeptIds: string[]) {
    const qb = this.documentRepository
      .createQueryBuilder('d')
      .innerJoin(
        (sub) =>
          sub
            .select('c.document_id', 'document_id')
            .addSelect('MAX(c.version_no)', 'max_version')
            .from('doc_document_content', 'c')
            .groupBy('c.document_id'),
        'latest',
        'latest.document_id = d.id',
      )
      .innerJoin(
        'doc_document_content',
        'c',
        'c.document_id = d.id AND c.version_no = latest.max_version',
      )
      .leftJoin(
        'doc_document_exclude',
        'ex',
        'ex.document_content_id = c.id AND ex.user_id = :userId',
        { userId },
      )
      .select('c.status', 'status')
      .addSelect('COUNT(DISTINCT d.id)::int', 'count')
      .addSelect(
        `SUM(CASE WHEN c.status = 'completed' AND ex.id IS NULL THEN 1 ELSE 0 END)::int`,
        'enabledCount',
      );

    // 본인 문서 + 접근 가능한 부서 문서
    if (accessibleDeptIds.length > 0) {
      qb.where(
        '(d.created_by = :userId OR c.auth_dept_id IN (:...accessibleDeptIds))',
        { userId, accessibleDeptIds },
      );
    } else {
      qb.where('d.created_by = :userId', { userId });
    }

    qb.andWhere('c.deleted_at IS NULL').groupBy('c.status');

    const result = await qb.getRawMany();

    const summary = {
      uploaded: 0,
      completed: 0,
      enabled: 0,
      pendingApproval: 0,
    };

    for (const row of result) {
      const count = row.count ?? 0;
      if (row.status === DocStatus.UPLOADED) summary.uploaded = count;
      else if (row.status === DocStatus.COMPLETED) {
        summary.completed = count;
        summary.enabled = row.enabledCount ?? 0;
      } else if (row.status === DocStatus.PENDING_APPROVAL)
        summary.pendingApproval = count;
    }

    return summary;
  }

  async findDocuments(
    userId: string,
    authDeptId: string | null,
    deptPermissions: string[],
    query: DocumentListQueryDto,
  ): Promise<DocumentListResponseDto> {
    const {
      page = 1,
      limit = 20,
      status,
      favorite,
      deptIds,
      sort = 'latest',
      tagIds,
      keyword,
      view = 'all',
    } = query;
    const skip = (page - 1) * limit;

    let tagFilteredDocIds: string[] | null = null;
    if (tagIds && tagIds.length > 0) {
      tagFilteredDocIds = await this.documentTagsService.findDocumentIdsByTagIds(
        userId,
        tagIds,
      );
      if (tagFilteredDocIds.length === 0) {
        return {
          items: [],
          meta: { total: 0, page, limit, totalPages: 0 },
        };
      }
    }

    // Simple query: get documents with versions
    const queryBuilder = this.documentRepository
      .createQueryBuilder('d')
      .leftJoinAndSelect('d.contents', 'c')
      .leftJoinAndSelect('d.favorites', 'f', 'f.usersId = :userId', { userId })
      .leftJoinAndSelect('c.excludes', 'ex', 'ex.userId = :userId', { userId })
      .leftJoinAndSelect('d.createdByUser', 'u');

    // 전사 공개 부서(env PUBLIC_DEPT_IDS)
    const publicDeptIds = this.authService.getPublicDeptIds();

    if (view === 'mine') {
      // 본인 업로드 문서만 (uploader_id 기준)
      queryBuilder.where('c.uploaderId = :userId', { userId });
    } else if (view === 'public') {
      // 공개 부서 문서만
      if (publicDeptIds.length === 0) {
        return {
          items: [],
          meta: { total: 0, page, limit, totalPages: 0 },
        };
      }
      queryBuilder.where('c.authDeptId IN (:...publicDeptIds)', {
        publicDeptIds,
      });
    } else if (view === 'dept') {
      // 선택한 부서만 — 본인/공개 자동 포함 없음
      if (!deptIds || deptIds.length === 0) {
        return {
          items: [],
          meta: { total: 0, page, limit, totalPages: 0 },
        };
      }
      const accessibleDeptIds = this.authService.getAccessibleDeptIds(
        authDeptId,
        deptPermissions,
      );
      const filteredDeptIds = deptIds.filter((id) =>
        accessibleDeptIds.includes(id),
      );
      if (filteredDeptIds.length === 0) {
        return {
          items: [],
          meta: { total: 0, page, limit, totalPages: 0 },
        };
      }
      queryBuilder.where('c.authDeptId IN (:...filteredDeptIds)', {
        filteredDeptIds,
      });
    } else {
      // view === 'all' (default): 접근 가능 모든 부서 + 본인 업로드
      const accessibleDeptIds = this.authService.getAccessibleDeptIds(
        authDeptId,
        deptPermissions,
      );
      if (accessibleDeptIds.length > 0) {
        queryBuilder.where(
          '(c.authDeptId IN (:...accessibleDeptIds) OR c.uploaderId = :userId)',
          { accessibleDeptIds, userId },
        );
      } else {
        queryBuilder.where('c.uploaderId = :userId', { userId });
      }
    }

    queryBuilder
      .andWhere('c.deletedAt IS NULL')
      .andWhere('c.status != :deletedStatus', {
        deletedStatus: DocStatus.DELETED,
      });

    if (tagFilteredDocIds && tagFilteredDocIds.length > 0) {
      queryBuilder.andWhere('d.id IN (:...tagFilteredDocIds)', {
        tagFilteredDocIds,
      });
    }

    if (keyword && keyword.length > 0) {
      const tokens = keyword.split(/\s+/).filter((t) => t.length > 0);
      tokens.forEach((token, idx) => {
        const paramKey = `keyword${idx}`;
        queryBuilder.andWhere(`c.originalFilename ILIKE :${paramKey}`, {
          [paramKey]: `%${token}%`,
        });
      });
    }

    // Apply status filter (filter on version status)
    if (status) {
      queryBuilder.andWhere('c.status = :status', { status });
    }

    // Apply favorite filter
    if (favorite === true) {
      queryBuilder.andWhere('f.id IS NOT NULL');
    } else if (favorite === false) {
      queryBuilder.andHaving('COUNT(f.id) = 0');
    }

    // Get total count
    const total = await queryBuilder.getCount();

    // Apply pagination and ordering
    const order = sort === 'oldest' ? 'ASC' : 'DESC';
    queryBuilder.orderBy('d.createdAt', order).skip(skip).take(limit);

    // Execute query
    const documents = await queryBuilder.getMany();

    // 최신 버전 contentId 수집 후 실패 횟수 조회
    const latestContentIds = documents
      .map(
        (doc) => doc.contents?.sort((a, b) => b.versionNo - a.versionNo)[0]?.id,
      )
      .filter(Boolean);

    let failedCountMap = new Map<string, number>();
    if (latestContentIds.length > 0) {
      const failedCounts = await this.statusEventRepository
        .createQueryBuilder('e')
        .select('e.docContentId', 'docContentId')
        .addSelect('COUNT(*)::int', 'failedCount')
        .where('e.docContentId IN (:...ids)', { ids: latestContentIds })
        .andWhere('e.status = :status', { status: 'failed' })
        .groupBy('e.docContentId')
        .getRawMany();
      failedCountMap = new Map(
        failedCounts.map((r) => [r.docContentId, r.failedCount]),
      );
    }

    // 최신 버전의 authDeptId로 부서명 조회
    const deptIdSet = new Set(
      documents
        .map(
          (doc) =>
            doc.contents?.sort((a, b) => b.versionNo - a.versionNo)[0]
              ?.authDeptId,
        )
        .filter(Boolean) as string[],
    );
    let deptNameMap = new Map<string, string>();
    if (deptIdSet.size > 0) {
      const depts = await this.userRepository.manager
        .createQueryBuilder()
        .select('d.id', 'id')
        .addSelect('d.dept_name', 'deptName')
        .from('auth_users_dept', 'd')
        .where('d.id IN (:...ids)', { ids: [...deptIdSet] })
        .getRawMany();
      deptNameMap = new Map(depts.map((d) => [d.id, d.deptName]));
    }

    const docIds = documents.map((d) => d.id);
    const myTagsMap = await this.documentTagsService.findTagsByDocumentIds(
      userId,
      docIds,
    );

    // Map results to DTOs
    const items: DocumentListItemDto[] = documents.map((doc) => {
      // Get latest version (highest versionNo)
      const latestContent = doc.contents?.sort(
        (a, b) => b.versionNo - a.versionNo,
      )[0];
      const isFavorite = doc.favorites && doc.favorites.length > 0;

      return {
        id: doc.id,
        title: doc.title,
        latestContent: latestContent
          ? {
              id: latestContent.id,
              versionNo: latestContent.versionNo,
              originalFilename: latestContent.originalFilename,
              fileSize: Number(latestContent.fileSize),
              mimeType: latestContent.mimeType,
              status: latestContent.status,
              statusReason: latestContent.statusReason || null,
              isEnabled: !latestContent.excludes?.length,
              createdAt: latestContent.createdAt,
            }
          : null,
        isFavorite,
        uploaderDepartment: latestContent?.authDeptId
          ? (deptNameMap.get(latestContent.authDeptId) ?? null)
          : null,
        failedCount: latestContent
          ? (failedCountMap.get(latestContent.id) ?? 0)
          : 0,
        myTags: myTagsMap.get(doc.id) ?? [],
        createdAt: doc.createdAt,
      };
    });

    return {
      items,
      meta: {
        total,
        page,
        limit,
        totalPages: Math.ceil(total / limit),
      },
    };
  }

  /**
   * Find all documents for admin (Story 4.12)
   * AC1: 관리자 문서 목록 조회 (모든 사용자 문서, 삭제된 문서 포함)
   * AC2: 페이지네이션
   * AC3: 상태 필터링
   * AC4: 삭제 여부 필터링
   * AC5: 응답 형식 (소유자 정보, deletedAt 포함)
   */
  async findAllDocumentsForAdmin(query: {
    page?: number;
    limit?: number;
    status?: DocStatus;
    deletedOnly?: boolean;
    sort?: 'latest' | 'oldest';
    deptIds?: string[];
  }): Promise<{
    data: Array<{
      id: string;
      title: string;
      latestContent: {
        id: string;
        versionNo: number;
        originalFilename: string;
        fileSize: number;
        mimeType: string;
        status: DocStatus;
        statusReason: string | null;
        createdAt: Date;
      } | null;
      createdBy: {
        id: string;
        name: string | null;
        email: string;
        department: string | null;
      };
      createdAt: Date;
    }>;
    meta: {
      total: number;
      page: number;
      limit: number;
      totalPages: number;
    };
  }> {
    const {
      page = 1,
      limit = 20,
      status,
      deletedOnly,
      sort = 'latest',
      deptIds,
    } = query;
    const skip = (page - 1) * limit;

    // Query all documents with versions and owner info
    const queryBuilder = this.documentRepository
      .createQueryBuilder('d')
      .leftJoinAndSelect('d.contents', 'c')
      .leftJoinAndSelect('d.createdByUser', 'u');

    // AC4: Filter by deleted status (now on content level)
    if (deletedOnly === true) {
      queryBuilder.where('c.deletedAt IS NOT NULL');
    }
    // By default, include all documents (deleted and non-deleted)

    // AC3: Apply status filter (filter on version status)
    if (status) {
      queryBuilder.andWhere('c.status = :status', { status });
    }

    // 부서 필터
    if (deptIds && deptIds.length > 0) {
      queryBuilder.andWhere('c.authDeptId IN (:...deptIds)', { deptIds });
    }

    // Get total count
    const total = await queryBuilder.getCount();

    // Apply pagination and ordering
    const order = sort === 'oldest' ? 'ASC' : 'DESC';
    queryBuilder.orderBy('d.createdAt', order).skip(skip).take(limit);

    // Execute query
    const documents = await queryBuilder.getMany();

    // 최신 버전의 authDeptId로 부서명 조회
    const adminDeptIdSet = new Set(
      documents
        .map(
          (doc) =>
            doc.contents?.sort((a, b) => b.versionNo - a.versionNo)[0]
              ?.authDeptId,
        )
        .filter(Boolean) as string[],
    );
    let adminDeptNameMap = new Map<string, string>();
    if (adminDeptIdSet.size > 0) {
      const depts = await this.userRepository.manager
        .createQueryBuilder()
        .select('d.id', 'id')
        .addSelect('d.dept_name', 'deptName')
        .from('auth_users_dept', 'd')
        .where('d.id IN (:...ids)', { ids: [...adminDeptIdSet] })
        .getRawMany();
      adminDeptNameMap = new Map(depts.map((d) => [d.id, d.deptName]));
    }

    // Map results to DTOs
    const data = documents.map((doc) => {
      // Get latest version (highest versionNo)
      const latestContent = doc.contents?.sort(
        (a, b) => b.versionNo - a.versionNo,
      )[0];

      return {
        id: doc.id,
        title: doc.title,
        latestContent: latestContent
          ? {
              id: latestContent.id,
              versionNo: latestContent.versionNo,
              originalFilename: latestContent.originalFilename,
              fileSize: Number(latestContent.fileSize),
              mimeType: latestContent.mimeType,
              status: latestContent.status,
              statusReason: latestContent.statusReason || null,
              createdAt: latestContent.createdAt,
            }
          : null,
        createdBy: {
          id: doc.createdByUser?.id || doc.createdBy,
          name: doc.createdByUser?.name || null,
          email: doc.createdByUser?.email || '',
          department: latestContent?.authDeptId
            ? (adminDeptNameMap.get(latestContent.authDeptId) ?? null)
            : null,
        },
        createdAt: doc.createdAt,
      };
    });

    return {
      data,
      meta: {
        total,
        page,
        limit,
        totalPages: Math.ceil(total / limit),
      },
    };
  }

  /**
   * Get document detail by ID
   * AC1: 문서 상세 조회
   * AC2: 버전 히스토리
   * AC3: 권한 검증
   * Note: Soft Delete된 문서는 조회 불가
   */
  async findOne(
    userId: string,
    documentId: string,
    authorities?: string[],
  ): Promise<DocumentDetailDto> {
    // Find document with non-deleted contents
    const document = await this.documentRepository.findOne({
      where: {
        id: documentId,
        contents: { deletedAt: IsNull() },
      },
      relations: ['contents'],
      order: { contents: { versionNo: 'DESC' } },
    });

    if (!document) {
      throw new BusinessException(
        ResponseCode.DOC_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.DOC_NOT_FOUND),
      );
    }

    // 권한 검증 (1순위: ADMIN → 2순위: 소유자)
    if (
      !authorities?.includes(AuthorityType.ADMIN) &&
      document.createdBy !== userId
    ) {
      throw new BusinessException(
        ResponseCode.DOC_FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.DOC_FORBIDDEN),
      );
    }

    // Check if user favorited this document
    const favorite = await this.favoriteRepository.findOne({
      where: { documentId, usersId: userId },
    });

    // Map contents to DTOs
    const versions: VersionDetailDto[] = document.contents.map((c) => ({
      id: c.id,
      versionNo: c.versionNo,
      originalFilename: c.originalFilename,
      fileSize: Number(c.fileSize),
      mimeType: c.mimeType,
      status: c.status,
      statusReason: c.statusReason || null,
      queuedAt: c.queuedAt || null,
      startedAt: c.startedAt || null,
      finishedAt: c.finishedAt || null,
      createdAt: c.createdAt,
    }));

    return {
      id: document.id,
      title: document.title,
      minioUrl: document.minioUrl,
      createdBy: document.createdBy,
      createdAt: document.createdAt,
      versions,
      isFavorite: !!favorite,
    };
  }

  /**
   * Soft Delete a document
   * Story 4.7: 문서 삭제 API
   * AC1: DB - deleted_at, is_active='N', status='deleted' 업데이트
   * AC2: MinIO JSON 메타데이터 is_active 업데이트 (manifest.json, metadata.json, stats.json)
   * AC3: Qdrant 벡터 payload is_active 업데이트
   * AC4: 권한 검증 (소유자 또는 admin)
   * AC5: 존재하지 않는 문서
   * Note: 보상 트랜잭션 (Saga) - DB 먼저 커밋, 외부 서비스 실패 시 DB 롤백
   */
  async deleteDocument(
    userId: string,
    documentId: string,
    authorities: AuthorityType[] = [],
  ): Promise<void> {
    // Find document with contents
    const document = await this.documentRepository.findOne({
      where: { id: documentId },
      relations: ['contents'],
    });

    if (!document) {
      throw new BusinessException(
        ResponseCode.DOC_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.DOC_NOT_FOUND),
      );
    }

    // Check if all contents are already deleted
    const activeContents = document.contents?.filter((c) => !c.deletedAt) || [];
    if (activeContents.length === 0) {
      throw new BusinessException(
        ResponseCode.DOC_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.DOC_NOT_FOUND),
      );
    }

    // Check authority (AC4) — 1순위: 소유자 → 2순위: admin
    const isSystem = authorities.includes(AuthorityType.ADMIN);
    const isAdmin = authorities.includes(AuthorityType.ADMIN);
    const isOwner = document.createdBy === userId;

    if (!isSystem && !isOwner && !isAdmin) {
      throw new BusinessException(
        ResponseCode.DOC_DELETE_FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.DOC_DELETE_FORBIDDEN),
      );
    }

    this.logger.debug(`문서 Soft Delete 시작: documentId=${documentId}`);

    // 원본 상태 저장 (보상 트랜잭션용)
    const originalStates = activeContents.map((c) => ({
      id: c.id,
      deletedAt: c.deletedAt,
      status: c.status,
      isActive: c.isActive,
    }));

    // Step 1: DB 트랜잭션 - deleted_at, is_active, status 업데이트 (AC1)
    const queryRunner = this.dataSource.createQueryRunner();
    await queryRunner.connect();
    await queryRunner.startTransaction();

    try {
      const now = new Date();
      for (const content of activeContents) {
        content.deletedAt = now;
        content.status = DocStatus.DELETED;
        content.isActive = 'N';
        content.sha256 = null; // Clear sha256 to allow re-upload of same file
      }
      await queryRunner.manager.save(activeContents);
      await queryRunner.commitTransaction();
      this.logger.debug(`DB: ${activeContents.length} contents soft deleted`);
    } catch (error) {
      await queryRunner.rollbackTransaction();
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`DB soft delete failed: ${message}`);
      throw new InternalServerErrorException(
        `Failed to soft delete document: ${message}`,
      );
    } finally {
      await queryRunner.release();
    }

    // Step 2: MinIO JSON 메타데이터 is_active='N' 업데이트 (AC2)
    let minioUpdatedKeys: string[] = [];
    try {
      minioUpdatedKeys = await this.deactivateMinioMetadata(documentId);
      this.logger.debug(
        `MinIO: ${minioUpdatedKeys.length} files deactivated for document ${documentId}`,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(
        `MinIO deactivation failed, rolling back DB: ${message}`,
      );
      // 보상 트랜잭션: DB 상태 복구
      await this.compensateDbSoftDelete(activeContents, originalStates);
      throw new InternalServerErrorException(
        `Failed to deactivate MinIO metadata: ${message}`,
      );
    }

    // Step 3: Qdrant 벡터 payload is_active='N' 업데이트 (AC3)
    try {
      const deactivatedCount =
        await this.qdrantService.deactivateByDocumentId(documentId);
      this.logger.debug(
        `Qdrant: ${deactivatedCount} points deactivated for document ${documentId}`,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(
        `Qdrant deactivation failed, rolling back MinIO and DB: ${message}`,
      );
      // 보상 트랜잭션: MinIO + DB 상태 복구
      await this.reactivateMinioMetadata(minioUpdatedKeys);
      await this.compensateDbSoftDelete(activeContents, originalStates);
      throw new InternalServerErrorException(
        `Failed to deactivate Qdrant vectors: ${message}`,
      );
    }

    this.logger.log(`문서 Soft Delete 완료: documentId=${documentId}`);
  }

  /**
   * 보상 트랜잭션: DB Soft Delete 롤백
   * 원래 상태로 복구 (deleted_at, status, is_active)
   */
  private async compensateDbSoftDelete(
    contents: DocDocumentContent[],
    originalStates: Array<{
      id: string;
      deletedAt: Date | null;
      status: DocStatus;
      isActive: string;
    }>,
  ): Promise<void> {
    const queryRunner = this.dataSource.createQueryRunner();
    await queryRunner.connect();
    await queryRunner.startTransaction();

    try {
      for (const content of contents) {
        const original = originalStates.find((s) => s.id === content.id);
        if (original) {
          content.deletedAt = original.deletedAt;
          content.status = original.status;
          content.isActive = original.isActive;
        }
      }
      await queryRunner.manager.save(contents);
      await queryRunner.commitTransaction();
      this.logger.debug('DB soft delete compensated (rolled back)');
    } catch (error) {
      await queryRunner.rollbackTransaction();
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`DB compensation failed: ${message}`);
    } finally {
      await queryRunner.release();
    }
  }

  /**
   * MinIO 메타데이터 JSON 파일의 is_active를 'N'으로 업데이트
   * 대상: manifest.json, metadata.json, stats.json
   * @returns 업데이트된 파일 키 목록 (롤백용)
   */
  private async deactivateMinioMetadata(documentId: string): Promise<string[]> {
    const updatedKeys: string[] = [];
    const targets = [
      {
        prefix: 'raw/',
        description: 'manifest.json',
        filename: 'manifest.json',
      },
      {
        prefix: `chunks/${documentId}/`,
        description: 'metadata.json',
        filename: 'metadata.json',
      },
      {
        prefix: `embeddings/${documentId}/`,
        description: 'stats.json',
        filename: 'stats.json',
      },
    ];

    for (const { prefix, description, filename } of targets) {
      let targetFiles: string[];

      if (prefix === 'raw/') {
        // raw는 deptId/년/월/documentId 구조라 전체 검색 후 documentId로 필터
        const objects = await this.minioService.listObjects(prefix);
        targetFiles = objects
          .filter(
            (obj) =>
              obj.name.includes(documentId) && obj.name.endsWith(filename),
          )
          .map((obj) => obj.name);
      } else {
        // chunks/embeddings는 documentId가 바로 다음에 옴
        const objects = await this.minioService.listObjects(prefix);
        targetFiles = objects
          .filter((obj) => obj.name.endsWith(filename))
          .map((obj) => obj.name);
      }

      for (const objectKey of targetFiles) {
        const updated = await this.minioService.updateJsonObject(objectKey, {
          is_active: 'N',
        });
        if (updated) {
          updatedKeys.push(objectKey);
          this.logger.debug(`MinIO ${description} deactivated: ${objectKey}`);
        }
      }
    }

    return updatedKeys;
  }

  /**
   * MinIO 메타데이터 JSON 파일의 is_active를 'Y'로 롤백
   * deactivateMinioMetadata 실패 시 복구용
   */
  private async reactivateMinioMetadata(objectKeys: string[]): Promise<void> {
    for (const objectKey of objectKeys) {
      try {
        await this.minioService.updateJsonObject(objectKey, {
          is_active: 'Y',
        });
        this.logger.debug(`MinIO rollback (reactivated): ${objectKey}`);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Unknown error';
        this.logger.error(`MinIO rollback failed for ${objectKey}: ${message}`);
      }
    }
  }

  /**
   * Hard Delete a document (관리자 전용)
   * 모든 데이터를 영구 삭제: DB 레코드, MinIO 파일, Qdrant 벡터
   * 순서: DB 삭제 (트랜잭션 시작) → MinIO → Qdrant → 커밋
   * Note: 외부 서비스 실패 시 트랜잭션 롤백으로 DB 복구
   */
  async hardDeleteDocument(documentId: string): Promise<void> {
    // Find document with all relations
    const document = await this.documentRepository.findOne({
      where: { id: documentId },
      relations: ['contents'],
    });

    if (!document) {
      throw new BusinessException(
        ResponseCode.DOC_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.DOC_NOT_FOUND),
      );
    }

    this.logger.debug(`문서 Hard Delete 시작: documentId=${documentId}`);

    const queryRunner = this.dataSource.createQueryRunner();
    await queryRunner.connect();
    await queryRunner.startTransaction();

    try {
      // Step 1: MinIO 파일 삭제 (없으면 무시)
      try {
        await this.deleteMinioFiles(documentId, document.minioUrl);
        this.logger.debug(`MinIO: files deleted for document ${documentId}`);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Unknown error';
        this.logger.warn(`MinIO hard delete failed (continuing): ${message}`);
      }

      // Step 2: Qdrant 벡터 삭제 (없으면 무시)
      try {
        const deletedCount =
          await this.qdrantService.deleteByDocumentId(documentId);
        this.logger.debug(
          `Qdrant: ${deletedCount} points deleted for document ${documentId}`,
        );
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Unknown error';
        this.logger.warn(`Qdrant hard delete failed (continuing): ${message}`);
      }

      // Step 3: 외부 삭제 완료 후 DB 삭제 → 커밋
      await queryRunner.manager.remove(document);
      await queryRunner.commitTransaction();
      this.logger.debug(`DB transaction committed`);
    } catch (error) {
      // 어떤 단계든 실패 시 트랜잭션 롤백 (DB 복구)
      await queryRunner.rollbackTransaction();
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Hard delete failed, DB rolled back: ${message}`);
      throw error instanceof InternalServerErrorException
        ? error
        : new InternalServerErrorException(
            `Failed to hard delete document: ${message}`,
          );
    } finally {
      await queryRunner.release();
    }

    this.logger.log(`문서 Hard Delete 완료: documentId=${documentId}`);
  }

  /**
   * MinIO에서 문서 관련 모든 파일 삭제
   * 대상: raw/{...}/{documentId}/*, chunks/{documentId}/*, embeddings/{documentId}/*
   */
  private async deleteMinioFiles(
    documentId: string,
    minioUrl: string,
  ): Promise<void> {
    const prefixes = [
      minioUrl, // raw/{deptId}/{year}/{month}/{documentId}/
      `chunks/${documentId}/`,
      `embeddings/${documentId}/`,
    ];

    for (const prefix of prefixes) {
      try {
        const objects = await this.minioService.listObjects(prefix);
        for (const obj of objects) {
          await this.minioService.deleteObject(obj.name);
          this.logger.debug(`MinIO deleted: ${obj.name}`);
        }
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Unknown error';
        this.logger.warn(
          `MinIO delete failed for prefix ${prefix}: ${message}`,
        );
        // MinIO 파일이 없을 수 있으므로 계속 진행
      }
    }
  }

  /**
   * Get download URL for a document version
   * Story 4.8: 문서 다운로드 API
   * AC1: Pre-signed GET URL 생성
   * AC2: 응답 형식 (downloadUrl, expiresIn)
   * AC3: 권한 검증 (문서 소유자만)
   */
  async getDownloadUrl(
    userId: string,
    deptPermissions: string[],
    authDeptId: string | null,
    versionId: string,
  ): Promise<DownloadUrlResponse> {
    // Find version with parent document
    const version = await this.contentRepository.findOne({
      where: { id: versionId },
      relations: ['document'],
    });

    if (!version) {
      throw new BusinessException(
        ResponseCode.DOC_REFERENCE_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.DOC_REFERENCE_NOT_FOUND),
      );
    }

    // AC3: 3단계 우선순위 권한 검증
    // 1순위: 문서 생성자 → 즉시 허용
    if (version.document.createdBy === userId) {
      // pass
    }
    // 2순위: 부서 권한 일치 → 본인 소속 부서 또는 부여된 부서 권한과 일치
    else if (
      version.authDeptId &&
      (version.authDeptId === authDeptId ||
        deptPermissions.includes(version.authDeptId))
    ) {
      // pass
    }
    // 그 외 → 403
    else {
      throw new BusinessException(
        ResponseCode.DOC_DOWNLOAD_FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.DOC_DOWNLOAD_FORBIDDEN),
      );
    }

    // Generate object key using document's minioUrl (base path) (AC1)
    // minioUrl format: raw/{deptId}/{year}/{month}/{documentId}/
    const objectKey = `${version.document.minioUrl}${version.originalFilename}`;

    const downloadUrl = await this.minioService.generatePresignedGetUrl(
      objectKey,
      this.URL_EXPIRY_SECONDS,
    );

    // AC2: 응답 형식
    return {
      downloadUrl,
      expiresIn: this.URL_EXPIRY_SECONDS,
    };
  }

  /**
   * Toggle document RAG reference (ON/OFF)
   * 레코드 없음 = ON(기본), 레코드 있음 = OFF
   */
  async toggleDocumentReference(
    userId: string,
    contentId: string,
  ): Promise<{ isEnabled: boolean }> {
    const content = await this.contentRepository.findOne({
      where: { id: contentId },
    });

    if (!content) {
      throw new BusinessException(
        ResponseCode.DOC_REFERENCE_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.DOC_REFERENCE_NOT_FOUND),
      );
    }

    const existing = await this.excludeRepository.findOne({
      where: { userId, documentContentId: contentId },
    });

    if (existing) {
      // 제외 레코드 있음 → 삭제 (ON으로 전환)
      await this.excludeRepository.remove(existing);
      return { isEnabled: true };
    } else {
      // 제외 레코드 없음 → 생성 (OFF로 전환)
      const exclude = this.excludeRepository.create({
        userId,
        documentContentId: contentId,
      });
      await this.excludeRepository.save(exclude);
      return { isEnabled: false };
    }
  }

  /**
   * Add document to favorites
   * AC1: 즐겨찾기 추가
   * AC2: 중복 즐겨찾기 방지
   * AC5: 권한 검증
   */
  async addFavorite(userId: string, documentId: string): Promise<void> {
    // Check if document exists (AC5)
    const document = await this.documentRepository.findOne({
      where: { id: documentId },
    });

    if (!document) {
      throw new BusinessException(
        ResponseCode.DOC_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.DOC_NOT_FOUND),
      );
    }

    // Check if already favorited (AC2)
    const existing = await this.favoriteRepository.findOne({
      where: { documentId, usersId: userId },
    });

    if (existing) {
      throw new BusinessException(
        ResponseCode.DOC_FAVORITE_DUPLICATE,
        undefined,
        getHttpStatus(ResponseCode.DOC_FAVORITE_DUPLICATE),
      );
    }

    // Create favorite record (AC1)
    const favorite = this.favoriteRepository.create({
      documentId,
      usersId: userId,
    });
    await this.favoriteRepository.save(favorite);
  }

  /**
   * Remove document from favorites
   * AC3: 즐겨찾기 해제
   */
  async removeFavorite(userId: string, documentId: string): Promise<void> {
    // Find favorite record
    const favorite = await this.favoriteRepository.findOne({
      where: { documentId, usersId: userId },
    });

    if (!favorite) {
      throw new BusinessException(
        ResponseCode.DOC_FAVORITE_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.DOC_FAVORITE_NOT_FOUND),
      );
    }

    // Remove favorite
    await this.favoriteRepository.remove(favorite);
  }
}
