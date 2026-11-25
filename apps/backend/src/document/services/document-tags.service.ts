import { Injectable, Logger, Inject, forwardRef } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, In, DataSource } from 'typeorm';
import { DocUserTag } from '../entities/doc-user-tag.entity';
import { DocUserTagMapping } from '../entities/doc-user-tag-mapping.entity';
import { DocDocument } from '../entities/doc-document.entity';
import { DocDocumentContent } from '../entities/doc-document-content.entity';
import { BusinessException } from '../../common/exceptions/business.exception';
import { ResponseCode as RC } from '../../common/constants/response-codes';
import { CreateTagDto, UpdateTagDto } from '../dto/document-tag.dto';
import { AuthService } from '../../auth/auth.service';

export interface TagSummary {
  id: string;
  name: string;
  color: string;
}

@Injectable()
export class DocumentTagsService {
  private readonly logger = new Logger(DocumentTagsService.name);

  constructor(
    @InjectRepository(DocUserTag)
    private readonly tagRepository: Repository<DocUserTag>,
    @InjectRepository(DocUserTagMapping)
    private readonly mappingRepository: Repository<DocUserTagMapping>,
    @InjectRepository(DocDocument)
    private readonly docRepository: Repository<DocDocument>,
    @InjectRepository(DocDocumentContent)
    private readonly contentRepository: Repository<DocDocumentContent>,
    private readonly dataSource: DataSource,
    @Inject(forwardRef(() => AuthService))
    private readonly authService: AuthService,
  ) {}

  async listMyTags(userId: string) {
    const tags = await this.tagRepository.find({
      where: { userId },
      order: { name: 'ASC' },
    });
    return tags.map((t) => ({
      id: t.id,
      name: t.name,
      color: t.color,
      createdAt: t.createdAt,
      updatedAt: t.updatedAt,
    }));
  }

  async createTag(userId: string, dto: CreateTagDto) {
    const exists = await this.tagRepository.findOne({
      where: { userId, name: dto.name },
    });
    if (exists) {
      throw new BusinessException(RC.DOC_TAG_DUPLICATE);
    }
    const tag = this.tagRepository.create({
      userId,
      name: dto.name,
      color: dto.color ?? '#9e9e9e',
    });
    const saved = await this.tagRepository.save(tag);
    return {
      id: saved.id,
      name: saved.name,
      color: saved.color,
      createdAt: saved.createdAt,
      updatedAt: saved.updatedAt,
    };
  }

  async updateTag(userId: string, tagId: string, dto: UpdateTagDto) {
    const tag = await this.findOwnedTagOrThrow(userId, tagId);
    if (dto.name !== undefined && dto.name !== tag.name) {
      const dup = await this.tagRepository.findOne({
        where: { userId, name: dto.name },
      });
      if (dup && dup.id !== tag.id) {
        throw new BusinessException(RC.DOC_TAG_DUPLICATE);
      }
      tag.name = dto.name;
    }
    if (dto.color !== undefined) {
      tag.color = dto.color;
    }
    const saved = await this.tagRepository.save(tag);
    return {
      id: saved.id,
      name: saved.name,
      color: saved.color,
      createdAt: saved.createdAt,
      updatedAt: saved.updatedAt,
    };
  }

  async deleteTag(userId: string, tagId: string) {
    const tag = await this.findOwnedTagOrThrow(userId, tagId);
    await this.tagRepository.remove(tag);
  }

  async setDocumentTags(
    userId: string,
    authDeptId: string | null,
    deptPermissions: string[],
    documentId: string,
    tagIds: string[],
  ) {
    await this.assertDocumentAccessible(
      userId,
      authDeptId,
      deptPermissions,
      documentId,
    );

    const uniqueTagIds = Array.from(new Set(tagIds));
    if (uniqueTagIds.length > 0) {
      const tags = await this.tagRepository.find({
        where: { id: In(uniqueTagIds) },
      });
      if (tags.length !== uniqueTagIds.length) {
        throw new BusinessException(RC.DOC_TAG_NOT_FOUND);
      }
      const foreign = tags.find((t) => t.userId !== userId);
      if (foreign) {
        throw new BusinessException(RC.DOC_TAG_FORBIDDEN);
      }
    }

    await this.dataSource.transaction(async (manager) => {
      await manager.delete(DocUserTagMapping, { userId, documentId });
      if (uniqueTagIds.length > 0) {
        const rows = uniqueTagIds.map((tagId) => ({
          userId,
          tagId,
          documentId,
        }));
        await manager.insert(DocUserTagMapping, rows);
      }
    });

    return this.getDocumentTags(userId, documentId);
  }

  async getDocumentTags(userId: string, documentId: string): Promise<TagSummary[]> {
    const rows = await this.mappingRepository.find({
      where: { userId, documentId },
      relations: ['tag'],
    });
    return rows
      .filter((r) => r.tag)
      .map((r) => ({
        id: r.tag.id,
        name: r.tag.name,
        color: r.tag.color,
      }));
  }

  async findTagsByDocumentIds(
    userId: string,
    documentIds: string[],
  ): Promise<Map<string, TagSummary[]>> {
    const result = new Map<string, TagSummary[]>();
    if (documentIds.length === 0) return result;
    const rows = await this.mappingRepository.find({
      where: { userId, documentId: In(documentIds) },
      relations: ['tag'],
    });
    for (const r of rows) {
      if (!r.tag) continue;
      const list = result.get(r.documentId) ?? [];
      list.push({ id: r.tag.id, name: r.tag.name, color: r.tag.color });
      result.set(r.documentId, list);
    }
    return result;
  }

  async findDocumentIdsByTagIds(
    userId: string,
    tagIds: string[],
  ): Promise<string[]> {
    if (tagIds.length === 0) return [];
    const ownedTags = await this.tagRepository.find({
      where: { userId, id: In(tagIds) },
    });
    if (ownedTags.length === 0) return [];
    const ownedIds = ownedTags.map((t) => t.id);
    const rows = await this.mappingRepository.find({
      where: { userId, tagId: In(ownedIds) },
    });
    return Array.from(new Set(rows.map((r) => r.documentId)));
  }

  private async findOwnedTagOrThrow(userId: string, tagId: string) {
    const tag = await this.tagRepository.findOne({ where: { id: tagId } });
    if (!tag) {
      throw new BusinessException(RC.DOC_TAG_NOT_FOUND);
    }
    if (tag.userId !== userId) {
      throw new BusinessException(RC.DOC_TAG_FORBIDDEN);
    }
    return tag;
  }

  private async assertDocumentAccessible(
    userId: string,
    authDeptId: string | null,
    deptPermissions: string[],
    documentId: string,
  ) {
    const doc = await this.docRepository.findOne({ where: { id: documentId } });
    if (!doc) {
      throw new BusinessException(RC.DOC_TAG_DOCUMENT_FORBIDDEN);
    }
    if (doc.createdBy === userId) {
      return;
    }

    const accessibleDeptIds = this.authService.getAccessibleDeptIds(
      authDeptId,
      deptPermissions,
    );
    if (accessibleDeptIds.length === 0) {
      throw new BusinessException(RC.DOC_TAG_DOCUMENT_FORBIDDEN);
    }

    const content = await this.contentRepository.findOne({
      where: { documentId, isActive: 'Y' },
    });
    if (!content || !content.authDeptId) {
      throw new BusinessException(RC.DOC_TAG_DOCUMENT_FORBIDDEN);
    }
    if (!accessibleDeptIds.includes(content.authDeptId)) {
      throw new BusinessException(RC.DOC_TAG_DOCUMENT_FORBIDDEN);
    }
  }
}
