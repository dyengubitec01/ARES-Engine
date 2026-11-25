import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { v4 as uuidv4 } from 'uuid';
import { BoardType } from './entities/board-type.entity';
import { BoardPost } from './entities/board-post.entity';
import { BoardPostImage } from './entities/board-post-image.entity';
import { BoardComment } from './entities/board-comment.entity';
import { BoardSurvey } from './entities/board-survey.entity';
import { AuthUser } from '../auth/entities/auth-user.entity';
import { AuthUsersAlarm } from '../auth/entities/auth-users-alarm.entity';
import { MinioService } from '../external/minio/minio.service';
import {
  CreatePostDto,
  CreateReplyDto,
  PostListQueryDto,
} from './dto/board.dto';
import { CreateSurveyDto } from './dto/board-survey.dto';
import { AuthorityType } from '../common/enums';
import { BusinessException } from '../common/exceptions/business.exception';
import {
  ResponseCode,
  getHttpStatus,
} from '../common/constants/response-codes';

@Injectable()
export class BoardService {
  private readonly logger = new Logger(BoardService.name);
  private readonly URL_EXPIRY_SECONDS = 3600;

  constructor(
    @InjectRepository(BoardType)
    private readonly boardTypeRepository: Repository<BoardType>,
    @InjectRepository(BoardPost)
    private readonly postRepository: Repository<BoardPost>,
    @InjectRepository(BoardPostImage)
    private readonly imageRepository: Repository<BoardPostImage>,
    @InjectRepository(BoardComment)
    private readonly commentRepository: Repository<BoardComment>,
    @InjectRepository(BoardSurvey)
    private readonly surveyRepository: Repository<BoardSurvey>,
    @InjectRepository(AuthUser)
    private readonly userRepository: Repository<AuthUser>,
    @InjectRepository(AuthUsersAlarm)
    private readonly alarmRepository: Repository<AuthUsersAlarm>,
    private readonly minioService: MinioService,
  ) {}

  async getBoardTypes(name?: string) {
    return this.boardTypeRepository.find({
      select: ['id', 'name', 'description'],
      ...(name && { where: { name: name as any } }),
      order: { name: 'ASC' },
    });
  }

  // ============================================================
  // Post CRUD
  // ============================================================

  async createPost(userId: string, authorities: string[], dto: CreatePostDto) {
    const hasImage = dto.images && dto.images.length > 0;

    // 이미지 objectKey가 MinIO에 실제 존재하는지 검증
    if (hasImage && dto.images) {
      const checks = await Promise.all(
        dto.images.map((img) => this.minioService.objectExists(img.objectKey)),
      );
      const missing = dto.images.filter((_, i) => !checks[i]);
      if (missing.length > 0) {
        throw new BusinessException(
          ResponseCode.BOARD_IMAGE_NOT_UPLOADED,
          `업로드되지 않은 이미지: ${missing.map((m) => m.originalFilename).join(', ')}`,
          getHttpStatus(ResponseCode.BOARD_IMAGE_NOT_UPLOADED),
        );
      }
    }

    const post = this.postRepository.create({
      boardTypeId: dto.boardTypeId,
      userId,
      title: dto.title,
      content: dto.content,
      hasImage,
    });

    const savedPost = await this.postRepository.save(post);

    // 이미지 메타데이터 저장
    if (hasImage && dto.images) {
      const images = dto.images.map((img, index) =>
        this.imageRepository.create({
          postId: savedPost.id,
          objectKey: img.objectKey,
          originalFilename: img.originalFilename,
          fileSize: img.fileSize ?? null,
          mimeType: img.mimeType ?? null,
          sortOrder: img.sortOrder ?? index,
        }),
      );
      await this.imageRepository.save(images);
    }

    return this.getPostDetail(userId, authorities, savedPost.id);
  }

  async getPostList(
    userId: string,
    authorities: string[],
    query: PostListQueryDto,
  ) {
    const { page = 1, limit = 20, boardTypeId } = query;
    const isSystem = authorities.includes(AuthorityType.ADMIN);

    const queryBuilder = this.postRepository
      .createQueryBuilder('p')
      .select('p');

    if (!isSystem) {
      queryBuilder.where('p.user_id = :userId', { userId });
    }

    if (boardTypeId) {
      queryBuilder.andWhere('p.board_type_id = :boardTypeId', { boardTypeId });
    }

    const total = await queryBuilder.getCount();

    const posts = await queryBuilder
      .orderBy('p.created_at', 'DESC')
      .skip((page - 1) * limit)
      .take(limit)
      .getRawMany();

    // 작성자 이름 조회
    const postIds = posts.map((p) => p.p_id);
    const userIds = [...new Set(posts.map((p) => p.p_user_id))];
    const users =
      userIds.length > 0
        ? await this.userRepository
            .createQueryBuilder('u')
            .select(['u.id', 'u.name'])
            .whereInIds(userIds)
            .getMany()
        : [];
    const userMap = new Map(users.map((u) => [u.id, u.name]));

    // 답변 여부 조회
    const repliedPostIds: Set<string> =
      postIds.length > 0
        ? new Set(
            (
              await this.commentRepository
                .createQueryBuilder('c')
                .select('DISTINCT c.post_id', 'postId')
                .where('c.post_id IN (:...postIds)', { postIds })
                .andWhere('c.deleted_at IS NULL')
                .getRawMany()
            ).map((r) => r.postId),
          )
        : new Set();

    return {
      items: posts.map((p) => ({
        id: p.p_id,
        boardTypeId: p.p_board_type_id,
        userId: p.p_user_id,
        userName: userMap.get(p.p_user_id) ?? null,
        title: p.p_title,
        hasImage: p.p_has_image,
        isReplied: repliedPostIds.has(p.p_id),
        createdAt: p.p_created_at,
      })),
      meta: {
        total,
        page,
        limit,
        totalPages: Math.ceil(total / limit),
      },
    };
  }

  async getPostDetail(userId: string, authorities: string[], postId: string) {
    const isSystem = authorities.includes(AuthorityType.ADMIN);
    const post = await this.postRepository.findOne({
      where: isSystem ? { id: postId } : { id: postId, userId },
    });

    if (!post) {
      throw new BusinessException(
        ResponseCode.BOARD_POST_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.BOARD_POST_NOT_FOUND),
      );
    }

    const images = await this.imageRepository.find({
      where: { postId },
      order: { sortOrder: 'ASC' },
    });

    // 작성자 이름 조회
    const user = await this.userRepository.findOne({
      where: { id: post.userId },
      select: ['id', 'name'],
    });

    const imagesWithUrl = await Promise.all(
      images.map(async (img) => ({
        id: img.id,
        objectKey: img.objectKey,
        originalFilename: img.originalFilename,
        fileSize: img.fileSize,
        mimeType: img.mimeType,
        sortOrder: img.sortOrder,
        viewUrl: await this.minioService.generatePresignedGetUrl(
          img.objectKey,
          this.URL_EXPIRY_SECONDS,
        ),
      })),
    );

    // 답변 조회
    const comment = await this.commentRepository.findOne({
      where: { postId },
    });
    let reply = null;
    if (comment) {
      const replyUser = await this.userRepository.findOne({
        where: { id: comment.userId },
        select: ['id', 'name'],
      });
      reply = {
        id: comment.id,
        userId: comment.userId,
        userName: replyUser?.name ?? null,
        content: comment.content,
        createdAt: comment.createdAt,
      };
    }

    return {
      id: post.id,
      boardTypeId: post.boardTypeId,
      userId: post.userId,
      userName: user?.name ?? null,
      title: post.title,
      content: post.content,
      hasImage: post.hasImage,
      isReplied: !!reply,
      images: imagesWithUrl,
      reply,
      createdAt: post.createdAt,
    };
  }

  // ============================================================
  // Reply (답변)
  // ============================================================

  async createReply(
    adminUserId: string,
    authorities: string[],
    postId: string,
    dto: CreateReplyDto,
  ) {
    if (!authorities.includes(AuthorityType.ADMIN)) {
      throw new BusinessException(
        ResponseCode.FORBIDDEN,
        undefined,
        getHttpStatus(ResponseCode.FORBIDDEN),
      );
    }

    const post = await this.postRepository.findOne({ where: { id: postId } });
    if (!post) {
      throw new BusinessException(
        ResponseCode.BOARD_POST_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.BOARD_POST_NOT_FOUND),
      );
    }

    const existing = await this.commentRepository.findOne({
      where: { postId },
    });
    if (existing) {
      throw new BusinessException(
        ResponseCode.BOARD_REPLY_ALREADY_EXISTS,
        undefined,
        getHttpStatus(ResponseCode.BOARD_REPLY_ALREADY_EXISTS),
      );
    }

    const comment = this.commentRepository.create({
      postId,
      userId: adminUserId,
      content: dto.content,
    });
    await this.commentRepository.save(comment);

    await this.alarmRepository
      .save(
        this.alarmRepository.create({
          usersId: post.userId,
          postId,
          message: '피드백에 답변이 등록되었습니다.',
        }),
      )
      .catch((err) => {
        this.logger.error(`Failed to create alarm: ${err}`);
      });

    const adminUser = await this.userRepository.findOne({
      where: { id: adminUserId },
      select: ['id', 'name'],
    });

    return {
      id: comment.id,
      postId: comment.postId,
      userId: comment.userId,
      userName: adminUser?.name ?? null,
      content: comment.content,
      createdAt: comment.createdAt,
    };
  }

  // ============================================================
  // Presigned URL
  // ============================================================

  async generatePresignedUrl(filename: string, boardTypeName: string) {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const objectKey = `board/${boardTypeName}/${year}/${month}/${uuidv4()}/${filename}`;
    const uploadUrl = await this.minioService.generatePresignedPutUrl(
      objectKey,
      this.URL_EXPIRY_SECONDS,
    );

    return {
      uploadUrl,
      objectKey,
      expiresIn: this.URL_EXPIRY_SECONDS,
    };
  }

  // ============================================================
  // Survey
  // ============================================================

  async submitSurvey(userId: string, dto: CreateSurveyDto) {
    const existing = await this.surveyRepository.findOne({
      where: { userId },
    });
    if (existing) {
      throw new BusinessException(
        ResponseCode.BOARD_SURVEY_DUPLICATE,
        undefined,
        getHttpStatus(ResponseCode.BOARD_SURVEY_DUPLICATE),
      );
    }

    const survey = this.surveyRepository.create({
      userId,
      ...dto,
    });

    return this.surveyRepository.save(survey);
  }
}
