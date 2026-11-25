import {
  Controller,
  Get,
  Post,
  Put,
  Patch,
  Delete,
  Body,
  Param,
  Query,
  HttpCode,
  HttpStatus,
  ParseUUIDPipe,
} from '@nestjs/common';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiCookieAuth,
  ApiQuery,
  ApiBody,
} from '@nestjs/swagger';
import { AdminService } from './admin.service';
import { ActivityService } from './activity.service';
import { AdoptionService } from './adoption.service';
import { ActivityListQueryDto } from './dto/activity.dto';
import { AdoptPostDto } from './dto/adoption.dto';
import { DocumentService } from '../document/document.service';
import { Authorities } from '../auth/decorators/authorities.decorator';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import type { AuthenticatedUser } from '../auth/types/authenticated-user';
import {
  UserListQueryDto,
  GrantAuthoritiesDto,
  RevokeAuthoritiesDto,
  SetDeptPermissionsDto,
} from './dto/admin.dto';
import { AdminDocumentListQueryDto } from './dto/admin-document.dto';
import { ResponseCode } from '../common/decorators/response-code.decorator';
import { ResponseCode as RC } from '../common/constants/response-codes';
import { AuthorityType, DocStatus } from '../common/enums';
import * as Examples from './swagger-examples/admin.examples';

@ApiTags('admin')
@ApiCookieAuth()
@Controller('admin')
@Authorities(AuthorityType.ADMIN)
export class AdminController {
  constructor(
    private readonly adminService: AdminService,
    private readonly activityService: ActivityService,
    private readonly adoptionService: AdoptionService,
    private readonly documentService: DocumentService,
  ) {}

  /**
   * Story 3.8 — Task 8: suggestion 게시글 채택 (평가위원회 결과 입력)
   * PATCH /api/admin/board/posts/:postId/adoption
   */
  @Patch('board/posts/:postId/adoption')
  @Authorities(AuthorityType.EMBEDDING, AuthorityType.ADMIN)
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.ADMIN_BOARD_ADOPTION_SUCCESS)
  @ApiOperation({
    summary: '서비스 제안 채택 (embedding/admin) — 권한 임시',
    description:
      'suggestion 게시판 글에 채택 등급(50~200) 부여. 같은 글에 다시 호출하면 UPSERT. ⚠️ 권한은 추후 평가위원회 전용 권한으로 분리 예정 (임시로 embedding 권한 사용).',
  })
  @ApiBody({
    schema: {
      type: 'object',
      required: ['grade'],
      properties: {
        grade: { type: 'integer', minimum: 50, maximum: 200, example: 150 },
      },
    },
  })
  @ApiResponse({
    status: 200,
    description: '채택 완료',
    schema: { example: Examples.AdoptPostSuccessExample },
  })
  @ApiResponse({ status: 400, description: 'suggestion 게시판 글이 아님' })
  @ApiResponse({ status: 404, description: '게시글 없음' })
  async adoptPost(
    @CurrentUser() user: AuthenticatedUser,
    @Param('postId', ParseUUIDPipe) postId: string,
    @Body() dto: AdoptPostDto,
  ) {
    const adoption = await this.adoptionService.adopt(
      postId,
      dto.grade,
      user.userId,
    );
    return {
      data: {
        postId: adoption.postId,
        grade: adoption.grade,
        reviewerId: adoption.reviewerId,
        reviewedAt: adoption.reviewedAt,
      },
    };
  }

  /**
   * Story 3.8: 사용자 활동 모니터링 - 전체 랭킹 조회
   */
  @Get('activity')
  @ResponseCode(RC.ADMIN_ACTIVITY_SUCCESS)
  @ApiOperation({ summary: '사용자 활동 모니터링 랭킹 조회 (ADMIN 전용)' })
  @ApiQuery({ name: 'page', required: false, type: Number })
  @ApiQuery({ name: 'limit', required: false, type: Number })
  @ApiResponse({
    status: 200,
    description: '사용자 활동 모니터링 랭킹',
    schema: { example: Examples.GetActivityListSuccessExample },
  })
  async getActivityList(@Query() query: ActivityListQueryDto) {
    const result = await this.activityService.getActivityList(
      query.page ?? 1,
      query.limit ?? 20,
    );
    return { items: result.items, meta: result.meta };
  }

  /**
   * Story 3.8: 사용자 활동 모니터링 - 사용자 상세 조회
   */
  @Get('activity/:userId')
  @ResponseCode(RC.ADMIN_ACTIVITY_SUCCESS)
  @ApiOperation({ summary: '사용자 활동 상세 조회 (ADMIN 전용)' })
  @ApiResponse({
    status: 200,
    description: '사용자 활동 상세 (Persona / Heritage / EXpert 분리)',
    schema: { example: Examples.GetActivityDetailSuccessExample },
  })
  @ApiResponse({ status: 404, description: '사용자 활동 데이터 없음' })
  async getActivityDetail(@Param('userId', ParseUUIDPipe) userId: string) {
    const data = await this.activityService.getActivityByUserId(userId);
    return { data };
  }

  /**
   * Story 3.8: 사용자 활동 모니터링 - 수동 갱신
   */
  @Post('activity/refresh')
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.ADMIN_ACTIVITY_REFRESH_SUCCESS)
  @ApiOperation({ summary: '사용자 활동 데이터 수동 갱신 (ADMIN 전용)' })
  @ApiResponse({
    status: 200,
    description: '갱신 완료',
    schema: { example: Examples.RefreshActivitySuccessExample },
  })
  async refreshActivity() {
    const refreshedAt = await this.activityService.refresh();
    return { data: { refreshedAt } };
  }

  /**
   * Story 3.2: 사용자 목록 조회 API
   */
  @Get('users')
  @ResponseCode(RC.ADMIN_USER_LIST_SUCCESS)
  @ApiOperation({ summary: '사용자 목록 조회 (관리자 전용)' })
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
    name: 'search',
    required: false,
    type: String,
    description: '이름 또는 이메일 검색 (ILIKE, 검색 시 페이지네이션 무시)',
  })
  @ApiResponse({
    status: 200,
    description: '사용자 목록 반환',
    schema: { example: Examples.GetUserListSuccessExample },
  })
  @ApiResponse({ status: 403, description: '관리자 권한 필요' })
  async getUserList(@Query() query: UserListQueryDto) {
    const { data, total, page, limit } =
      await this.adminService.getUserList(query);
    return {
      items: data,
      meta: {
        total,
        page,
        limit,
        totalPages: Math.ceil(total / limit),
      },
    };
  }

  /**
   * Story 3.3: 권한 일괄 부여 API
   */
  @Post('users/authorities')
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.ADMIN_AUTHORITY_GRANTED)
  @ApiOperation({ summary: '사용자에게 권한 일괄 부여 (관리자 전용)' })
  @ApiResponse({
    status: 200,
    description: '권한 일괄 부여 성공',
    schema: { example: Examples.GrantAuthoritiesSuccessExample },
  })
  @ApiBody({ type: GrantAuthoritiesDto })
  @ApiResponse({ status: 404, description: '사용자 또는 권한을 찾을 수 없음' })
  async grantAuthorities(@Body() dto: GrantAuthoritiesDto) {
    return this.adminService.grantAuthorities(dto);
  }

  /**
   * Story 3.4: 권한 일괄 회수 API
   */
  @Delete('users/authorities')
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.ADMIN_AUTHORITY_REVOKED)
  @ApiOperation({ summary: '사용자 권한 일괄 회수 (관리자 전용)' })
  @ApiResponse({
    status: 200,
    description: '권한 일괄 회수 성공',
    schema: { example: Examples.RevokeAuthoritiesSuccessExample },
  })
  @ApiBody({ type: RevokeAuthoritiesDto })
  @ApiResponse({ status: 404, description: '사용자 또는 권한을 찾을 수 없음' })
  async revokeAuthorities(@Body() dto: RevokeAuthoritiesDto) {
    return this.adminService.revokeAuthorities(dto);
  }

  /**
   * Story 3.5: 권한 목록 조회 API
   */
  @Get('authorities')
  @ResponseCode(RC.ADMIN_AUTHORITY_LIST_SUCCESS)
  @ApiOperation({ summary: '시스템 권한 목록 조회 (관리자 전용)' })
  @ApiResponse({
    status: 200,
    description: '권한 목록 반환',
    schema: { example: Examples.GetAuthorityListSuccessExample },
  })
  async getAuthorityList() {
    return this.adminService.getAuthorityList();
  }

  /**
   * 전체 부서 목록 조회
   */
  @Get('departments')
  @ResponseCode(RC.ADMIN_DEPT_LIST_SUCCESS)
  @ApiOperation({ summary: '전체 부서 목록 조회 (관리자 전용)' })
  @ApiResponse({
    status: 200,
    description: '부서 목록 반환',
    schema: { example: Examples.GetDeptListSuccessExample },
  })
  async getDeptList() {
    return this.adminService.getDeptList();
  }

  /**
   * 사용자 부서 권한 일괄 설정 (PUT - 덮어쓰기)
   */
  @Put('users/:userId/dept-permissions')
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.ADMIN_DEPT_PERMISSION_SET)
  @ApiOperation({
    summary: '사용자 부서 권한 일괄 설정 (관리자 전용)',
    description:
      '기존 부서 권한을 전부 삭제하고 전달된 목록으로 교체합니다. 빈 배열 전송 시 전체 제거됩니다.',
  })
  @ApiResponse({
    status: 200,
    description: '부서 권한 설정 성공',
    schema: { example: Examples.SetDeptPermissionsSuccessExample },
  })
  @ApiBody({ type: SetDeptPermissionsDto })
  @ApiResponse({ status: 404, description: '사용자 또는 부서를 찾을 수 없음' })
  async setDeptPermissions(
    @Param('userId', ParseUUIDPipe) userId: string,
    @Body() dto: SetDeptPermissionsDto,
  ) {
    const result = await this.adminService.setDeptPermissions(
      userId,
      dto.deptIds,
    );
    return { data: result };
  }

  /**
   * 사용자 부서 권한 조회
   */
  @Get('users/:userId/departments')
  @ResponseCode(RC.ADMIN_DEPT_PERMISSION_LIST_SUCCESS)
  @ApiOperation({ summary: '사용자 부서 권한 조회 (관리자 전용)' })
  @ApiResponse({
    status: 200,
    description: '사용자 부서 권한 목록 반환',
    schema: { example: Examples.GetUserDeptPermissionsSuccessExample },
  })
  @ApiResponse({ status: 404, description: '사용자를 찾을 수 없음' })
  async getUserDeptPermissions(@Param('userId', ParseUUIDPipe) userId: string) {
    return this.adminService.getUserDeptPermissions(userId);
  }

  /**
   * Story 4.12: 관리자 문서 목록 조회 API
   * 모든 사용자의 문서 목록을 조회 (삭제된 문서 포함)
   */
  @Get('documents')
  @ResponseCode(RC.ADMIN_DOC_LIST_SUCCESS)
  @ApiOperation({
    summary: '관리자 문서 목록 조회 (모든 사용자, 삭제된 문서 포함)',
  })
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
    name: 'deletedOnly',
    required: false,
    type: Boolean,
    description: 'Show only deleted documents',
  })
  @ApiQuery({
    name: 'sort',
    required: false,
    enum: ['latest', 'oldest'],
    description:
      '정렬 순서 (latest: 최신순, oldest: 오래된순, default: latest)',
  })
  @ApiQuery({
    name: 'deptIds',
    required: false,
    type: [String],
    description: '부서 필터 (미입력 시 전체 조회)',
  })
  @ApiResponse({
    status: 200,
    description: '관리자 문서 목록 반환',
    schema: { example: Examples.GetDocumentListSuccessExample },
  })
  @ApiResponse({ status: 403, description: '관리자 권한 필요' })
  async getDocumentList(@Query() query: AdminDocumentListQueryDto) {
    const result = await this.documentService.findAllDocumentsForAdmin(query);
    return { items: result.data, meta: result.meta };
  }

  /**
   * Admin Soft Delete document
   * DELETE /admin/documents/:documentId/soft
   */
  @Delete('documents/:documentId/soft')
  @Authorities(AuthorityType.ADMIN, AuthorityType.SOFT_DELETE)
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.ADMIN_DOC_SOFT_DELETE_SUCCESS)
  @ApiOperation({ summary: '관리자 문서 Soft Delete' })
  @ApiResponse({
    status: 200,
    description: 'Document soft deleted',
    schema: { example: Examples.SoftDeleteDocumentSuccessExample },
  })
  @ApiResponse({ status: 404, description: 'Document not found' })
  async softDeleteDocument(
    @CurrentUser() user: AuthenticatedUser,
    @Param('documentId', ParseUUIDPipe) documentId: string,
  ) {
    await this.documentService.deleteDocument(user.userId, documentId, [
      AuthorityType.ADMIN,
    ]);
    return { message: '문서가 Soft Delete 되었습니다' };
  }

  /**
   * Admin Hard Delete document
   * DELETE /admin/documents/:documentId/hard
   */
  @Delete('documents/:documentId/hard')
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.ADMIN_DOC_HARD_DELETE_SUCCESS)
  @ApiOperation({ summary: '관리자 문서 Hard Delete (영구 삭제)' })
  @ApiResponse({
    status: 200,
    description: 'Document permanently deleted',
    schema: { example: Examples.HardDeleteDocumentSuccessExample },
  })
  @ApiResponse({ status: 404, description: 'Document not found' })
  async hardDeleteDocument(
    @Param('documentId', ParseUUIDPipe) documentId: string,
  ) {
    await this.documentService.hardDeleteDocument(documentId);
    return { message: '문서가 영구 삭제되었습니다' };
  }
}
