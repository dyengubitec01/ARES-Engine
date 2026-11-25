import { registerAs } from '@nestjs/config';

export default registerAs('external', () => ({
  chatbot: {
    url: process.env.CHATBOT_AGENT_URL || 'http://localhost:8000',
  },
  embedding: {
    url: process.env.EMBEDDING_SERVER_URL || 'http://localhost:8000',
    chunkingProfile: process.env.EMBEDDING_CHUNKING_PROFILE || 'default_v1',
    embeddingProfile: process.env.EMBEDDING_MODEL_PROFILE || 'bge_m3_v1',
  },
  minio: {
    endpoint: process.env.MINIO_ENDPOINT || 'localhost',
    port: parseInt(process.env.MINIO_PORT || '9000', 10),
    useSSL: process.env.MINIO_USE_SSL === 'true',
    accessKey: process.env.MINIO_ACCESS_KEY,
    secretKey: process.env.MINIO_SECRET_KEY,
    bucket: process.env.MINIO_BUCKET || 'documents',
    publicUrl: process.env.MINIO_PUBLIC_URL || '',
  },
  kafka: {
    brokers: (process.env.KAFKA_BROKERS || 'localhost:9092').split(','),
    clientId: process.env.KAFKA_CLIENT_ID || 'backend',
  },
  qdrant: {
    url: process.env.QDRANT_URL || '', // 빈 값이면 비활성화
    apiKey: process.env.QDRANT_API_KEY || '',
    collection: process.env.QDRANT_COLLECTION || 'rag_chunks_v1',
  },
  redis: {
    host: process.env.REDIS_HOST || '', // 빈 값이면 비활성화
    port: parseInt(process.env.REDIS_PORT || '6379', 10),
    password: process.env.REDIS_PASSWORD || '',
    db: parseInt(process.env.REDIS_DB || '0', 10),
  },
  tools: {
    url: process.env.TOOLS_API_URL || '', // 빈 값이면 비활성화
  },
}));
