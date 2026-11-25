import {
  Controller,
  Get,
  Post,
  Patch,
  Delete,
  Body,
  Param,
  ParseUUIDPipe,
  HttpCode,
  HttpStatus,
} from '@nestjs/common';
import {
  ApiTags,
  ApiBearerAuth,
  ApiOperation,
  ApiResponse,
  ApiBody,
} from '@nestjs/swagger';
import { DocumentTagsService } from '../services/document-tags.service';
import { CreateTagDto, UpdateTagDto } from '../dto/document-tag.dto';
import { ResponseCode } from '../../common/decorators/response-code.decorator';
import { ResponseCode as RC } from '../../common/constants/response-codes';
import { CurrentUser } from '../../auth/decorators/current-user.decorator';
import type { AuthenticatedUser } from '../../auth/types/authenticated-user';
import * as Examples from '../swagger-examples/document-tags.examples';

@ApiTags('document-tags')
@ApiBearerAuth()
@Controller('document-tags')
export class DocumentTagsController {
  constructor(private readonly tagsService: DocumentTagsService) {}

  /**
   * GET /document-tags
   * 내 태그 목록 조회 (Story 4.16)
   */
  @Get()
  @ResponseCode(RC.DOC_TAG_SUCCESS)
  @ApiOperation({
    summary: '내 태그 목록 조회',
    description:
      '본인이 생성한 문서 분류 태그 목록을 이름 오름차순으로 반환합니다.',
  })
  @ApiResponse({
    status: 200,
    description: '내 태그 목록',
    schema: { example: Examples.ListTagsSuccessExample },
  })
  async list(@CurrentUser() user: AuthenticatedUser) {
    const items = await this.tagsService.listMyTags(user.userId);
    return { items };
  }

  /**
   * POST /document-tags
   * 태그 생성 (Story 4.16)
   */
  @Post()
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.DOC_TAG_SUCCESS)
  @ApiOperation({
    summary: '태그 생성',
    description: '본인 소유 태그를 생성합니다. 같은 이름 중복 불가.',
  })
  @ApiBody({ type: CreateTagDto })
  @ApiResponse({
    status: 200,
    description: '생성된 태그',
    schema: { example: Examples.CreateTagSuccessExample },
  })
  @ApiResponse({
    status: 409,
    description: '동일 이름 태그 존재',
    schema: { example: Examples.CreateTagDuplicateExample },
  })
  async create(
    @CurrentUser() user: AuthenticatedUser,
    @Body() dto: CreateTagDto,
  ) {
    return this.tagsService.createTag(user.userId, dto);
  }

  /**
   * PATCH /document-tags/:tagId
   * 태그 수정 (Story 4.16)
   */
  @Patch(':tagId')
  @ResponseCode(RC.DOC_TAG_SUCCESS)
  @ApiOperation({
    summary: '태그 수정',
    description: '본인 소유 태그의 이름/색상을 수정합니다.',
  })
  @ApiBody({ type: UpdateTagDto })
  @ApiResponse({
    status: 200,
    description: '수정된 태그',
    schema: { example: Examples.UpdateTagSuccessExample },
  })
  @ApiResponse({
    status: 403,
    description: '본인 태그 아님',
    schema: { example: Examples.UpdateTagForbiddenExample },
  })
  @ApiResponse({
    status: 404,
    description: '태그 없음',
    schema: { example: Examples.UpdateTagNotFoundExample },
  })
  @ApiResponse({
    status: 409,
    description: '동일 이름 태그 존재',
    schema: { example: Examples.UpdateTagDuplicateExample },
  })
  async update(
    @CurrentUser() user: AuthenticatedUser,
    @Param('tagId', new ParseUUIDPipe()) tagId: string,
    @Body() dto: UpdateTagDto,
  ) {
    return this.tagsService.updateTag(user.userId, tagId, dto);
  }

  /**
   * DELETE /document-tags/:tagId
   * 태그 삭제 — 매핑도 CASCADE 삭제 (Story 4.16)
   */
  @Delete(':tagId')
  @ResponseCode(RC.DOC_TAG_SUCCESS)
  @ApiOperation({
    summary: '태그 삭제',
    description:
      '본인 소유 태그를 삭제합니다. 해당 태그가 문서에 부여돼 있던 매핑도 CASCADE 로 함께 삭제됩니다.',
  })
  @ApiResponse({
    status: 200,
    description: '삭제 완료',
    schema: { example: Examples.DeleteTagSuccessExample },
  })
  @ApiResponse({
    status: 403,
    description: '본인 태그 아님',
    schema: { example: Examples.DeleteTagForbiddenExample },
  })
  @ApiResponse({
    status: 404,
    description: '태그 없음',
    schema: { example: Examples.DeleteTagNotFoundExample },
  })
  async delete(
    @CurrentUser() user: AuthenticatedUser,
    @Param('tagId', new ParseUUIDPipe()) tagId: string,
  ) {
    await this.tagsService.deleteTag(user.userId, tagId);
    return { tagId };
  }
}
