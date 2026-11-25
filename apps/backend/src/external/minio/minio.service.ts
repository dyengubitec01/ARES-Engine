import {
  Injectable,
  Logger,
  OnModuleInit,
  ServiceUnavailableException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import * as Minio from 'minio';

@Injectable()
export class MinioService implements OnModuleInit {
  private readonly logger = new Logger(MinioService.name);
  private readonly client: Minio.Client;
  /** Separate client for presigned URLs, configured with the public endpoint */
  private readonly presignedClient: Minio.Client;
  private readonly bucket: string;

  // Default expiration time for pre-signed URLs (1 hour in seconds)
  private readonly DEFAULT_EXPIRY = 3600;

  // Retry configuration
  private readonly MAX_RETRIES = 3;
  private readonly INITIAL_DELAY_MS = 1000;

  constructor(private configService: ConfigService) {
    const endpoint = this.configService.get<string>('external.minio.endpoint');
    const port = this.configService.get<number>('external.minio.port');
    const useSSL = this.configService.get<boolean>('external.minio.useSSL');
    const accessKey = this.configService.get<string>(
      'external.minio.accessKey',
    );
    const secretKey = this.configService.get<string>(
      'external.minio.secretKey',
    );

    this.bucket =
      this.configService.get<string>('external.minio.bucket') || 'documents';
    const publicUrl =
      this.configService.get<string>('external.minio.publicUrl') || '';

    this.client = new Minio.Client({
      endPoint: endpoint || 'localhost',
      port: port || 9000,
      useSSL: useSSL || false,
      accessKey: accessKey || '',
      secretKey: secretKey || '',
    });

    // Presigned URL client: use public endpoint so signatures match the URL the frontend uses
    if (publicUrl) {
      const parsed = new URL(publicUrl);
      this.presignedClient = new Minio.Client({
        endPoint: parsed.hostname,
        port: parsed.port
          ? Number(parsed.port)
          : parsed.protocol === 'https:'
            ? 443
            : 80,
        useSSL: parsed.protocol === 'https:',
        accessKey: accessKey || '',
        secretKey: secretKey || '',
      });
      this.logger.log(
        `Presigned URL client configured with public endpoint: ${parsed.hostname}:${parsed.port || (parsed.protocol === 'https:' ? 443 : 80)}`,
      );
    } else {
      this.presignedClient = this.client;
    }
  }

  /**
   * Verify MinIO connection on module initialization (AC1, AC6)
   * Note: Bucket existence check is skipped if MINIO_SKIP_BUCKET_CHECK=true
   * This is useful when the service account has limited permissions (e.g., only PutObject on specific prefix)
   */
  async onModuleInit(): Promise<void> {
    const skipBucketCheck =
      this.configService.get<string>('MINIO_SKIP_BUCKET_CHECK') === 'true';

    if (skipBucketCheck) {
      this.logger.log(
        `MinIO configured (bucket check skipped). Bucket: ${this.bucket}`,
      );
      return;
    }

    try {
      const bucketExists = await this.client.bucketExists(this.bucket);
      if (!bucketExists) {
        this.logger.warn(
          `Bucket '${this.bucket}' does not exist. Creating it...`,
        );
        await this.client.makeBucket(this.bucket);
        this.logger.log(`Bucket '${this.bucket}' created successfully`);
      }
      this.logger.log(`MinIO connection established. Bucket: ${this.bucket}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Failed to connect to MinIO: ${message}`);
      throw new ServiceUnavailableException(
        `MinIO connection failed: ${message}`,
      );
    }
  }

  /**
   * Retry wrapper with exponential backoff
   * Retries: 1s → 2s → 4s
   */
  private async withRetry<T>(
    operation: () => Promise<T>,
    context: string,
  ): Promise<T> {
    let lastError: Error = new Error('Unknown error');

    for (let attempt = 1; attempt <= this.MAX_RETRIES; attempt++) {
      try {
        return await operation();
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));

        if (attempt < this.MAX_RETRIES) {
          const delay = this.INITIAL_DELAY_MS * Math.pow(2, attempt - 1);
          this.logger.warn(
            `MinIO ${context} failed (attempt ${attempt}/${this.MAX_RETRIES}): ${lastError.message}. Retrying in ${delay}ms...`,
          );
          await this.sleep(delay);
        }
      }
    }

    this.logger.error(
      `MinIO ${context} failed after ${this.MAX_RETRIES} attempts: ${lastError.message}`,
    );
    throw new ServiceUnavailableException(
      `MinIO ${context} failed after retries: ${lastError.message}`,
    );
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Generate a pre-signed PUT URL for uploading objects (AC2)
   * Uses presignedClient so the signature matches the public endpoint the frontend uses.
   * @param objectKey - The object key (file path) in the bucket
   * @param expiresIn - Expiration time in seconds (default: 1 hour)
   */
  async generatePresignedPutUrl(
    objectKey: string,
    expiresIn: number = this.DEFAULT_EXPIRY,
  ): Promise<string> {
    return this.withRetry(async () => {
      const url = await this.presignedClient.presignedPutObject(
        this.bucket,
        objectKey,
        expiresIn,
      );
      this.logger.debug(
        `Generated pre-signed PUT URL for ${objectKey} (expires in ${expiresIn}s)`,
      );
      return url;
    }, `generatePresignedPutUrl(${objectKey})`);
  }

  /**
   * Generate a pre-signed GET URL for downloading objects
   * Uses presignedClient so the signature matches the public endpoint the frontend uses.
   * @param objectKey - The object key (file path) in the bucket
   * @param expiresIn - Expiration time in seconds (default: 1 hour)
   */
  async generatePresignedGetUrl(
    objectKey: string,
    expiresIn: number = this.DEFAULT_EXPIRY,
  ): Promise<string> {
    return this.withRetry(async () => {
      const url = await this.presignedClient.presignedGetObject(
        this.bucket,
        objectKey,
        expiresIn,
      );
      this.logger.debug(
        `Generated pre-signed GET URL for ${objectKey} (expires in ${expiresIn}s)`,
      );
      return url;
    }, `generatePresignedGetUrl(${objectKey})`);
  }

  /**
   * Upload a buffer directly to MinIO
   * @param objectKey - The object key (file path) in the bucket
   * @param buffer - The file buffer to upload
   * @param contentType - The MIME type of the file
   */
  async uploadBuffer(
    objectKey: string,
    buffer: Buffer,
    contentType: string,
  ): Promise<void> {
    return this.withRetry(async () => {
      await this.client.putObject(
        this.bucket,
        objectKey,
        buffer,
        buffer.length,
        {
          'Content-Type': contentType,
        },
      );
      this.logger.debug(
        `Uploaded object: ${objectKey} (${buffer.length} bytes)`,
      );
    }, `uploadBuffer(${objectKey})`);
  }

  /**
   * Get an object from the bucket as a Buffer
   * @param objectKey - The object key (file path) in the bucket
   * @returns Buffer containing the object data
   */
  async getObject(objectKey: string): Promise<Buffer> {
    return this.withRetry(async () => {
      const stream = await this.client.getObject(this.bucket, objectKey);
      const chunks: Buffer[] = [];

      return new Promise<Buffer>((resolve, reject) => {
        stream.on('data', (chunk: Buffer) => chunks.push(chunk));
        stream.on('end', () => {
          this.logger.debug(`Downloaded object: ${objectKey}`);
          resolve(Buffer.concat(chunks));
        });
        stream.on('error', (error) => {
          const message =
            error instanceof Error ? error.message : 'Unknown error';
          reject(new Error(`Failed to get object: ${message}`));
        });
      });
    }, `getObject(${objectKey})`);
  }

  /**
   * Get a JSON file from the bucket, parse and return as object
   * @param objectKey - The object key (file path) in the bucket
   * @returns Parsed JSON object, or null if not found
   */
  async getJsonObject<T = Record<string, unknown>>(
    objectKey: string,
  ): Promise<T | null> {
    try {
      const buffer = await this.getObject(objectKey);
      return JSON.parse(buffer.toString('utf-8')) as T;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      if (message.includes('NoSuchKey') || message.includes('Not Found')) {
        this.logger.debug(`JSON object not found: ${objectKey}`);
        return null;
      }
      throw error;
    }
  }

  /**
   * Update a JSON file in the bucket (Get → Merge → Put)
   * @param objectKey - The object key (file path) in the bucket
   * @param updates - Partial object to merge into existing JSON
   * @returns true if updated, false if file not found
   */
  async updateJsonObject(
    objectKey: string,
    updates: Record<string, unknown>,
  ): Promise<boolean> {
    const existing = await this.getJsonObject(objectKey);
    if (!existing) {
      return false;
    }

    const merged = { ...existing, ...updates };
    const buffer = Buffer.from(JSON.stringify(merged, null, 2));
    await this.uploadBuffer(objectKey, buffer, 'application/json');
    this.logger.debug(`Updated JSON object: ${objectKey}`);
    return true;
  }

  /**
   * Check if an object exists in the bucket
   * @param objectKey - The object key (file path) in the bucket
   * @returns true if exists, false otherwise
   */
  async objectExists(objectKey: string): Promise<boolean> {
    try {
      await this.client.statObject(this.bucket, objectKey);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Delete an object from the bucket
   * @param objectKey - The object key (file path) to delete
   */
  async deleteObject(objectKey: string): Promise<void> {
    return this.withRetry(async () => {
      await this.client.removeObject(this.bucket, objectKey);
      this.logger.debug(`Deleted object: ${objectKey}`);
    }, `deleteObject(${objectKey})`);
  }

  /**
   * Delete all objects under a prefix (including folder markers)
   * @param prefix - The prefix to delete (e.g., 'raw/{documentId}/')
   * @returns Number of deleted objects
   */
  async deleteObjectsByPrefix(prefix: string): Promise<number> {
    return this.withRetry(async () => {
      // List all objects with the prefix
      const objects = await this.listObjects(prefix);

      // Collect object names and potential folder markers
      const objectNames = objects.map((obj) => obj.name);

      // Extract unique folder paths that are under the prefix (not parent folders)
      const folderMarkers = new Set<string>();
      for (const obj of objects) {
        // Get folder paths under the prefix only
        const relativePath = obj.name.substring(prefix.length);
        const parts = relativePath.split('/');
        let path = prefix;
        for (let i = 0; i < parts.length - 1; i++) {
          path += parts[i] + '/';
          folderMarkers.add(path);
        }
      }

      // Add folder markers to delete list (only folders under prefix)
      for (const folder of folderMarkers) {
        if (!objectNames.includes(folder)) {
          objectNames.push(folder);
        }
      }

      // Also try to delete the prefix itself as a folder marker
      if (!objectNames.includes(prefix)) {
        objectNames.push(prefix);
      }

      if (objectNames.length === 0) {
        this.logger.debug(`No objects found with prefix: ${prefix}`);
        return 0;
      }

      // Delete all objects and folder markers
      await this.client.removeObjects(this.bucket, objectNames);

      this.logger.debug(
        `Deleted ${objectNames.length} objects/folders with prefix: ${prefix}`,
      );
      return objectNames.length;
    }, `deleteObjectsByPrefix(${prefix})`);
  }

  /**
   * Get the default bucket name
   */
  getBucket(): string {
    return this.bucket;
  }

  /**
   * Health check - verify MinIO connection
   * @returns true if connected, false otherwise
   */
  async healthCheck(): Promise<boolean> {
    try {
      await this.client.bucketExists(this.bucket);
      return true;
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.warn(`MinIO health check failed: ${message}`);
      return false;
    }
  }

  /**
   * List objects in the bucket with a prefix (AC7)
   * Note: Only `raw/*` prefix is accessible due to IAM policy restrictions
   * @param prefix - The prefix to filter objects (default: 'raw/')
   * @returns Array of object info (name, size, lastModified)
   */
  async listObjects(
    prefix: string = 'raw/',
  ): Promise<{ name: string; size: number; lastModified: Date }[]> {
    return this.withRetry(async () => {
      return new Promise((resolve, reject) => {
        const objects: { name: string; size: number; lastModified: Date }[] =
          [];

        const stream = this.client.listObjectsV2(this.bucket, prefix, true);

        stream.on('data', (obj) => {
          if (obj.name) {
            objects.push({
              name: obj.name,
              size: obj.size,
              lastModified: obj.lastModified,
            });
          }
        });

        stream.on('error', (error) => {
          const message =
            error instanceof Error ? error.message : 'Unknown error';
          reject(new Error(`Failed to list objects: ${message}`));
        });

        stream.on('end', () => {
          this.logger.debug(
            `Listed ${objects.length} objects with prefix: ${prefix}`,
          );
          resolve(objects);
        });
      });
    }, `listObjects(${prefix})`);
  }
}
