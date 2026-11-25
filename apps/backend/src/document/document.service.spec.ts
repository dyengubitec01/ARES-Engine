import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import {
  PayloadTooLargeException,
  UnsupportedMediaTypeException,
  NotFoundException,
  ForbiddenException,
  ConflictException,
} from '@nestjs/common';
import { DocumentService } from './document.service';
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
import { DocStatus, ObjectKind, AuthorityType } from '../common/enums';
import { IsNull, DataSource } from 'typeorm';

describe('DocumentService', () => {
  let service: DocumentService;

  const mockDocument: Partial<DocDocument> = {
    id: 'doc-uuid-123',
    title: 'test-document',
    minioUrl: 'raw/dept-001/2026/01/doc-uuid-123/', // Pattern: raw/{deptId}/{year}/{month}/{documentId}/
    createdBy: 'user-uuid-123',
    createdAt: new Date(),
  };

  const mockContent: Partial<DocDocumentContent> = {
    id: 'version-uuid-123',
    documentId: 'doc-uuid-123',
    versionNo: 1,
    originalFilename: 'test-document.pdf',
    uploaderId: 'user-uuid-123',
    sha256: '',
    fileSize: 1024000,
    mimeType: 'application/pdf',
    status: DocStatus.UPLOADING,
    isActive: 'Y',
    createdAt: new Date(),
  };

  const mockStorageFile: Partial<StorageObjectFile> = {
    id: 'storage-uuid-123',
    docContentId: 'version-uuid-123',
    kind: ObjectKind.RAW,
    bucket: 'rag',
    objectKey: 'raw/doc-uuid-123/version-uuid-123/test-document.pdf',
    sizeBytes: 1024000,
    createdAt: new Date(),
  };

  const mockDocumentRepository = {
    create: jest.fn(),
    save: jest.fn(),
    findOne: jest.fn(),
    remove: jest.fn(),
    createQueryBuilder: jest.fn(),
  };

  const mockContentRepository = {
    create: jest.fn(),
    save: jest.fn(),
    findOne: jest.fn(),
    createQueryBuilder: jest.fn(),
  };

  const mockStorageFileRepository = {
    create: jest.fn(),
    save: jest.fn(),
    find: jest.fn(),
  };

  const mockFavoriteRepository = {
    findOne: jest.fn(),
    create: jest.fn(),
    save: jest.fn(),
    remove: jest.fn(),
  };

  const mockUser = {
    id: 'user-uuid-123',
    email: 'test@example.com',
    name: 'Test User',
    authDeptId: 'dept-001',
  };

  const mockUserRepository = {
    findOne: jest.fn().mockResolvedValue(mockUser),
  };

  const mockMinioService = {
    generatePresignedPutUrl: jest.fn(),
    generatePresignedGetUrl: jest.fn(),
    getBucket: jest.fn().mockReturnValue('rag'),
    deleteObject: jest.fn(),
    listObjects: jest.fn(),
  };

  const mockEmbeddingService = {
    requestEmbedding: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        DocumentService,
        {
          provide: getRepositoryToken(DocDocument),
          useValue: mockDocumentRepository,
        },
        {
          provide: getRepositoryToken(DocDocumentContent),
          useValue: mockContentRepository,
        },
        {
          provide: getRepositoryToken(DocDocumentFavorite),
          useValue: mockFavoriteRepository,
        },
        {
          provide: getRepositoryToken(DocDocumentExclude),
          useValue: {},
        },
        {
          provide: getRepositoryToken(StorageObjectFile),
          useValue: mockStorageFileRepository,
        },
        {
          provide: getRepositoryToken(AuthUser),
          useValue: mockUserRepository,
        },
        {
          provide: getRepositoryToken(AuthUsersAlarm),
          useValue: {},
        },
        {
          provide: getRepositoryToken(DocEmbedReview),
          useValue: {},
        },
        {
          provide: getRepositoryToken(RagStatusEvent),
          useValue: {},
        },
        {
          provide: MinioService,
          useValue: mockMinioService,
        },
        {
          provide: EmbeddingService,
          useValue: mockEmbeddingService,
        },
        {
          provide: QdrantService,
          useValue: {},
        },
        {
          provide: DataSource,
          useValue: {},
        },
      ],
    }).compile();

    service = module.get<DocumentService>(DocumentService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('createUploadSession', () => {
    it('[P1] AC1,AC4: should create upload session with pre-signed URL', async () => {
      // GIVEN: Valid file metadata
      const userId = 'user-uuid-123';
      const dto = {
        files: [
          {
            filename: 'test-document.pdf',
            mimeType: 'application/pdf',
            size: 1024000,
            fileModifiedAt: '2026-01-01T00:00:00.000Z',
            sha256:
              'a3f1c2e4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2',
          },
        ],
      };

      mockDocumentRepository.create.mockReturnValue(mockDocument);
      mockDocumentRepository.save.mockResolvedValue(mockDocument);
      mockContentRepository.create.mockReturnValue(mockContent);
      mockContentRepository.save.mockResolvedValue(mockContent);
      mockMinioService.generatePresignedPutUrl.mockResolvedValue(
        'https://minio.example.com/presigned-url',
      );

      // WHEN: Creating upload session
      const result = await service.createUploadSession(userId, dto);

      // THEN: Returns session with documentId and uploads (versionId is in uploads[])
      expect(result).toHaveProperty('documentId');
      expect(result).toHaveProperty('uploads');
      expect(result.uploads[0]).toHaveProperty('versionId');
      expect(result.uploads).toHaveLength(1);
      expect(result.uploads[0]).toHaveProperty('filename', 'test-document.pdf');
      expect(result.uploads[0]).toHaveProperty('uploadUrl');
      expect(result.uploads[0]).toHaveProperty('objectKey');
      expect(result.uploads[0]).toHaveProperty('expiresIn', 3600);

      expect(mockDocumentRepository.create).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'test-document',
          createdBy: userId,
        }),
      );
      expect(mockContentRepository.create).toHaveBeenCalledWith(
        expect.objectContaining({
          originalFilename: 'test-document.pdf',
          uploaderId: userId,
          status: DocStatus.UPLOADING,
        }),
      );
      expect(mockMinioService.generatePresignedPutUrl).toHaveBeenCalled();
    });

    it('[P1] AC2: should throw PayloadTooLargeException when file exceeds 100MB', async () => {
      // GIVEN: File larger than 100MB
      const userId = 'user-uuid-123';
      const dto = {
        files: [
          {
            filename: 'large-file.pdf',
            mimeType: 'application/pdf',
            size: 150 * 1024 * 1024, // 150MB
            fileModifiedAt: '2026-01-01T00:00:00.000Z',
            sha256:
              'a3f1c2e4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2',
          },
        ],
      };

      // WHEN/THEN: Creating upload session throws PayloadTooLargeException
      await expect(service.createUploadSession(userId, dto)).rejects.toThrow(
        PayloadTooLargeException,
      );
      expect(mockDocumentRepository.create).not.toHaveBeenCalled();
    });

    it('[P1] AC3: should throw UnsupportedMediaTypeException for invalid MIME type', async () => {
      // GIVEN: Unsupported file type
      const userId = 'user-uuid-123';
      const dto = {
        files: [
          {
            filename: 'image.jpg',
            mimeType: 'image/jpeg',
            size: 1024000,
            fileModifiedAt: '2026-01-01T00:00:00.000Z',
            sha256:
              'a3f1c2e4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2',
          },
        ],
      };

      // WHEN/THEN: Creating upload session throws UnsupportedMediaTypeException
      await expect(service.createUploadSession(userId, dto)).rejects.toThrow(
        UnsupportedMediaTypeException,
      );
      expect(mockDocumentRepository.create).not.toHaveBeenCalled();
    });

    it('[P2] should support all allowed MIME types', async () => {
      // GIVEN: Various supported MIME types
      const userId = 'user-uuid-123';
      const supportedTypes = [
        { filename: 'doc.pdf', mimeType: 'application/pdf' },
        {
          filename: 'doc.docx',
          mimeType:
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        },
        {
          filename: 'doc.xlsx',
          mimeType:
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        },
        {
          filename: 'doc.pptx',
          mimeType:
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        },
        { filename: 'doc.txt', mimeType: 'text/plain' },
        { filename: 'doc.md', mimeType: 'text/markdown' },
      ];

      mockDocumentRepository.create.mockReturnValue(mockDocument);
      mockDocumentRepository.save.mockResolvedValue(mockDocument);
      mockContentRepository.create.mockReturnValue(mockContent);
      mockContentRepository.save.mockResolvedValue(mockContent);
      mockMinioService.generatePresignedPutUrl.mockResolvedValue(
        'https://minio.example.com/presigned-url',
      );

      // WHEN/THEN: Each type should work without throwing
      for (const type of supportedTypes) {
        const dto = {
          files: [
            {
              ...type,
              size: 1024000,
              fileModifiedAt: '2026-01-01T00:00:00.000Z',
              sha256:
                'a3f1c2e4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2',
            },
          ],
        };
        await expect(
          service.createUploadSession(userId, dto),
        ).resolves.not.toThrow();
      }
    });

    it('[P2] should generate correct objectKey pattern', async () => {
      // GIVEN: Valid file metadata
      const userId = 'user-uuid-123';
      const dto = {
        files: [
          {
            filename: 'my-document.pdf',
            mimeType: 'application/pdf',
            size: 1024000,
            fileModifiedAt: '2026-01-01T00:00:00.000Z',
            sha256:
              'a3f1c2e4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2',
          },
        ],
      };

      mockDocumentRepository.create.mockReturnValue(mockDocument);
      mockDocumentRepository.save.mockResolvedValue(mockDocument);
      mockContentRepository.create.mockReturnValue(mockContent);
      mockContentRepository.save.mockResolvedValue(mockContent);
      mockMinioService.generatePresignedPutUrl.mockResolvedValue(
        'https://minio.example.com/presigned-url',
      );

      // WHEN: Creating upload session
      const result = await service.createUploadSession(userId, dto);

      // THEN: objectKey follows pattern raw/{deptId}/{year}/{month}/{documentId}/{filename}
      const expectedPattern =
        /^raw\/[\w-]+\/\d{4}\/\d{2}\/[\w-]+\/my-document\.pdf$/;
      expect(result.uploads[0].objectKey).toMatch(expectedPattern);
    });

    it('[P2] should set document title from filename without extension', async () => {
      // GIVEN: File with specific name
      const userId = 'user-uuid-123';
      const dto = {
        files: [
          {
            filename: 'important-report.pdf',
            mimeType: 'application/pdf',
            size: 1024000,
            fileModifiedAt: '2026-01-01T00:00:00.000Z',
            sha256:
              'a3f1c2e4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2',
          },
        ],
      };

      mockDocumentRepository.create.mockReturnValue({
        ...mockDocument,
        title: 'important-report',
      });
      mockDocumentRepository.save.mockResolvedValue(mockDocument);
      mockContentRepository.create.mockReturnValue(mockContent);
      mockContentRepository.save.mockResolvedValue(mockContent);
      mockMinioService.generatePresignedPutUrl.mockResolvedValue(
        'https://minio.example.com/presigned-url',
      );

      // WHEN: Creating upload session
      await service.createUploadSession(userId, dto);

      // THEN: Document title should be filename without extension
      expect(mockDocumentRepository.create).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'important-report',
        }),
      );
    });

    it('[P2] should set version status to UPLOADING', async () => {
      // GIVEN: Valid file metadata
      const userId = 'user-uuid-123';
      const dto = {
        files: [
          {
            filename: 'test.pdf',
            mimeType: 'application/pdf',
            size: 1024000,
            fileModifiedAt: '2026-01-01T00:00:00.000Z',
            sha256:
              'a3f1c2e4b5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2',
          },
        ],
      };

      mockDocumentRepository.create.mockReturnValue(mockDocument);
      mockDocumentRepository.save.mockResolvedValue(mockDocument);
      mockContentRepository.create.mockReturnValue(mockContent);
      mockContentRepository.save.mockResolvedValue(mockContent);
      mockMinioService.generatePresignedPutUrl.mockResolvedValue(
        'https://minio.example.com/presigned-url',
      );

      // WHEN: Creating upload session
      await service.createUploadSession(userId, dto);

      // THEN: Version status should be UPLOADING
      expect(mockContentRepository.create).toHaveBeenCalledWith(
        expect.objectContaining({
          status: DocStatus.UPLOADING,
        }),
      );
    });
  });

  describe('completeUpload', () => {
    it('[P1] AC1,AC2: should complete upload and set status to uploaded', async () => {
      // GIVEN: Valid document and version
      const userId = 'user-uuid-123';
      const documentId = 'doc-uuid-123';
      const versionId = 'version-uuid-123';

      mockDocumentRepository.findOne.mockResolvedValue(mockDocument);
      mockContentRepository.findOne.mockResolvedValue({ ...mockContent });
      mockContentRepository.save.mockResolvedValue({
        ...mockContent,
        status: DocStatus.UPLOADED,
      });
      mockStorageFileRepository.create.mockReturnValue(mockStorageFile);
      mockStorageFileRepository.save.mockResolvedValue(mockStorageFile);

      // WHEN: Completing upload
      const result = await service.completeUpload(
        userId,
        documentId,
        versionId,
      );

      // THEN: Returns uploaded status (not queued - embedding is separate now)
      expect(result).toEqual({
        documentId,
        versionId,
        status: DocStatus.UPLOADED,
      });
      expect(mockStorageFileRepository.create).toHaveBeenCalledWith(
        expect.objectContaining({
          kind: ObjectKind.RAW,
          bucket: 'rag',
        }),
      );
      // Embedding request should NOT be called - it's now a separate endpoint
      expect(mockEmbeddingService.requestEmbedding).not.toHaveBeenCalled();
    });

    it('[P1] should throw NotFoundException when document not found', async () => {
      // GIVEN: Document does not exist
      const userId = 'user-uuid-123';
      const documentId = 'non-existent-doc';
      const versionId = 'version-uuid-123';

      mockDocumentRepository.findOne.mockResolvedValue(null);

      // WHEN/THEN: Should throw NotFoundException
      await expect(
        service.completeUpload(userId, documentId, versionId),
      ).rejects.toThrow(NotFoundException);
    });

    it('[P1] should throw ForbiddenException when user is not owner', async () => {
      // GIVEN: User is not the document owner
      const userId = 'other-user-uuid';
      const documentId = 'doc-uuid-123';
      const versionId = 'version-uuid-123';

      mockDocumentRepository.findOne.mockResolvedValue(mockDocument);

      // WHEN/THEN: Should throw ForbiddenException
      await expect(
        service.completeUpload(userId, documentId, versionId),
      ).rejects.toThrow(ForbiddenException);
    });

    it('[P1] should throw NotFoundException when version not found', async () => {
      // GIVEN: Version does not exist
      const userId = 'user-uuid-123';
      const documentId = 'doc-uuid-123';
      const versionId = 'non-existent-version';

      mockDocumentRepository.findOne.mockResolvedValue(mockDocument);
      mockContentRepository.findOne.mockResolvedValue(null);

      // WHEN/THEN: Should throw NotFoundException
      await expect(
        service.completeUpload(userId, documentId, versionId),
      ).rejects.toThrow(NotFoundException);
    });
  });

  describe('findDocuments', () => {
    const mockQueryBuilder = {
      leftJoinAndSelect: jest.fn().mockReturnThis(),
      leftJoin: jest.fn().mockReturnThis(),
      addSelect: jest.fn().mockReturnThis(),
      where: jest.fn().mockReturnThis(),
      andWhere: jest.fn().mockReturnThis(),
      andHaving: jest.fn().mockReturnThis(),
      orderBy: jest.fn().mockReturnThis(),
      skip: jest.fn().mockReturnThis(),
      take: jest.fn().mockReturnThis(),
      getCount: jest.fn(),
      getMany: jest.fn(),
    };

    const mockContentQueryBuilder = {
      select: jest.fn().mockReturnThis(),
      where: jest.fn().mockReturnThis(),
      getQuery: jest
        .fn()
        .mockReturnValue(
          '(SELECT MAX(lv.version_no) FROM doc_document_content lv WHERE lv.document_id = d.id)',
        ),
    };

    beforeEach(() => {
      mockDocumentRepository.createQueryBuilder = jest
        .fn()
        .mockReturnValue(mockQueryBuilder);
      mockContentRepository.createQueryBuilder = jest
        .fn()
        .mockReturnValue(mockContentQueryBuilder);
    });

    it('[P1] AC1: should return documents list for user', async () => {
      // GIVEN: User with documents
      const userId = 'user-uuid-123';
      const query = { page: 1, limit: 20 };

      const mockDocWithVersion = {
        ...mockDocument,
        contents: [mockContent],
        favorites: [], // No favorites
      };

      mockQueryBuilder.getCount.mockResolvedValue(1);
      mockQueryBuilder.getMany.mockResolvedValue([mockDocWithVersion]);

      // WHEN: Finding documents
      const result = await service.findDocuments(userId, null, [], query);

      // THEN: Returns paginated list with correct structure
      expect(result).toHaveProperty('items');
      expect(result).toHaveProperty('meta');
      expect(result.items).toHaveLength(1);
      expect(result.items[0]).toHaveProperty('id', mockDocument.id);
      expect(result.items[0]).toHaveProperty('title', mockDocument.title);
      expect(result.items[0]).toHaveProperty('latestContent');
      expect(result.items[0]).toHaveProperty('isFavorite', false);
      expect(mockQueryBuilder.where).toHaveBeenCalledWith(
        'd.createdBy = :userId',
        { userId },
      );
    });

    it('[P1] AC2: should apply pagination correctly', async () => {
      // GIVEN: Pagination parameters
      const userId = 'user-uuid-123';
      const query = { page: 2, limit: 10 };

      mockQueryBuilder.getCount.mockResolvedValue(25);
      mockQueryBuilder.getMany.mockResolvedValue([]);

      // WHEN: Finding documents with pagination
      const result = await service.findDocuments(userId, null, [], query);

      // THEN: Pagination is applied correctly
      expect(mockQueryBuilder.skip).toHaveBeenCalledWith(10); // (page-1) * limit
      expect(mockQueryBuilder.take).toHaveBeenCalledWith(10);
      expect(result.meta).toEqual({
        total: 25,
        page: 2,
        limit: 10,
        totalPages: 3,
      });
    });

    it('[P1] AC3: should filter by status', async () => {
      // GIVEN: Status filter
      const userId = 'user-uuid-123';
      const query = { page: 1, limit: 20, status: DocStatus.COMPLETED };

      mockQueryBuilder.getCount.mockResolvedValue(0);
      mockQueryBuilder.getMany.mockResolvedValue([]);

      // WHEN: Finding documents with status filter
      await service.findDocuments(userId, null, [], query);

      // THEN: Status filter is applied
      expect(mockQueryBuilder.andWhere).toHaveBeenCalledWith(
        'c.status = :status',
        { status: DocStatus.COMPLETED },
      );
    });

    it('[P1] AC4: should include latestContent info in response', async () => {
      // GIVEN: Document with version
      const userId = 'user-uuid-123';
      const query = { page: 1, limit: 20 };

      const mockDocWithVersionAndFavorite = {
        ...mockDocument,
        contents: [mockContent],
        favorites: [{ id: 'fav-123' }], // Has favorite
      };

      mockQueryBuilder.getCount.mockResolvedValue(1);
      mockQueryBuilder.getMany.mockResolvedValue([
        mockDocWithVersionAndFavorite,
      ]);

      // WHEN: Finding documents
      const result = await service.findDocuments(userId, null, [], query);

      // THEN: latestContent contains correct info
      expect(result.items[0].latestContent).toEqual({
        versionNo: mockContent.versionNo,
        originalFilename: mockContent.originalFilename,
        fileSize: Number(mockContent.fileSize),
        mimeType: mockContent.mimeType,
        status: mockContent.status,
        createdAt: mockContent.createdAt,
      });
      expect(result.items[0].isFavorite).toBe(true);
    });

    it('[P2] should filter by favorite=true', async () => {
      // GIVEN: Favorite filter true
      const userId = 'user-uuid-123';
      const query = { page: 1, limit: 20, favorite: true };

      mockQueryBuilder.getCount.mockResolvedValue(0);
      mockQueryBuilder.getMany.mockResolvedValue([]);

      // WHEN: Finding favorite documents
      await service.findDocuments(userId, null, [], query);

      // THEN: Favorite filter is applied
      expect(mockQueryBuilder.andWhere).toHaveBeenCalledWith(
        'f.id IS NOT NULL',
      );
    });

    it('[P2] should filter by favorite=false', async () => {
      // GIVEN: Favorite filter false
      const userId = 'user-uuid-123';
      const query = { page: 1, limit: 20, favorite: false };

      mockQueryBuilder.getCount.mockResolvedValue(0);
      mockQueryBuilder.getMany.mockResolvedValue([]);

      // WHEN: Finding non-favorite documents
      await service.findDocuments(userId, null, [], query);

      // THEN: Non-favorite filter is applied using HAVING
      expect(mockQueryBuilder.andHaving).toHaveBeenCalledWith(
        'COUNT(f.id) = 0',
      );
    });

    it('[P2] should return empty list when no documents found', async () => {
      // GIVEN: No documents for user
      const userId = 'user-uuid-123';
      const query = { page: 1, limit: 20 };

      mockQueryBuilder.getCount.mockResolvedValue(0);
      mockQueryBuilder.getMany.mockResolvedValue([]);

      // WHEN: Finding documents
      const result = await service.findDocuments(userId, null, [], query);

      // THEN: Returns empty list with correct meta
      expect(result.items).toHaveLength(0);
      expect(result.meta.total).toBe(0);
      expect(result.meta.totalPages).toBe(0);
    });

    it('[P2] should handle document without version', async () => {
      // GIVEN: Document without versions
      const userId = 'user-uuid-123';
      const query = { page: 1, limit: 20 };

      const mockDocWithoutVersion = {
        ...mockDocument,
        contents: [],
      };

      mockQueryBuilder.getCount.mockResolvedValue(1);
      mockQueryBuilder.getMany.mockResolvedValue([mockDocWithoutVersion]);

      // WHEN: Finding documents
      const result = await service.findDocuments(userId, null, [], query);

      // THEN: latestContent is null
      expect(result.items[0].latestContent).toBeNull();
    });

    it('[P1] AC1: should exclude deleted documents (Soft Delete)', async () => {
      // GIVEN: Default query
      const userId = 'user-uuid-123';
      const query = { page: 1, limit: 20 };

      mockQueryBuilder.getCount.mockResolvedValue(0);
      mockQueryBuilder.getMany.mockResolvedValue([]);

      // WHEN: Finding documents
      await service.findDocuments(userId, null, [], query);

      // THEN: content-level deletedAt IS NULL filter is applied
      expect(mockQueryBuilder.andWhere).toHaveBeenCalledWith(
        'c.deletedAt IS NULL',
      );
    });
  });

  describe('findOne', () => {
    it('[P1] AC1: should return document detail with versions', async () => {
      // GIVEN: Valid document with versions
      const userId = 'user-uuid-123';
      const documentId = 'doc-uuid-123';

      const mockDocWithVersions = {
        ...mockDocument,
        contents: [mockContent],
      };

      mockDocumentRepository.findOne.mockResolvedValue(mockDocWithVersions);
      mockFavoriteRepository.findOne.mockResolvedValue(null);

      // WHEN: Finding document
      const result = await service.findOne(userId, documentId);

      // THEN: Returns document with versions and isFavorite
      expect(result).toHaveProperty('id', documentId);
      expect(result).toHaveProperty('title', mockDocument.title);
      expect(result).toHaveProperty('versions');
      expect(result.versions).toHaveLength(1);
      expect(result).toHaveProperty('isFavorite', false);
      expect(mockDocumentRepository.findOne).toHaveBeenCalledWith({
        where: {
          id: documentId,
          contents: { deletedAt: IsNull() },
        },
        relations: ['contents'],
        order: { contents: { versionNo: 'DESC' } },
      });
    });

    it('[P1] AC2: should include all version details', async () => {
      // GIVEN: Document with version containing status info
      const userId = 'user-uuid-123';
      const documentId = 'doc-uuid-123';

      const versionWithTimestamps = {
        ...mockContent,
        statusReason: 'Test reason',
        queuedAt: new Date(),
        startedAt: new Date(),
        finishedAt: null,
      };

      const mockDocWithVersions = {
        ...mockDocument,
        contents: [versionWithTimestamps],
      };

      mockDocumentRepository.findOne.mockResolvedValue(mockDocWithVersions);
      mockFavoriteRepository.findOne.mockResolvedValue(null);

      // WHEN: Finding document
      const result = await service.findOne(userId, documentId);

      // THEN: Version includes all status fields
      expect(result.versions[0]).toHaveProperty('status');
      expect(result.versions[0]).toHaveProperty('statusReason', 'Test reason');
      expect(result.versions[0]).toHaveProperty('queuedAt');
      expect(result.versions[0]).toHaveProperty('startedAt');
      expect(result.versions[0]).toHaveProperty('finishedAt', null);
    });

    it('[P1] AC3: should throw ForbiddenException for non-owner', async () => {
      // GIVEN: User is not the document owner
      const userId = 'other-user-uuid';
      const documentId = 'doc-uuid-123';

      mockDocumentRepository.findOne.mockResolvedValue({
        ...mockDocument,
        contents: [],
      });

      // WHEN/THEN: Should throw ForbiddenException
      await expect(service.findOne(userId, documentId)).rejects.toThrow(
        ForbiddenException,
      );
    });

    it('[P1] should throw NotFoundException when document not found', async () => {
      // GIVEN: Document does not exist
      const userId = 'user-uuid-123';
      const documentId = 'non-existent-doc';

      mockDocumentRepository.findOne.mockResolvedValue(null);

      // WHEN/THEN: Should throw NotFoundException
      await expect(service.findOne(userId, documentId)).rejects.toThrow(
        NotFoundException,
      );
    });

    it('[P2] should return isFavorite=true when favorited', async () => {
      // GIVEN: Document is favorited
      const userId = 'user-uuid-123';
      const documentId = 'doc-uuid-123';

      mockDocumentRepository.findOne.mockResolvedValue({
        ...mockDocument,
        contents: [],
      });
      mockFavoriteRepository.findOne.mockResolvedValue({
        id: 'fav-uuid',
        documentId,
        usersId: userId,
      });

      // WHEN: Finding document
      const result = await service.findOne(userId, documentId);

      // THEN: isFavorite is true
      expect(result.isFavorite).toBe(true);
    });
  });

  describe('deleteDocument', () => {
    it('[P1] AC1: should soft delete contents (update deletedAt + status)', async () => {
      // GIVEN: Valid document with active contents owned by user
      const userId = 'user-uuid-123';
      const documentId = 'doc-uuid-123';
      const activeContent = { ...mockContent, deletedAt: null };
      const documentWithContents = {
        ...mockDocument,
        contents: [activeContent],
      };

      mockDocumentRepository.findOne.mockResolvedValue(documentWithContents);
      mockContentRepository.save.mockResolvedValue([activeContent]);

      // WHEN: Deleting document
      await service.deleteDocument(userId, documentId);

      // THEN: Contents saved with deletedAt set and status = DELETED
      expect(mockContentRepository.save).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            deletedAt: expect.any(Date),
            status: DocStatus.DELETED,
          }),
        ]),
      );
      // MinIO files should NOT be deleted (Soft Delete)
      expect(mockMinioService.deleteObject).not.toHaveBeenCalled();
    });

    it('[P1] AC3: should throw ForbiddenException for non-owner without admin', async () => {
      // GIVEN: User is not the document owner and not admin
      const userId = 'other-user-uuid';
      const documentId = 'doc-uuid-123';
      const activeContent = { ...mockContent, deletedAt: null };
      const documentWithContents = {
        ...mockDocument,
        contents: [activeContent],
      };

      mockDocumentRepository.findOne.mockResolvedValue(documentWithContents);

      // WHEN/THEN: Should throw ForbiddenException
      await expect(service.deleteDocument(userId, documentId)).rejects.toThrow(
        ForbiddenException,
      );
      expect(mockContentRepository.save).not.toHaveBeenCalled();
    });

    it('[P1] AC3: should allow admin to delete any document', async () => {
      // GIVEN: User is admin but not document owner
      const userId = 'admin-user-uuid';
      const documentId = 'doc-uuid-123';
      const activeContent = { ...mockContent, deletedAt: null };
      const documentWithContents = {
        ...mockDocument,
        contents: [activeContent],
      };

      mockDocumentRepository.findOne.mockResolvedValue(documentWithContents);
      mockContentRepository.save.mockResolvedValue([activeContent]);

      // WHEN: Admin deletes document
      await service.deleteDocument(userId, documentId, [AuthorityType.ADMIN]);

      // THEN: Contents saved with deletedAt set and status = DELETED
      expect(mockContentRepository.save).toHaveBeenCalledWith(
        expect.arrayContaining([
          expect.objectContaining({
            deletedAt: expect.any(Date),
            status: DocStatus.DELETED,
          }),
        ]),
      );
    });

    it('[P1] AC4: should throw NotFoundException when document not found', async () => {
      // GIVEN: Document does not exist
      const userId = 'user-uuid-123';
      const documentId = 'non-existent-doc';

      mockDocumentRepository.findOne.mockResolvedValue(null);

      // WHEN/THEN: Should throw NotFoundException
      await expect(service.deleteDocument(userId, documentId)).rejects.toThrow(
        NotFoundException,
      );
    });

    it('[P1] should throw NotFoundException when all contents are already soft deleted', async () => {
      // GIVEN: Document exists but all contents already deleted
      const userId = 'user-uuid-123';
      const documentId = 'doc-uuid-123';
      const deletedContent = {
        ...mockContent,
        deletedAt: new Date(),
        status: DocStatus.DELETED,
      };
      const documentWithDeletedContents = {
        ...mockDocument,
        contents: [deletedContent],
      };

      mockDocumentRepository.findOne.mockResolvedValue(
        documentWithDeletedContents,
      );

      // WHEN/THEN: Should throw NotFoundException
      await expect(service.deleteDocument(userId, documentId)).rejects.toThrow(
        NotFoundException,
      );
    });
  });

  describe('getDownloadUrl', () => {
    it('[P1] AC1: should generate pre-signed GET URL for document download', async () => {
      // GIVEN: Version exists with parent document, user is owner
      const userId = 'user-uuid-123';
      const versionId = 'version-uuid-123';
      const downloadUrl = 'https://minio.example.com/presigned-get-url';

      mockContentRepository.findOne.mockResolvedValue({
        ...mockContent,
        document: mockDocument,
      });
      mockMinioService.generatePresignedGetUrl.mockResolvedValue(downloadUrl);

      // WHEN: Getting download URL (user is document owner)
      const result = await service.getDownloadUrl(userId, [], null, versionId);

      // THEN: Returns downloadUrl and expiresIn (AC2)
      expect(result).toHaveProperty('downloadUrl', downloadUrl);
      expect(result).toHaveProperty('expiresIn', 3600);
      // objectKey = document.minioUrl + version.originalFilename
      expect(mockMinioService.generatePresignedGetUrl).toHaveBeenCalledWith(
        'raw/dept-001/2026/01/doc-uuid-123/test-document.pdf',
        3600,
      );
    });

    it('[P1] AC3: should throw ForbiddenException when user has no permission', async () => {
      // GIVEN: Version exists but user is not owner, no dept match
      const userId = 'other-user-uuid';
      const versionId = 'version-uuid-123';

      mockContentRepository.findOne.mockResolvedValue({
        ...mockContent,
        document: mockDocument,
      });

      // WHEN/THEN: Should throw ForbiddenException
      await expect(
        service.getDownloadUrl(userId, [], null, versionId),
      ).rejects.toThrow(ForbiddenException);
    });

    it('[P1] should throw NotFoundException when version not found', async () => {
      // GIVEN: Version does not exist
      const userId = 'user-uuid-123';
      const versionId = 'nonexistent-version';

      mockContentRepository.findOne.mockResolvedValue(null);

      // WHEN/THEN: Should throw NotFoundException
      await expect(
        service.getDownloadUrl(userId, [], null, versionId),
      ).rejects.toThrow(NotFoundException);
    });
  });

  describe('addFavorite', () => {
    it('[P1] AC1: should add document to favorites', async () => {
      // GIVEN: Document exists and not favorited
      const userId = 'user-uuid-123';
      const documentId = 'doc-uuid-123';
      const mockFavorite = { id: 'fav-uuid', documentId, usersId: userId };

      mockDocumentRepository.findOne.mockResolvedValue(mockDocument);
      mockFavoriteRepository.findOne.mockResolvedValue(null);
      mockFavoriteRepository.create.mockReturnValue(mockFavorite);
      mockFavoriteRepository.save.mockResolvedValue(mockFavorite);

      // WHEN: Adding to favorites
      await service.addFavorite(userId, documentId);

      // THEN: Favorite is created
      expect(mockFavoriteRepository.create).toHaveBeenCalledWith({
        documentId,
        usersId: userId,
      });
      expect(mockFavoriteRepository.save).toHaveBeenCalledWith(mockFavorite);
    });

    it('[P1] AC2: should throw ConflictException for duplicate favorite', async () => {
      // GIVEN: Document is already favorited
      const userId = 'user-uuid-123';
      const documentId = 'doc-uuid-123';
      const existingFavorite = { id: 'fav-uuid', documentId, usersId: userId };

      mockDocumentRepository.findOne.mockResolvedValue(mockDocument);
      mockFavoriteRepository.findOne.mockResolvedValue(existingFavorite);

      // WHEN/THEN: Should throw ConflictException
      await expect(service.addFavorite(userId, documentId)).rejects.toThrow(
        ConflictException,
      );
      expect(mockFavoriteRepository.save).not.toHaveBeenCalled();
    });

    it('[P1] AC5: should throw NotFoundException when document not found', async () => {
      // GIVEN: Document does not exist
      const userId = 'user-uuid-123';
      const documentId = 'non-existent-doc';

      mockDocumentRepository.findOne.mockResolvedValue(null);

      // WHEN/THEN: Should throw NotFoundException
      await expect(service.addFavorite(userId, documentId)).rejects.toThrow(
        NotFoundException,
      );
    });
  });

  describe('removeFavorite', () => {
    it('[P1] AC3: should remove document from favorites', async () => {
      // GIVEN: Document is favorited
      const userId = 'user-uuid-123';
      const documentId = 'doc-uuid-123';
      const favorite = { id: 'fav-uuid', documentId, usersId: userId };

      mockFavoriteRepository.findOne.mockResolvedValue(favorite);
      mockFavoriteRepository.remove.mockResolvedValue(undefined);

      // WHEN: Removing from favorites
      await service.removeFavorite(userId, documentId);

      // THEN: Favorite is removed
      expect(mockFavoriteRepository.remove).toHaveBeenCalledWith(favorite);
    });

    it('[P1] should throw NotFoundException when not favorited', async () => {
      // GIVEN: Document is not favorited
      const userId = 'user-uuid-123';
      const documentId = 'doc-uuid-123';

      mockFavoriteRepository.findOne.mockResolvedValue(null);

      // WHEN/THEN: Should throw NotFoundException
      await expect(service.removeFavorite(userId, documentId)).rejects.toThrow(
        NotFoundException,
      );
      expect(mockFavoriteRepository.remove).not.toHaveBeenCalled();
    });
  });
});
