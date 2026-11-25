import { Injectable, Logger, OnModuleDestroy } from '@nestjs/common';
import { Subject, Observable, filter, map } from 'rxjs';

/**
 * SSE Event for embedding status updates
 */
export interface EmbeddingStatusEvent {
  documentId: string;
  versionId: string;
  status: string;
  message?: string;
  metadata?: Record<string, unknown>;
  timestamp: string;
}

/**
 * MessageEvent for SSE response
 */
interface MessageEvent {
  data: string;
  type?: string;
}

/**
 * Subscriber info for cleanup
 */
interface Subscriber {
  documentId: string;
  userId: string;
  subject: Subject<EmbeddingStatusEvent>;
}

/**
 * Gateway service for managing SSE subscriptions and broadcasting embedding status events
 * Story 4.10: Kafka 상태 Consumer + SSE 스트리밍
 */
@Injectable()
export class EmbeddingStatusGateway implements OnModuleDestroy {
  private readonly logger = new Logger(EmbeddingStatusGateway.name);

  // Global event stream - all status events go through here
  private readonly eventStream = new Subject<EmbeddingStatusEvent>();

  // Track active subscribers for logging/debugging
  private readonly subscribers = new Map<string, Subscriber[]>();

  onModuleDestroy() {
    this.eventStream.complete();
    this.subscribers.clear();
    this.logger.log(
      'EmbeddingStatusGateway destroyed, all subscribers cleaned up',
    );
  }

  /**
   * Subscribe to status events for a specific document
   * Returns an Observable that emits MessageEvent for SSE
   *
   * @param documentId - Document to subscribe to
   * @param userId - User ID for tracking
   * @returns Observable<MessageEvent> for SSE streaming
   */
  subscribe(documentId: string, userId: string): Observable<MessageEvent> {
    const subscriberId = `${documentId}-${userId}-${Date.now()}`;

    this.logger.debug(`New subscriber: ${subscriberId}`);

    // Track subscriber
    if (!this.subscribers.has(documentId)) {
      this.subscribers.set(documentId, []);
    }

    const subscriberSubject = new Subject<EmbeddingStatusEvent>();
    const subscriber: Subscriber = {
      documentId,
      userId,
      subject: subscriberSubject,
    };
    this.subscribers.get(documentId)!.push(subscriber);

    // Return observable that filters events for this document
    return this.eventStream.pipe(
      filter((event) => event.documentId === documentId),
      map((event) => ({
        type: 'status',
        data: JSON.stringify(event),
      })),
    );
  }

  /**
   * Unsubscribe from status events
   * Called when SSE connection is closed
   *
   * @param documentId - Document ID
   * @param userId - User ID
   */
  unsubscribe(documentId: string, userId: string): void {
    const subs = this.subscribers.get(documentId);
    if (subs) {
      const index = subs.findIndex((s) => s.userId === userId);
      if (index !== -1) {
        subs[index].subject.complete();
        subs.splice(index, 1);
        this.logger.debug(`Unsubscribed: ${documentId}-${userId}`);
      }
      if (subs.length === 0) {
        this.subscribers.delete(documentId);
      }
    }
  }

  /**
   * Emit status event to all subscribers of a document
   * Called by Kafka consumer when status message is received
   *
   * @param event - Embedding status event
   */
  emit(event: EmbeddingStatusEvent): void {
    const subscriberCount = this.subscribers.get(event.documentId)?.length ?? 0;
    this.logger.debug(
      `Emitting status event for document ${event.documentId} to ${subscriberCount} subscribers: ${event.status}`,
    );
    this.eventStream.next(event);
  }

  /**
   * Get count of active subscribers for a document
   * Useful for debugging and metrics
   */
  getSubscriberCount(documentId: string): number {
    return this.subscribers.get(documentId)?.length ?? 0;
  }

  /**
   * Get total count of all active subscribers
   */
  getTotalSubscriberCount(): number {
    let total = 0;
    for (const subs of this.subscribers.values()) {
      total += subs.length;
    }
    return total;
  }
}
