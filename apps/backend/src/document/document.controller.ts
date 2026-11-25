import {
  Controller,
  Post,
  Put,
  Get,
  Patch,
  Delete,
  Body,
  Param,
  Query,
  ParseUUIDPipe,
  HttpCode,
  HttpStatus,
  UnauthorizedException,
  Logger,
} from '@nestjs/common';
import { Sse } from '../common/decorators';
import { Observable } from 'rxjs';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiBearerAuth,
  ApiQuery,
  ApiBody,
} from '@nestjs/swagger';
import { JwtService } from '@nestjs/jwt';
import { DocumentService } from './document.service';
import { DocumentTagsService } from './services/document-tags.service';
import { SetDocumentTagsDto } from './dto/document-tag.dto';
import { CreateUploadSessionDto } from './dto/create-upload-session.dto';
import { DocumentListQueryDto } from './dto/document-list.dto';
import { Authorities } from '../auth/decorators/authorities.decorator';
import { DocStatus, AuthorityType } from '../common/enums';
import { MinioService } from '../external/minio/minio.service';
import { EmbeddingStatusGateway } from './services/embedding-status.gateway';
import { ResponseCode } from '../common/decorators/response-code.decorator';
import {
  ResponseCode as RC,
  ResponseMessage,
  getHttpStatus,
} from '../common/constants/response-codes';
import { BusinessException } from '../common/exceptions/business.exception';
import { Public } from '../auth/decorators/public.decorator';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import type { AuthenticatedUser } from '../auth/types/authenticated-user';
import { AuthService } from '../auth/auth.service';
import * as Examples from './swagger-examples/documents.examples';

interface MessageEvent {
  data: string;
  type?: string;
}

@ApiTags('documents')
@ApiBearerAuth()
@Controller('documents')
export class DocumentController {
  private readonly logger = new Logger(DocumentController.name);

  constructor(
    private readonly documentService: DocumentService,
    private readonly documentTagsService: DocumentTagsService,
    private readonly minioService: MinioService,
    private readonly embeddingStatusGateway: EmbeddingStatusGateway,
    private readonly jwtService: JwtService,
    private readonly authService: AuthService,
  ) {}

  /**
   * GET /documents
   * Get list of documents with pagination and filtering
   * Story 4.5: 문서 목록 조회 API
   */
  @Get()
  @ResponseCode(RC.DOC_LIST_SUCCESS)
  @ApiOperation({ summary: '문서 목록 조회 (페이징 및 필터링)' })
  @ApiQuery({
    name: 'page',
    required: false,
    type: Number,
    description: 'Page number (default: 1)',
  })
  @ApiQuery({
    name: 'limit',
    required: false,
    type: Number,
    description: 'Items per page (default: 20, max: 100)',
  })
  @ApiQuery({
    name: 'status',
    required: false,
    enum: DocStatus,
    description: 'Filter by status',
  })
  @ApiQuery({
    name: 'favorite',
    required: false,
    type: Boolean,
    description: 'Filter by favorite status',
  })
  @ApiQuery({
    name: 'deptIds',
    required: false,
    type: [String],
    description:
      '조회할 부서 ID 목록 (접근 가능한 부서 내에서 선택). 미입력 시 본인 문서만 조회. 전사 공개 부서(env PUBLIC_DEPT_IDS) 문서는 입력 여부와 무관하게 항상 결과에 포함',
  })
  @ApiQuery({
    name: 'sort',
    required: false,
    enum: ['latest', 'oldest'],
    description:
      '정렬 순서 (latest: 최신순, oldest: 오래된순, default: latest)',
  })
  @ApiQuery({
    name: 'tagIds',
    required: false,
    type: [String],
    description:
      '내 태그 ID로 필터링 (콤마구분 또는 배열). 입력 태그 중 하나라도 매칭되는 문서 반환 (OR). 본인 태그가 아닌 ID는 무시됨',
  })
  @ApiQuery({
    name: 'keyword',
    required: false,
    type: String,
    description:
      '파일명 검색 키워드 (1~100자). 공백으로 토큰 분리 후 모든 토큰을 originalFilename ILIKE 로 AND 매칭 (예: "계약 매출" → "계약" AND "매출" 둘 다 포함)',
  })
  @ApiQuery({
    name: 'view',
    required: false,
    enum: ['mine', 'all', 'public', 'dept'],
    description:
      '조회 모드 (default: all). mine=본인 업로드만 | all=본인 부서+권한 부서+공개 부서 | public=공개 부서만 | dept=deptIds 지정 부서만(접근 가능한 것만, 공개/본인 자동포함 없음)',
  })
  @ApiResponse({
    status: 200,
    description: 'Document list retrieved successfully',
    schema: { example: Examples.DocumentListSuccessExample },
  })
  async findDocuments(
    @CurrentUser() user: AuthenticatedUser,
    @Query() query: DocumentListQueryDto,
  ) {
    const result = await this.documentService.findDocuments(
      user.userId,
      user.authDeptId,
      user.deptPermissions,
      query,
    );
    return {
      items: result.items,
      meta: result.meta,
    };
  }

  /**
   * GET /documents/summary
   * 문서 상태별 카운트 요약
   */
  @Get('summary')
  @ResponseCode(RC.DOC_SUMMARY_SUCCESS)
  @ApiOperation({
    summary: '문서 상태별 요약 통계',
    description:
      '내 문서 + 접근 가능한 부서 문서의 상태별 카운트를 반환합니다. 문서함 페이지 상단 통계 표시용입니다.',
  })
  @ApiResponse({
    status: 200,
    description: '요약 통계 조회 성공',
    schema: { example: Examples.DocumentSummarySuccessExample },
  })
  async getDocumentSummary(@CurrentUser() user: AuthenticatedUser) {
    const accessibleDeptIds = this.authService.getAccessibleDeptIds(
      user.authDeptId,
      user.deptPermissions,
    );
    const result = await this.documentService.getDocumentSummary(
      user.userId,
      accessibleDeptIds,
    );
    return { data: result };
  }

  /**
   * GET /documents/storage/list
   * List files in MinIO storage (raw/ prefix)
   * Debug endpoint for checking uploaded files
   */
  @Get('storage/list')
  @ResponseCode(RC.DOC_STORAGE_LIST_SUCCESS)
  @ApiOperation({ summary: 'MinIO 스토리지 파일 목록 조회 (raw/ 프리픽스)' })
  @ApiResponse({
    status: 200,
    description: 'Storage files listed successfully',
    schema: { example: Examples.StorageFileListSuccessExample },
  })
  async listStorageFiles() {
    const prefix = 'raw/';
    const files = await this.minioService.listObjects(prefix);
    return {
      data: files,
      bucket: this.minioService.getBucket(),
      prefix,
      count: files.length,
    };
  }

  /**
   * POST /documents/upload-session
   * Create upload session with pre-signed URLs for file upload
   * Story 4.2.1: UploaderGuard - uploader 또는 admin 권한 필요
   * AC1: Pre-signed URL 생성
   * AC4: 응답 형식
   */
  @Post('upload-session')
  @Authorities(AuthorityType.UPLOADER, AuthorityType.ADMIN)
  @ResponseCode(RC.DOC_UPLOAD_SESSION_CREATED)
  @ApiOperation({ summary: '업로드 세션 생성 (Pre-signed URL)' })
  @ApiBody({
    type: CreateUploadSessionDto,
    description: 'File metadata for creating upload session',
    examples: Examples.CreateUploadSessionBodyExamples,
  })
  @ApiResponse({
    status: 201,
    description: 'Upload session created with pre-signed URLs',
    schema: { example: Examples.CreateUploadSessionSuccessExample },
  })
  @ApiResponse({
    status: 413,
    description: 'File size exceeds 100MB limit',
  })
  @ApiResponse({
    status: 415,
    description: 'Unsupported media type',
  })
  async createUploadSession(
    @CurrentUser() user: AuthenticatedUser,
    @Body() dto: CreateUploadSessionDto,
  ) {
    const result = await this.documentService.createUploadSession(
      user.userId,
      dto,
    );
    return {
      data: result,
      message: '업로드 URL이 생성되었습니다',
    };
  }

  /**
   * POST /documents/:documentId/versions/:versionId/complete
   * Complete upload - sets status to 'uploaded'
   * Story 4.2.1: UploaderGuard - uploader 또는 admin 권한 필요
   * Story 4.4: 업로드 완료 API (임베딩은 별도 API로 분리됨)
   */
  @Post(':documentId/versions/:versionId/complete')
  @Authorities(AuthorityType.UPLOADER, AuthorityType.ADMIN)
  @ResponseCode(RC.DOC_UPLOAD_COMPLETE)
  @ApiOperation({ summary: '업로드 완료 처리 (상태: uploaded)' })
  @ApiResponse({
    status: 201,
    description: 'Upload completed successfully',
    schema: { example: Examples.CompleteUploadSuccessExample },
  })
  @ApiResponse({
    status: 404,
    description: 'Document or version not found',
  })
  @ApiResponse({
    status: 403,
    description: 'Access denied - not document owner',
  })
  async completeUpload(
    @CurrentUser() user: AuthenticatedUser,
    @Param('documentId', ParseUUIDPipe) documentId: string,
    @Param('versionId', ParseUUIDPipe) versionId: string,
  ) {
    const result = await this.documentService.completeUpload(
      user.userId,
      documentId,
      versionId,
    );
    return {
      data: result,
      message: '업로드가 완료되었습니다',
    };
  }

  /**
   * POST /documents/embed-requests/batch
   * 임베딩 승인 요청 일괄 (Story 4.15)
   */
  @Post('embed-requests/batch')
  @Authorities(
    AuthorityType.UPLOADER,
    AuthorityType.EMBEDDING,
    AuthorityType.ADMIN,
  )
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.EMBED_REQUEST_ACCEPTED)
  @ApiOperation({ summary: '임베딩 승인 일괄 요청 (uploader/embedding/admin)' })
  @ApiBody({
    schema: {
      type: 'object',
      required: ['versionIds'],
      properties: {
        versionIds: {
          type: 'array',
          items: { type: 'string', format: 'uuid' },
          description:
            '임베딩 승인을 요청할 doc_document_content.id 목록 (uploaded/rejected 상태만 가능)',
          example: [
            'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
            'v2b2c3d4-e5f6-7890-abcd-ef1234567890',
          ],
        },
      },
    },
  })
  @ApiResponse({
    status: 200,
    description: '일괄 임베딩 승인 요청 처리 결과',
    schema: { example: Examples.BulkRequestEmbeddingApprovalSuccessExample },
  })
  async bulkRequestEmbeddingApproval(
    @CurrentUser() user: AuthenticatedUser,
    @Body() body: { versionIds: string[] },
  ) {
    return this.documentService.bulkRequestEmbeddingApproval(
      body.versionIds,
      user.userId,
      user.authorities,
    );
  }

  /**
   * POST /documents/re-embed-requests/batch
   * 재임베딩 일괄 요청 (failed/completed → 바로 Embedding Server 호출)
   */
  @Post('re-embed-requests/batch')
  @Authorities(
    AuthorityType.UPLOADER,
    AuthorityType.EMBEDDING,
    AuthorityType.ADMIN,
  )
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.RE_EMBED_REQUEST_ACCEPTED)
  @ApiOperation({
    summary: '재임베딩 일괄 요청 (failed/completed 상태, 승인 불필요)',
  })
  @ApiBody({
    schema: {
      type: 'object',
      required: ['versionIds'],
      properties: {
        versionIds: {
          type: 'array',
          items: { type: 'string', format: 'uuid' },
          description:
            '재임베딩할 doc_document_content.id 목록 (failed/completed 상태만 가능)',
        },
      },
    },
  })
  @ApiResponse({
    status: 200,
    description: '재임베딩 요청 처리 결과',
    schema: { example: Examples.BulkRequestReEmbeddingSuccessExample },
  })
  async bulkRequestReEmbedding(
    @CurrentUser() user: AuthenticatedUser,
    @Body() body: { versionIds: string[] },
  ) {
    return this.documentService.bulkRequestReEmbedding(
      body.versionIds,
      user.userId,
      user.authorities,
    );
  }

  /**
   * GET /documents/embed-requests
   * 임베딩 승인 대기 목록 조회 (Story 4.15)
   */
  @Get('embed-requests')
  @Authorities(AuthorityType.EMBEDDING, AuthorityType.ADMIN)
  @ResponseCode(RC.EMBED_APPROVAL_LIST_SUCCESS)
  @ApiOperation({
    summary:
      '임베딩 목록 조회 (embedding/admin) — type: pending(기본)/approved/rejected',
  })
  @ApiQuery({ name: 'page', required: false, type: Number })
  @ApiQuery({ name: 'limit', required: false, type: Number })
  @ApiQuery({
    name: 'type',
    required: false,
    enum: ['pending', 'approved', 'rejected'],
    description: '목록 유형 (기본: pending)',
  })
  @ApiQuery({
    name: 'deptIds',
    required: false,
    type: [String],
    description: '부서 필터 (접근 가능한 부서 내 선택)',
  })
  @ApiResponse({
    status: 200,
    description: '임베딩 승인 대기 목록',
    schema: { example: Examples.GetEmbedRequestsSuccessExample },
  })
  async getEmbedRequests(
    @CurrentUser() user: AuthenticatedUser,
    @Query('page') page?: number,
    @Query('limit') limit?: number,
    @Query('type') type?: 'pending' | 'approved' | 'rejected',
    @Query('deptIds') deptIds?: string | string[],
  ) {
    const isAdmin = user.authorities.includes(AuthorityType.ADMIN);
    const accessibleDeptIds = this.authService.getAccessibleDeptIds(
      user.authDeptId,
      user.deptPermissions,
    );
    const deptIdsArray = deptIds
      ? Array.isArray(deptIds)
        ? deptIds
        : [deptIds]
      : undefined;
    return this.documentService.getEmbedRequests(
      isAdmin,
      accessibleDeptIds,
      page,
      limit,
      type ?? 'pending',
      deptIdsArray,
    );
  }

  /**
   * PATCH /documents/embed-requests
   * 임베딩 일괄 승인 (Story 4.15)
   */
  @Patch('embed-requests')
  @Authorities(AuthorityType.EMBEDDING, AuthorityType.ADMIN)
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.EMBED_APPROVE_SUCCESS)
  @ApiOperation({ summary: '임베딩 요청 일괄 승인 (embedding/admin)' })
  @ApiBody({
    schema: {
      type: 'object',
      required: ['versionIds'],
      properties: {
        versionIds: {
          type: 'array',
          items: { type: 'string', format: 'uuid' },
          example: [
            'v1b2c3d4-e5f6-7890-abcd-ef1234567890',
            'v2b2c3d4-e5f6-7890-abcd-ef1234567890',
          ],
        },
      },
    },
  })
  @ApiResponse({
    status: 200,
    description: '일괄 승인 완료',
    schema: { example: Examples.BulkApproveEmbeddingSuccessExample },
  })
  async bulkApproveEmbedding(
    @CurrentUser() user: AuthenticatedUser,
    @Body() body: { versionIds: string[] },
  ) {
    return this.documentService.bulkApproveEmbedding(
      body.versionIds,
      user.userId,
    );
  }

  /**
   * PATCH /documents/embed-requests/reject
   * 임베딩 일괄 거절 (Story 4.15)
   */
  @Patch('embed-requests/reject')
  @Authorities(AuthorityType.EMBEDDING, AuthorityType.ADMIN)
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.EMBED_REJECT_SUCCESS)
  @ApiOperation({ summary: '임베딩 요청 일괄 거절 (embedding/admin)' })
  @ApiBody({
    schema: {
      type: 'object',
      required: ['items'],
      properties: {
        items: {
          type: 'array',
          items: {
            type: 'object',
            required: ['versionId'],
            properties: {
              versionId: { type: 'string', format: 'uuid' },
              reason: {
                type: 'string',
                example: '내용 보완 필요',
                nullable: true,
              },
            },
          },
          description: '거절할 문서 목록 (각각 개별 사유 입력 가능)',
        },
      },
    },
  })
  @ApiResponse({
    status: 200,
    description: '일괄 거절 완료',
    schema: { example: Examples.BulkRejectEmbeddingSuccessExample },
  })
  async bulkRejectEmbedding(
    @CurrentUser() user: AuthenticatedUser,
    @Body() body: { items: { versionId: string; reason?: string }[] },
  ) {
    return this.documentService.bulkRejectEmbedding(
      body.items,
      user.userId,
    );
  }

  // ============================================================
  // Wildcard param routes — MUST be below all literal path routes
  // ============================================================

  /**
   * GET /documents/:documentId
   * Get document detail with version history
   * Story 4.6: 문서 상태 조회 API
   */
  @Get(':documentId')
  @ResponseCode(RC.DOC_DETAIL_SUCCESS)
  @ApiOperation({ summary: '문서 상세 및 버전 히스토리 조회' })
  @ApiResponse({
    status: 200,
    description: 'Document detail retrieved successfully',
    schema: { example: Examples.DocumentDetailSuccessExample },
  })
  @ApiResponse({
    status: 404,
    description: 'Document not found',
  })
  @ApiResponse({
    status: 403,
    description: 'Access denied - not document owner',
  })
  async findOne(
    @CurrentUser() user: AuthenticatedUser,
    @Param('documentId', ParseUUIDPipe) documentId: string,
  ) {
    const result = await this.documentService.findOne(
      user.userId,
      documentId,
      user.authorities,
    );
    return {
      data: result,
    };
  }

  /**
   * PATCH /documents/contents/:contentId/reference
   * Toggle document RAG reference ON/OFF
   */
  @HttpCode(HttpStatus.OK)
  @Patch('versions/:contentId/reference')
  @ResponseCode(RC.DOC_REFERENCE_TOGGLED)
  @ApiOperation({ summary: '문서 RAG 참조 ON/OFF 토글' })
  @ApiResponse({
    status: 200,
    description: '토글 성공',
    schema: { example: Examples.ToggleReferenceSuccessExample },
  })
  @ApiResponse({ status: 404, description: '문서 버전 없음' })
  async toggleReference(
    @CurrentUser() user: AuthenticatedUser,
    @Param('contentId', ParseUUIDPipe) contentId: string,
  ) {
    const result = await this.documentService.toggleDocumentReference(
      user.userId,
      contentId,
    );
    return { data: result };
  }

  /**
   * GET /documents/:documentId/versions/:versionId/download
   * Get pre-signed download URL for a document version
   * Story 4.8: 문서 다운로드 API
   */
  @Get('versions/:versionId/download')
  @Authorities(AuthorityType.DOWNLOAD, AuthorityType.ADMIN)
  @ResponseCode(RC.DOC_DOWNLOAD_URL_SUCCESS)
  @ApiOperation({ summary: '문서 다운로드 URL 생성 (Pre-signed GET URL)' })
  @ApiResponse({
    status: 200,
    description: 'Download URL generated successfully',
    schema: { example: Examples.DownloadUrlSuccessExample },
  })
  @ApiResponse({
    status: 404,
    description: 'Version not found',
  })
  @ApiResponse({
    status: 403,
    description: 'Access denied - not document owner',
  })
  async getDownloadUrl(
    @CurrentUser() user: AuthenticatedUser,
    @Param('versionId', ParseUUIDPipe) versionId: string,
  ) {
    const result = await this.documentService.getDownloadUrl(
      user.userId,
      user.deptPermissions,
      user.authDeptId,
      versionId,
    );
    return {
      data: result,
    };
  }

  /**
   * POST /documents/:documentId/favorite
   * Add document to favorites
   * Story 4.9: 문서 즐겨찾기 API
   */
  @Post(':documentId/favorite')
  @ResponseCode(RC.DOC_FAVORITE_ADDED)
  @ApiOperation({ summary: '문서 즐겨찾기 추가' })
  @ApiResponse({
    status: 201,
    description: 'Document added to favorites',
    schema: { example: Examples.AddFavoriteSuccessExample },
  })
  @ApiResponse({
    status: 404,
    description: 'Document not found',
  })
  @ApiResponse({
    status: 409,
    description: 'Document is already in favorites',
  })
  async addFavorite(
    @CurrentUser() user: AuthenticatedUser,
    @Param('documentId', ParseUUIDPipe) documentId: string,
  ) {
    await this.documentService.addFavorite(user.userId, documentId);
    return {
      message: '즐겨찾기에 추가되었습니다',
    };
  }

  /**
   * DELETE /documents/:documentId/favorite
   * Remove document from favorites
   * Story 4.9: 문서 즐겨찾기 API
   */
  @Delete(':documentId/favorite')
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.DOC_FAVORITE_REMOVED)
  @ApiOperation({ summary: '문서 즐겨찾기 해제' })
  @ApiResponse({
    status: 200,
    description: 'Document removed from favorites',
    schema: { example: Examples.RemoveFavoriteSuccessExample },
  })
  @ApiResponse({
    status: 404,
    description: 'Document is not in favorites',
  })
  async removeFavorite(
    @CurrentUser() user: AuthenticatedUser,
    @Param('documentId', ParseUUIDPipe) documentId: string,
  ) {
    await this.documentService.removeFavorite(user.userId, documentId);
    return {
      message: '즐겨찾기가 해제되었습니다',
    };
  }

  // ============================================================
  // SSE Endpoints - Story 4.10
  // ============================================================

  /**
   * GET /documents/:documentId/status/stream
   * SSE endpoint for real-time embedding status updates
   * Story 4.10: Kafka 상태 Consumer + SSE 스트리밍
   * AC3: SSE 엔드포인트
   * AC4: SSE 인증 (Query parameter JWT)
   */
  @Public()
  @Get(':documentId/status/stream')
  @Sse()
  @ApiOperation({ summary: '문서 임베딩 상태 실시간 스트리밍 (SSE)' })
  @ApiQuery({
    name: 'token',
    required: true,
    description: 'JWT access token for authentication',
  })
  @ApiResponse({
    status: 200,
    description: 'SSE stream established',
  })
  @ApiResponse({
    status: 401,
    description: 'Invalid or missing token',
  })
  @ApiResponse({
    status: 403,
    description: 'Access denied - not document owner or admin',
  })
  @ApiResponse({
    status: 404,
    description: 'Document not found',
  })
  statusStream(
    @Param('documentId', ParseUUIDPipe) documentId: string,
    @Query('token') token: string,
  ): Observable<MessageEvent> {
    return new Observable((subscriber) => {
      let userId: string | null = null;

      (async () => {
        try {
          // AC4: JWT 토큰 검증
          if (!token) {
            throw new UnauthorizedException('Token is required');
          }

          let payload: { sub: string; authorities?: AuthorityType[] };
          try {
            payload = this.jwtService.verify(token);
          } catch {
            throw new UnauthorizedException('Invalid or expired token');
          }

          userId = payload.sub;
          const authorities = payload.authorities || [];

          // AC3: 권한 검증 (ADMIN 또는 소유자)
          const document = await this.documentService.findOne(
            userId,
            documentId,
            authorities as string[],
          );
          if (!document) {
            throw new BusinessException(
              RC.DOC_NOT_FOUND,
              undefined,
              getHttpStatus(RC.DOC_NOT_FOUND),
            );
          }

          // findOne에서 이미 소유자 검증됨, admin 추가 확인
          const isOwner = document.createdBy === userId;
          const isAdmin = authorities.includes(AuthorityType.ADMIN);

          if (!isOwner && !isAdmin) {
            throw new BusinessException(
              RC.DOC_FORBIDDEN,
              undefined,
              getHttpStatus(RC.DOC_FORBIDDEN),
            );
          }

          this.logger.debug(
            `SSE connection established: documentId=${documentId}, userId=${userId}`,
          );

          // 연결 성공 이벤트 전송
          subscriber.next({
            type: 'connected',
            data: JSON.stringify({
              success: true,
              code: RC.EVENT_SUBSCRIBE_SUCCESS,
              message: ResponseMessage[RC.EVENT_SUBSCRIBE_SUCCESS],
              data: { documentId },
            }),
          });

          // 상태 스트림 구독
          const statusSubscription = this.embeddingStatusGateway
            .subscribe(documentId, userId)
            .subscribe({
              next: (event) => subscriber.next(event),
              error: (err) => {
                this.logger.error(`Status stream error: ${err.message}`);
                subscriber.next({
                  type: 'error',
                  data: JSON.stringify({
                    success: false,
                    code: 'BKN05500',
                    message: 'Status stream error',
                    data: { error: err.message },
                  }),
                });
              },
              complete: () => {
                subscriber.complete();
              },
            });

          // 클라이언트 연결 해제 시 정리
          return () => {
            this.logger.debug(
              `SSE connection closed: documentId=${documentId}, userId=${userId}`,
            );
            statusSubscription.unsubscribe();
            if (userId) {
              this.embeddingStatusGateway.unsubscribe(documentId, userId);
            }
          };
        } catch (error) {
          const err = error as Error;
          this.logger.error(`SSE connection error: ${err.message}`);

          // 에러 응답 전송 후 종료
          if (
            error instanceof UnauthorizedException ||
            error instanceof BusinessException
          ) {
            subscriber.next({
              type: 'error',
              data: JSON.stringify({
                success: false,
                code:
                  error instanceof BusinessException
                    ? error.code
                    : RC.UNAUTHORIZED,
                message: err.message,
                data: null,
              }),
            });
          }
          subscriber.complete();
        }
      })();

      // Cleanup function
      return () => {
        if (userId) {
          this.embeddingStatusGateway.unsubscribe(documentId, userId);
        }
      };
    });
  }

  /**
   * PUT /documents/:documentId/tags
   * 문서에 부여된 내 태그를 일괄 교체 (Story 4.16)
   */
  @Put(':documentId/tags')
  @ResponseCode(RC.DOC_TAG_SUCCESS)
  @ApiOperation({
    summary: '문서 태그 일괄 설정 (기존 매핑 대체)',
    description:
      '본인 소유 태그만 사용할 수 있으며, 본인 문서 또는 접근 가능한 부서 문서에만 부여 가능합니다. 전송한 tagIds 배열로 기존 매핑을 통째 교체합니다 (빈 배열로 호출 시 모든 태그 해제).',
  })
  @ApiBody({ type: SetDocumentTagsDto })
  @ApiResponse({
    status: 200,
    description: '문서에 부여된 내 태그 (교체 후 최신 상태)',
    schema: { example: Examples.SetDocumentTagsSuccessExample },
  })
  @ApiResponse({
    status: 403,
    description:
      '본인 문서/접근 가능 부서 문서가 아니거나, 본인 태그 ID가 아닌 값이 섞여있음',
    schema: { example: Examples.SetDocumentTagsForbiddenExample },
  })
  @ApiResponse({
    status: 404,
    description: '존재하지 않는 태그 ID 포함',
    schema: { example: Examples.SetDocumentTagsNotFoundExample },
  })
  async setDocumentTags(
    @CurrentUser() user: AuthenticatedUser,
    @Param('documentId', new ParseUUIDPipe()) documentId: string,
    @Body() dto: SetDocumentTagsDto,
  ) {
    const myTags = await this.documentTagsService.setDocumentTags(
      user.userId,
      user.authDeptId,
      user.deptPermissions,
      documentId,
      dto.tagIds,
    );
    return { documentId, myTags };
  }
}
