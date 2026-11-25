import { Test, TestingModule } from '@nestjs/testing';
import {
  EmbeddingStatusConsumer,
  EmbeddingStatusMessage,
} from './embedding-status.consumer';
import { EmbeddingStatusGateway } from '../../document/services/embedding-status.gateway';

describe('EmbeddingStatusConsumer', () => {
  let consumer: EmbeddingStatusConsumer;

  const mockEmbeddingStatusGateway = {
    emit: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        EmbeddingStatusConsumer,
        {
          provide: EmbeddingStatusGateway,
          useValue: mockEmbeddingStatusGateway,
        },
      ],
    }).compile();

    consumer = module.get<EmbeddingStatusConsumer>(EmbeddingStatusConsumer);

    jest.clearAllMocks();
  });

  it('should be defined', () => {
    expect(consumer).toBeDefined();
  });

  describe('handleStatusEvent', () => {
    it('should emit SSE event for parsing status', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'parsing',
        message: 'Parsing document...',
        timestamp: '2024-01-01T00:00:00Z',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).toHaveBeenCalledWith({
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'parsing',
        message: 'Parsing document...',
        metadata: undefined,
        timestamp: '2024-01-01T00:00:00Z',
      });
    });

    it('should emit SSE event for completed status', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'completed',
        message: 'Embedding completed successfully',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          documentId: 'doc-123',
          versionId: 'version-123',
          status: 'completed',
          message: 'Embedding completed successfully',
        }),
      );
    });

    it('should emit SSE event for failed status', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'failed',
        message: 'Embedding failed: Out of memory',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          documentId: 'doc-123',
          versionId: 'version-123',
          status: 'failed',
          message: 'Embedding failed: Out of memory',
        }),
      );
    });

    it('should emit SSE event for chunking status', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'chunking',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          documentId: 'doc-123',
          versionId: 'version-123',
          status: 'chunking',
        }),
      );
    });

    it('should emit SSE event for embedding status', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'embedding',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          documentId: 'doc-123',
          versionId: 'version-123',
          status: 'embedding',
        }),
      );
    });

    it('should emit SSE event for upserting status', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'upserting',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          documentId: 'doc-123',
          versionId: 'version-123',
          status: 'upserting',
        }),
      );
    });

    it('should skip invalid message without documentId', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: '',
        versionId: 'version-123',
        status: 'parsing',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).not.toHaveBeenCalled();
    });

    it('should skip invalid message without versionId', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: '',
        status: 'parsing',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).not.toHaveBeenCalled();
    });

    it('should skip invalid message without status', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: '',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).not.toHaveBeenCalled();
    });

    it('should skip unknown status', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'unknown-status',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).not.toHaveBeenCalled();
    });

    it('should handle case-insensitive status', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'COMPLETED',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          status: 'completed',
        }),
      );
    });

    it('should include metadata in SSE event', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'embedding',
        metadata: { chunksCount: 10, progress: 50 },
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          metadata: { chunksCount: 10, progress: 50 },
        }),
      );
    });

    it('should generate timestamp if not provided', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'completed',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          timestamp: expect.any(String),
        }),
      );
    });

    it('should use provided timestamp', async () => {
      const message: EmbeddingStatusMessage = {
        documentId: 'doc-123',
        versionId: 'version-123',
        status: 'parsing',
        timestamp: '2024-01-01T12:00:00Z',
      };

      await consumer.handleStatusEvent(message);

      expect(mockEmbeddingStatusGateway.emit).toHaveBeenCalledWith(
        expect.objectContaining({
          timestamp: '2024-01-01T12:00:00Z',
        }),
      );
    });
  });
});
