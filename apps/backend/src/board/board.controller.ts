import {
  Controller,
  Get,
  Post,
  Body,
  Param,
  Query,
  ParseUUIDPipe,
} from '@nestjs/common';
import {
  ApiTags,
  ApiBearerAuth,
  ApiOperation,
  ApiResponse,
  ApiParam,
  ApiQuery,
  ApiBody,
} from '@nestjs/swagger';
import { BoardService } from './board.service';
import {
  CreatePostDto,
  CreateReplyDto,
  PostListQueryDto,
  PresignedUrlRequestDto,
} from './dto/board.dto';
import { CreateSurveyDto } from './dto/board-survey.dto';
import { ResponseCode as RC } from '../common/constants/response-codes';
import { ResponseCode } from '../common/decorators/response-code.decorator';
import { CurrentUser } from '../auth/decorators/current-user.decorator';
import type { AuthenticatedUser } from '../auth/types/authenticated-user';
import * as Examples from './swagger-examples/board.examples';

@ApiTags('Board')
@ApiBearerAuth()
@Controller('board')
export class BoardController {
  constructor(private readonly boardService: BoardService) {}

  // ============================================================
  // Board Types
  // ============================================================

  @Get('types')
  @ResponseCode(RC.BOARD_TYPE_LIST_SUCCESS)
  @ApiOperation({
    summary: '게시판 타입 목록 조회',
    description:
      '게시판 타입 목록을 조회합니다. name 파라미터로 특정 타입만 조회 가능합니다. (feedback, notice)',
  })
  @ApiQuery({
    name: 'name',
    required: false,
    enum: ['feedback', 'suggestion', 'answer_suggestion'],
    description: '게시판 타입 이름 필터',
  })
  @ApiResponse({
    status: 200,
    description: '게시판 타입 목록 조회 성공',
    schema: { example: Examples.GetBoardTypesSuccessExample },
  })
  async getBoardTypes(@Query('name') name?: string) {
    return this.boardService.getBoardTypes(name);
  }

  // ============================================================
  // Post CRUD
  // ============================================================

  @Post('posts')
  @ResponseCode(RC.BOARD_POST_CREATED)
  @ApiOperation({
    summary: '게시글 작성',
    description:
      '게시판에 새 게시글을 작성합니다. 이미지는 presigned-url로 먼저 업로드 후 objectKey를 전달합니다.',
  })
  @ApiBody({ type: CreatePostDto })
  @ApiResponse({
    status: 201,
    description: '게시글 작성 성공',
    schema: { example: Examples.CreatePostSuccessExample },
  })
  async createPost(
    @CurrentUser() user: AuthenticatedUser,
    @Body() dto: CreatePostDto,
  ) {
    return this.boardService.createPost(user.userId, user.authorities, dto);
  }

  @Get('posts')
  @ResponseCode(RC.BOARD_POST_LIST_SUCCESS)
  @ApiOperation({
    summary: '게시글 목록 조회',
    description:
      '게시글 목록을 페이징 조회합니다. ADMIN 권한은 전체 글 조회, 일반 사용자는 본인 글만 조회됩니다.',
  })
  @ApiQuery({
    name: 'page',
    required: false,
    example: 1,
    description: '페이지 번호 (기본값: 1)',
  })
  @ApiQuery({
    name: 'limit',
    required: false,
    example: 20,
    description: '페이지당 항목 수 (기본값: 20, 최대: 100)',
  })
  @ApiQuery({
    name: 'boardTypeId',
    required: false,
    example: 'b1b2c3d4-e5f6-7890-abcd-ef1234567890',
    description: '게시판 타입 UUID 필터',
  })
  @ApiResponse({
    status: 200,
    description: '게시글 목록 조회 성공',
    schema: { example: Examples.GetPostListSuccessExample },
  })
  async getPostList(
    @CurrentUser() user: AuthenticatedUser,
    @Query() query: PostListQueryDto,
  ) {
    return this.boardService.getPostList(user.userId, user.authorities, query);
  }

  @Get('posts/:postId')
  @ResponseCode(RC.BOARD_POST_DETAIL_SUCCESS)
  @ApiOperation({
    summary: '게시글 상세 조회',
    description:
      '게시글 상세 내용과 이미지 목록을 조회합니다. ADMIN 권한은 전체, 일반 사용자는 본인 글만 조회 가능합니다.',
  })
  @ApiParam({
    name: 'postId',
    description: '게시글 UUID',
    example: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  })
  @ApiResponse({
    status: 200,
    description: '게시글 상세 조회 성공',
    schema: { example: Examples.GetPostDetailSuccessExample },
  })
  @ApiResponse({ status: 404, description: '게시글을 찾을 수 없음' })
  async getPostDetail(
    @CurrentUser() user: AuthenticatedUser,
    @Param('postId', ParseUUIDPipe) postId: string,
  ) {
    return this.boardService.getPostDetail(
      user.userId,
      user.authorities,
      postId,
    );
  }

  // ============================================================
  // Reply (답변)
  // ============================================================

  @Post('posts/:postId/comments')
  @ResponseCode(RC.BOARD_REPLY_CREATED)
  @ApiOperation({
    summary: '게시글 댓글 작성 (현재 ADMIN 전용)',
    description:
      '게시글에 댓글을 작성합니다. 현재 피드백 게시판은 ADMIN만 작성 가능하며 1개의 댓글만 허용됩니다.',
  })
  @ApiParam({
    name: 'postId',
    description: '게시글 UUID',
    example: 'a1b2c3d4-e5f6-7890-abcd-ef1234567890',
  })
  @ApiBody({ type: CreateReplyDto })
  @ApiResponse({
    status: 201,
    description: '답변 등록 성공',
    schema: { example: Examples.CreateReplySuccessExample },
  })
  @ApiResponse({ status: 403, description: 'ADMIN 권한 없음' })
  @ApiResponse({ status: 404, description: '게시글을 찾을 수 없음' })
  @ApiResponse({ status: 409, description: '이미 답변이 존재함' })
  async createReply(
    @CurrentUser() user: AuthenticatedUser,
    @Param('postId', ParseUUIDPipe) postId: string,
    @Body() dto: CreateReplyDto,
  ) {
    return this.boardService.createReply(
      user.userId,
      user.authorities,
      postId,
      dto,
    );
  }

  // ============================================================
  // Presigned URL
  // ============================================================

  @Post('presigned-url')
  @ResponseCode(RC.BOARD_PRESIGNED_URL_SUCCESS)
  @ApiOperation({
    summary: '이미지 업로드 Presigned URL 발급',
    description:
      '게시글 이미지 업로드를 위한 MinIO Presigned PUT URL을 발급합니다. 발급된 URL로 직접 업로드 후 objectKey를 게시글 작성 시 전달합니다.',
  })
  @ApiBody({ type: PresignedUrlRequestDto })
  @ApiResponse({
    status: 201,
    description: 'Presigned URL 발급 성공',
    schema: { example: Examples.GetPresignedUrlSuccessExample },
  })
  async getPresignedUrl(@Body() dto: PresignedUrlRequestDto) {
    return this.boardService.generatePresignedUrl(dto.filename, dto.boardTypeName);
  }

  // ============================================================
  // Survey
  // ============================================================

  @Post('surveys')
  @ResponseCode(RC.BOARD_SURVEY_SUBMITTED)
  @ApiOperation({
    summary: '설문 제출',
    description:
      '사용자 만족도 설문을 제출합니다. 복수 제출 가능합니다. 모든 점수 항목은 1~5 정수입니다.',
  })
  @ApiBody({ type: CreateSurveyDto })
  @ApiResponse({
    status: 201,
    description: '설문 제출 성공',
    schema: { example: Examples.SubmitSurveySuccessExample },
  })
  @ApiResponse({ status: 409, description: '이미 설문을 제출한 사용자' })
  async submitSurvey(
    @CurrentUser() user: AuthenticatedUser,
    @Body() dto: CreateSurveyDto,
  ) {
    return this.boardService.submitSurvey(user.userId, dto);
  }
}
