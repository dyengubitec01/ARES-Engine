import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { BoardPost } from '../board/entities/board-post.entity';
import { BoardPostAdoption } from '../board/entities/board-post-adoption.entity';
import { BusinessException } from '../common/exceptions/business.exception';
import {
  ResponseCode,
  getHttpStatus,
} from '../common/constants/response-codes';

@Injectable()
export class AdoptionService {
  private readonly logger = new Logger(AdoptionService.name);

  constructor(
    @InjectRepository(BoardPost)
    private readonly postRepository: Repository<BoardPost>,
    @InjectRepository(BoardPostAdoption)
    private readonly adoptionRepository: Repository<BoardPostAdoption>,
  ) {}

  /**
   * suggestion 게시글 채택 등급 부여 (UPSERT)
   * - post.boardType.name === 'suggestion' 만 허용
   * - 같은 post 에 다시 호출 시 grade 갱신
   */
  async adopt(
    postId: string,
    grade: number,
    reviewerId: string,
  ): Promise<BoardPostAdoption> {
    const post = await this.postRepository.findOne({
      where: { id: postId },
      relations: ['boardType'],
    });

    if (!post) {
      throw new BusinessException(
        ResponseCode.ADMIN_BOARD_ADOPTION_POST_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.ADMIN_BOARD_ADOPTION_POST_NOT_FOUND),
      );
    }

    if (post.boardType?.name !== 'suggestion') {
      throw new BusinessException(
        ResponseCode.ADMIN_BOARD_ADOPTION_INVALID_TYPE,
        undefined,
        getHttpStatus(ResponseCode.ADMIN_BOARD_ADOPTION_INVALID_TYPE),
      );
    }

    let adoption = await this.adoptionRepository.findOne({
      where: { postId },
    });

    if (adoption) {
      adoption.grade = grade;
      adoption.reviewerId = reviewerId;
      adoption.reviewedAt = new Date();
    } else {
      adoption = this.adoptionRepository.create({
        postId,
        grade,
        reviewerId,
        reviewedAt: new Date(),
      });
    }

    return this.adoptionRepository.save(adoption);
  }
}
