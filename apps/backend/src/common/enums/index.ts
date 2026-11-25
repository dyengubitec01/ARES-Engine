// ============================================================
// DY-OOO AI 솔루션 - Database ENUM Types
// ============================================================

export enum AuthorityType {
  UPLOADER = 'uploader',
  ADMIN = 'admin',
  EMBEDDING = 'embedding',
  SOFT_DELETE = 'soft_delete',
  DOWNLOAD = 'download',
}

export enum DocStatus {
  UPLOADING = 'uploading',
  UPLOADED = 'uploaded',
  VALIDATING = 'validating',
  PENDING_APPROVAL = 'pending_approval',
  QUEUED = 'queued',
  PARSING = 'parsing',
  CHUNKING = 'chunking',
  EMBEDDING = 'embedding',
  UPSERTING = 'upserting',
  COMPLETED = 'completed',
  FAILED = 'failed',
  REJECTED = 'rejected',
  DELETED = 'deleted',
}

export enum JobStatus {
  QUEUED = 'queued',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export enum EventSource {
  ER = 'er',
  EW = 'ew',
  BE = 'be',
  SYSTEM = 'system',
}

export enum ObjectKind {
  RAW = 'raw',
  CHUNKS = 'chunks',
  EMBEDDINGS = 'embeddings',
  META = 'meta',
}

export enum DistanceMetric {
  COSINE = 'cosine',
  EUCLIDEAN = 'euclidean',
  DOT = 'dot',
}

export enum FeedbackType {
  LIKE = 'like',
  DISLIKE = 'dislike',
}

export enum BoardTypeName {
  FEEDBACK = 'feedback',
  SUGGESTION = 'suggestion',
  ANSWER_SUGGESTION = 'answer_suggestion',
}
