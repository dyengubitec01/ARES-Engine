import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

export interface QdrantScrollResponse {
  result: {
    points: Array<{
      id: string | number;
      payload?: Record<string, unknown>;
    }>;
    next_page_offset?: string | number | null;
  };
}

@Injectable()
export class QdrantService {
  private readonly logger = new Logger(QdrantService.name);
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly collection: string;
  private readonly timeoutMs = 30000;

  constructor(private configService: ConfigService) {
    this.baseUrl = this.configService.get<string>('external.qdrant.url') || '';
    this.apiKey =
      this.configService.get<string>('external.qdrant.apiKey') || '';
    this.collection =
      this.configService.get<string>('external.qdrant.collection') || '';
  }

  /**
   * Scroll points by filter (paginated)
   * POST /collections/{collection}/points/scroll
   */
  async scrollPoints(
    filter: Record<string, unknown>,
  ): Promise<Array<{ id: string | number }>> {
    if (!this.baseUrl || !this.collection) {
      this.logger.warn('Qdrant not configured, skipping scroll');
      return [];
    }

    const url = `${this.baseUrl}/collections/${this.collection}/points/scroll`;
    const allPoints: Array<{ id: string | number }> = [];
    let offset: string | number | null = null;

    do {
      const body: Record<string, unknown> = {
        filter,
        limit: 100,
        with_payload: false,
      };
      if (offset !== null) {
        body.offset = offset;
      }

      const response = await this.fetchWithTimeout(url, {
        method: 'POST',
        headers: this.buildHeaders(),
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(
          `Qdrant scroll failed: ${response.status} - ${errorText}`,
        );
      }

      const data = (await response.json()) as QdrantScrollResponse;
      allPoints.push(...data.result.points.map((p) => ({ id: p.id })));
      offset = data.result.next_page_offset ?? null;
    } while (offset !== null);

    this.logger.debug(`Scrolled ${allPoints.length} points from Qdrant`);
    return allPoints;
  }

  /**
   * Update payload on specific points
   * POST /collections/{collection}/points/payload
   */
  async updatePayload(
    pointIds: Array<string | number>,
    payload: Record<string, unknown>,
  ): Promise<void> {
    if (!this.baseUrl || !this.collection) {
      this.logger.warn('Qdrant not configured, skipping payload update');
      return;
    }

    if (pointIds.length === 0) {
      this.logger.debug('No point IDs to update');
      return;
    }

    const url = `${this.baseUrl}/collections/${this.collection}/points/payload`;

    const response = await this.fetchWithTimeout(url, {
      method: 'POST',
      headers: this.buildHeaders(),
      body: JSON.stringify({
        points: pointIds,
        payload,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `Qdrant payload update failed: ${response.status} - ${errorText}`,
      );
    }

    this.logger.log(`Updated payload on ${pointIds.length} points in Qdrant`);
  }

  /**
   * Deactivate all points for a given document ID
   * Sets is_active: "N" on all matching points
   */
  async deactivateByDocumentId(documentId: string): Promise<number> {
    const filter = {
      must: [
        {
          key: 'doc_id',
          match: { value: documentId },
        },
      ],
    };

    const points = await this.scrollPoints(filter);
    if (points.length === 0) {
      this.logger.debug(`No Qdrant points found for document ${documentId}`);
      return 0;
    }

    const pointIds = points.map((p) => p.id);
    await this.updatePayload(pointIds, { is_active: 'N' });

    return pointIds.length;
  }

  /**
   * Reactivate all points for a given document ID (rollback용)
   * Sets is_active: "Y" on all matching points
   */
  async reactivateByDocumentId(documentId: string): Promise<number> {
    const filter = {
      must: [
        {
          key: 'doc_id',
          match: { value: documentId },
        },
      ],
    };

    const points = await this.scrollPoints(filter);
    if (points.length === 0) {
      this.logger.debug(
        `No Qdrant points found for document ${documentId} to reactivate`,
      );
      return 0;
    }

    const pointIds = points.map((p) => p.id);
    await this.updatePayload(pointIds, { is_active: 'Y' });

    this.logger.log(
      `Reactivated ${pointIds.length} Qdrant points for document ${documentId}`,
    );
    return pointIds.length;
  }

  /**
   * Delete all points for a given document ID (hard delete용)
   * POST /collections/{collection}/points/delete
   */
  async deleteByDocumentId(documentId: string): Promise<number> {
    if (!this.baseUrl || !this.collection) {
      this.logger.warn('Qdrant not configured, skipping delete');
      return 0;
    }

    const filter = {
      must: [
        {
          key: 'doc_id',
          match: { value: documentId },
        },
      ],
    };

    // First count points to return
    const points = await this.scrollPoints(filter);
    if (points.length === 0) {
      this.logger.debug(
        `No Qdrant points found for document ${documentId} to delete`,
      );
      return 0;
    }

    const url = `${this.baseUrl}/collections/${this.collection}/points/delete`;

    const response = await this.fetchWithTimeout(url, {
      method: 'POST',
      headers: this.buildHeaders(),
      body: JSON.stringify({
        filter,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(
        `Qdrant delete failed: ${response.status} - ${errorText}`,
      );
    }

    this.logger.log(
      `Deleted ${points.length} Qdrant points for document ${documentId}`,
    );
    return points.length;
  }

  /**
   * Health check for Qdrant service
   */
  async healthCheck(): Promise<boolean> {
    if (!this.baseUrl) {
      return false;
    }

    try {
      const response = await this.fetchWithTimeout(`${this.baseUrl}/healthz`, {
        method: 'GET',
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  private buildHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this.apiKey) {
      headers['api-key'] = this.apiKey;
    }
    return headers;
  }

  private async fetchWithTimeout(
    url: string,
    options: RequestInit,
  ): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      return response;
    } finally {
      clearTimeout(timeoutId);
    }
  }
}
