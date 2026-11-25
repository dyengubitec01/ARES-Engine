import { Test, TestingModule } from '@nestjs/testing';
import {
  EmbeddingStatusGateway,
  EmbeddingStatusEvent,
} from './embedding-status.gateway';

describe('EmbeddingStatusGateway', () => {
  let gateway: EmbeddingStatusGateway;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [EmbeddingStatusGateway],
    }).compile();

    gateway = module.get<EmbeddingStatusGateway>(EmbeddingStatusGateway);
  });

  afterEach(() => {
    gateway.onModuleDestroy();
  });

  it('should be defined', () => {
    expect(gateway).toBeDefined();
  });

  describe('subscribe', () => {
    it('should return an observable for SSE events', () => {
      const observable = gateway.subscribe('doc-123', 'user-456');
      expect(observable).toBeDefined();
      expect(typeof observable.subscribe).toBe('function');
    });

    it('should increment subscriber count for a document', () => {
      gateway.subscribe('doc-123', 'user-456');
      expect(gateway.getSubscriberCount('doc-123')).toBe(1);

      gateway.subscribe('doc-123', 'user-789');
      expect(gateway.getSubscriberCount('doc-123')).toBe(2);
    });

    it('should track subscribers for different documents separately', () => {
      gateway.subscribe('doc-123', 'user-456');
      gateway.subscribe('doc-456', 'user-789');

      expect(gateway.getSubscriberCount('doc-123')).toBe(1);
      expect(gateway.getSubscriberCount('doc-456')).toBe(1);
      expect(gateway.getTotalSubscriberCount()).toBe(2);
    });
  });

  describe('unsubscribe', () => {
    it('should decrement subscriber count', () => {
      gateway.subscribe('doc-123', 'user-456');
      gateway.subscribe('doc-123', 'user-789');
      expect(gateway.getSubscriberCount('doc-123')).toBe(2);

      gateway.unsubscribe('doc-123', 'user-456');
      expect(gateway.getSubscriberCount('doc-123')).toBe(1);
    });

    it('should remove document from map when no subscribers remain', () => {
      gateway.subscribe('doc-123', 'user-456');
      expect(gateway.getSubscriberCount('doc-123')).toBe(1);

      gateway.unsubscribe('doc-123', 'user-456');
      expect(gateway.getSubscriberCount('doc-123')).toBe(0);
    });

    it('should handle unsubscribe for non-existent document', () => {
      expect(() =>
        gateway.unsubscribe('non-existent', 'user-456'),
      ).not.toThrow();
    });

    it('should handle unsubscribe for non-existent user', () => {
      gateway.subscribe('doc-123', 'user-456');
      expect(() =>
        gateway.unsubscribe('doc-123', 'non-existent'),
      ).not.toThrow();
      expect(gateway.getSubscriberCount('doc-123')).toBe(1);
    });
  });

  describe('emit', () => {
    it('should emit event to subscribed document', (done) => {
      const event: EmbeddingStatusEvent = {
        documentId: 'doc-123',
        versionId: 'version-456',
        status: 'parsing',
        message: 'Parsing document...',
        timestamp: '2024-01-01T00:00:00Z',
      };

      const observable = gateway.subscribe('doc-123', 'user-456');

      observable.subscribe({
        next: (messageEvent) => {
          expect(messageEvent.type).toBe('status');
          const data = JSON.parse(messageEvent.data);
          expect(data.documentId).toBe('doc-123');
          expect(data.status).toBe('parsing');
          done();
        },
      });

      gateway.emit(event);
    });

    it('should not emit event to unrelated document subscribers', (done) => {
      const event: EmbeddingStatusEvent = {
        documentId: 'doc-123',
        versionId: 'version-456',
        status: 'parsing',
        timestamp: '2024-01-01T00:00:00Z',
      };

      const observable = gateway.subscribe('doc-other', 'user-456');
      let received = false;

      observable.subscribe({
        next: () => {
          received = true;
        },
      });

      gateway.emit(event);

      // Wait a bit and check that no event was received
      setTimeout(() => {
        expect(received).toBe(false);
        done();
      }, 100);
    });

    it('should emit to multiple subscribers of the same document', (done) => {
      const event: EmbeddingStatusEvent = {
        documentId: 'doc-123',
        versionId: 'version-456',
        status: 'completed',
        timestamp: '2024-01-01T00:00:00Z',
      };

      let receivedCount = 0;

      const observable1 = gateway.subscribe('doc-123', 'user-1');
      const observable2 = gateway.subscribe('doc-123', 'user-2');

      observable1.subscribe({
        next: () => {
          receivedCount++;
          if (receivedCount === 2) done();
        },
      });

      observable2.subscribe({
        next: () => {
          receivedCount++;
          if (receivedCount === 2) done();
        },
      });

      gateway.emit(event);
    });
  });

  describe('getSubscriberCount', () => {
    it('should return 0 for document with no subscribers', () => {
      expect(gateway.getSubscriberCount('non-existent')).toBe(0);
    });
  });

  describe('getTotalSubscriberCount', () => {
    it('should return 0 when no subscribers', () => {
      expect(gateway.getTotalSubscriberCount()).toBe(0);
    });

    it('should return total across all documents', () => {
      gateway.subscribe('doc-1', 'user-1');
      gateway.subscribe('doc-1', 'user-2');
      gateway.subscribe('doc-2', 'user-3');
      gateway.subscribe('doc-3', 'user-4');

      expect(gateway.getTotalSubscriberCount()).toBe(4);
    });
  });

  describe('onModuleDestroy', () => {
    it('should clean up all subscribers', () => {
      gateway.subscribe('doc-1', 'user-1');
      gateway.subscribe('doc-2', 'user-2');

      gateway.onModuleDestroy();

      expect(gateway.getTotalSubscriberCount()).toBe(0);
    });
  });
});
