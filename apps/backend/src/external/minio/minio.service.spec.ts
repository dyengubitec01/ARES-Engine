/* eslint-disable @typescript-eslint/unbound-method */
import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { ServiceUnavailableException } from '@nestjs/common';
import { MinioService } from './minio.service';
import * as Minio from 'minio';

// Mock the minio module
jest.mock('minio');

describe('MinioService', () => {
  let service: MinioService;
  let mockMinioClient: jest.Mocked<Minio.Client>;

  const mockConfig = {
    'external.minio.endpoint': 'localhost',
    'external.minio.port': 9000,
    'external.minio.useSSL': false,
    'external.minio.accessKey': 'minioadmin',
    'external.minio.secretKey': 'minioadmin',
    'external.minio.bucket': 'documents',
  };

  const mockConfigService = {
    get: jest.fn((key: string) => mockConfig[key as keyof typeof mockConfig]),
  };

  beforeEach(async () => {
    // Reset mocks
    jest.clearAllMocks();

    // Create mock MinIO client methods
    mockMinioClient = {
      bucketExists: jest.fn(),
      makeBucket: jest.fn(),
      presignedPutObject: jest.fn(),
    } as unknown as jest.Mocked<Minio.Client>;

    // Mock Minio.Client constructor
    (Minio.Client as jest.MockedClass<typeof Minio.Client>).mockImplementation(
      () => mockMinioClient,
    );

    const module: TestingModule = await Test.createTestingModule({
      providers: [
        MinioService,
        {
          provide: ConfigService,
          useValue: mockConfigService,
        },
      ],
    }).compile();

    service = module.get<MinioService>(MinioService);
  });

  describe('onModuleInit', () => {
    it('[P1] should verify bucket exists on initialization (AC1)', async () => {
      // GIVEN: MinIO server is available, bucket exists
      mockMinioClient.bucketExists.mockResolvedValue(true);

      // WHEN: Service initializes
      await service.onModuleInit();

      // THEN: Connection is verified
      expect(mockMinioClient.bucketExists).toHaveBeenCalledWith('documents');
    });

    it('[P1] should create bucket if it does not exist (AC1)', async () => {
      // GIVEN: Bucket does not exist
      mockMinioClient.bucketExists.mockResolvedValue(false);
      mockMinioClient.makeBucket.mockResolvedValue(undefined as never);

      // WHEN: Service initializes
      await service.onModuleInit();

      // THEN: Bucket is created
      expect(mockMinioClient.makeBucket).toHaveBeenCalledWith('documents');
    });

    it('[P1] should throw ServiceUnavailableException on connection failure (AC6)', async () => {
      // GIVEN: MinIO server is unavailable
      mockMinioClient.bucketExists.mockRejectedValue(
        new Error('Connection refused'),
      );

      // WHEN/THEN: Throws ServiceUnavailableException
      await expect(service.onModuleInit()).rejects.toThrow(
        ServiceUnavailableException,
      );
    });
  });

  describe('generatePresignedPutUrl', () => {
    it('[P1] should generate pre-signed PUT URL with default expiry (AC2)', async () => {
      // GIVEN: Valid object key
      const objectKey = 'test/file.pdf';
      const expectedUrl =
        'http://localhost:9000/documents/test/file.pdf?presigned';
      mockMinioClient.presignedPutObject.mockResolvedValue(expectedUrl);

      // WHEN: Generating pre-signed PUT URL
      const result = await service.generatePresignedPutUrl(objectKey);

      // THEN: Returns URL with default 1 hour expiry
      expect(result).toBe(expectedUrl);
      expect(mockMinioClient.presignedPutObject).toHaveBeenCalledWith(
        'documents',
        objectKey,
        3600, // default 1 hour
      );
    });

    it('[P1] should generate pre-signed PUT URL with custom expiry (AC2)', async () => {
      // GIVEN: Valid object key and custom expiry
      const objectKey = 'test/file.pdf';
      const customExpiry = 7200; // 2 hours
      const expectedUrl =
        'http://localhost:9000/documents/test/file.pdf?presigned';
      mockMinioClient.presignedPutObject.mockResolvedValue(expectedUrl);

      // WHEN: Generating pre-signed PUT URL with custom expiry
      const result = await service.generatePresignedPutUrl(
        objectKey,
        customExpiry,
      );

      // THEN: Returns URL with custom expiry
      expect(result).toBe(expectedUrl);
      expect(mockMinioClient.presignedPutObject).toHaveBeenCalledWith(
        'documents',
        objectKey,
        customExpiry,
      );
    });

    it('[P2] should throw ServiceUnavailableException on error (AC6)', async () => {
      // GIVEN: MinIO operation fails
      const objectKey = 'test/file.pdf';
      mockMinioClient.presignedPutObject.mockRejectedValue(
        new Error('Network error'),
      );

      // WHEN/THEN: Throws ServiceUnavailableException
      await expect(service.generatePresignedPutUrl(objectKey)).rejects.toThrow(
        ServiceUnavailableException,
      );
    });
  });

  describe('getBucket', () => {
    it('[P2] should return the configured bucket name', () => {
      // GIVEN: Service is initialized with bucket config

      // WHEN: Getting bucket name
      const result = service.getBucket();

      // THEN: Returns configured bucket
      expect(result).toBe('documents');
    });
  });
});
