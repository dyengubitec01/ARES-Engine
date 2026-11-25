# MinIO Pre-signed URL 업로드 플로우 보고서

**작성일:** 2025-12-21
**최종 수정일:** 2026-01-15 (v3.0 경로 구조 변경)
**작성자:** SM Agent (Bob)
**프로젝트:** backend - 사내 AI 게이트웨이

---

## 1. 개요

본 보고서는 **MinIO 파일 업로드 시스템**에서 **Pre-signed URL 방식**을 도입한 배경, 구현 방법, 그리고 프론트엔드-백엔드 간 상호작용을 설명합니다.

---

## 2. 도입 배경

### 2.1 기존 파일 업로드 방식의 문제점

전통적인 파일 업로드 방식:

```
프론트엔드 → (파일 전송) → 백엔드 → (파일 전송) → MinIO
```

**문제점:**
1. **백엔드 서버 부하**: 모든 파일이 백엔드 메모리를 거쳐감
2. **대역폭 낭비**: 파일이 2번 전송됨 (클라이언트→서버, 서버→MinIO)
3. **확장성 제한**: 동시 업로드 시 백엔드 병목 발생
4. **비용 증가**: 백엔드 서버의 네트워크 비용 증가

### 2.2 Pre-signed URL 방식의 장점

```
프론트엔드 ──(메타데이터)──► 백엔드 ──(URL 요청)──► MinIO
     │                                                    │
     └──────────────(파일 직접 업로드)────────────────────┘
```

**이점:**
1. ✅ **성능 향상**: 파일이 클라이언트에서 MinIO로 직접 전송
2. ✅ **서버 부하 감소**: 백엔드는 메타데이터만 처리
3. ✅ **확장성**: 파일 전송 부하가 MinIO로 분산
4. ✅ **보안**: 임시 URL로 제한된 시간만 업로드 가능

---

## 3. 전체 아키텍처

### 3.1 시스템 구성

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│              │      │              │      │              │
│  Frontend    │◄────►│   Backend    │◄────►│    MinIO     │
│  (React)     │      │  (NestJS)    │      │  (S3-like)   │
│              │      │              │      │              │
└──────────────┘      └──────┬───────┘      └──────────────┘
                             │
                             ▼
                      ┌──────────────┐
                      │  PostgreSQL  │
                      │  (Metadata)  │
                      └──────────────┘
```

### 3.2 MinIO 권한 제약사항

현재 서비스 계정에 부여된 IAM 정책:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:AbortMultipartUpload",
        "s3:ListBucketMultipartUploads"
      ],
      "Resource": ["arn:aws:s3:::rag/raw/*"]
    },
    {
      "Effect": "Allow",
      "Action": ["s3:ListBucket"],
      "Resource": ["arn:aws:s3:::rag"],
      "Condition": {
        "StringLike": { "s3:prefix": ["raw/*"] }
      }
    }
  ]
}
```

**허용된 작업:**
- ✅ 파일 업로드 (`s3:PutObject`)
- ✅ 파일 다운로드 (`s3:GetObject`) - 2026-01-14 추가
- ✅ 파일 삭제 (`s3:DeleteObject`) - 2026-01-08 추가
- ✅ 멀티파트 업로드 관리
- ✅ 버킷 목록 조회 (`raw/*` 경로만)

**불가능한 작업:**
- ❌ 메타데이터 조회 (`s3:HeadObject` 권한 없음)

**영향:**
- ✅ Story 4.8 (문서 다운로드 API) 구현 완료 (2026-01-14)
- ✅ Story 4.7 (문서 삭제) Hard Delete 구현 완료 (2026-01-08)
- Story 4.4 (업로드 완료) 파일 존재 검증 불가

### 3.3 지원 파일 형식

업로드 가능한 파일 형식은 백엔드에서 MIME 타입으로 검증됩니다.

| 확장자 | MIME Type | 설명 |
|--------|-----------|------|
| `.pdf` | `application/pdf` | PDF 문서 |
| `.docx` | `application/vnd.openxmlformats-officedocument.wordprocessingml.document` | Word 문서 |
| `.xlsx` | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | Excel 스프레드시트 |
| `.pptx` | `application/vnd.openxmlformats-officedocument.presentationml.presentation` | PowerPoint 프레젠테이션 |
| `.txt` | `text/plain` | 텍스트 파일 |
| `.md` | `text/markdown` | 마크다운 파일 |

**제한 사항:**
- **최대 파일 크기**: 100MB (`MAX_FILE_SIZE = 100 * 1024 * 1024`)
- **미지원 형식**: `.doc`, `.xls`, `.ppt` (구 Office 형식), 이미지, 압축파일 등

**검증 위치:** [create-upload-session.dto.ts](../../src/document/dto/create-upload-session.dto.ts)

### 3.4 MinIO 경로 구조 (v3.0)

**변경 전:**
```
raw/{documentId}/{versionId}/{filename}
```

**변경 후:**
```
raw/{deptId}/{year}/{month}/{documentId}/{filename}
raw/{deptId}/{year}/{month}/{documentId}/manifest.json
```

**경로 구성 요소:**
| 요소 | 설명 | 예시 |
|------|------|------|
| `deptId` | 업로더의 부서 ID (auth_users.auth_dept_id) | `00000000-0000-0000-0000-000000000001` |
| `year` | 업로드 연도 (4자리) | `2026` |
| `month` | 업로드 월 (2자리, 0-패딩) | `01` |
| `documentId` | 문서 ID (UUID) | `abc-123-uuid` |

**이점:**
- ✅ 부서별 데이터 분리 용이
- ✅ 시간 기반 파티셔닝 (연/월별)
- ✅ Embedding Worker가 메타데이터 접근 가능 (manifest.json)

### 3.5 manifest.json 구조

업로드 완료 시 백엔드가 자동 생성하여 MinIO에 업로드하는 메타데이터 파일입니다.

```json
{
  "documentId": "abc-123-uuid",
  "filename": "report.pdf",
  "fileType": "application/pdf",
  "fileSize": 1024000,
  "hash": null,
  "uploader": {
    "id": "user-uuid",
    "name": "홍길동",
    "deptId": "dept-uuid",
    "email": "hong@example.com"
  },
  "uploadedAt": "2026-01-15T12:00:00.000Z",
  "title": "2026년 1월 보고서"
}
```

**필드 설명:**
| 필드 | 타입 | 설명 |
|------|------|------|
| `documentId` | string | 문서 고유 ID |
| `filename` | string | 원본 파일명 |
| `fileType` | string | MIME 타입 |
| `fileSize` | number | 파일 크기 (bytes) |
| `hash` | string \| null | SHA-256 해시 (Worker 처리 후 채워짐) |
| `uploader.id` | string | 업로더 사용자 ID |
| `uploader.name` | string \| null | 업로더 이름 |
| `uploader.deptId` | string | 업로더 부서 ID |
| `uploader.email` | string | 업로더 이메일 |
| `uploadedAt` | string | 업로드 완료 시각 (ISO 8601) |
| `title` | string | 문서 제목 |

**용도:**
- Embedding Worker가 DB 조회 없이 파일 메타데이터 접근 가능
- 감사 추적 (Audit Trail)
- 백업/복원 시 메타데이터 보존

### 3.6 업로드 방식 비교 (원본 파일 vs manifest.json)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                        파일별 업로드 방식 비교                                │
└────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  [원본 파일 업로드]    Pre-signed URL 방식                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Frontend ──(1)──► Backend ──(2)──► MinIO                                  │
│       │                │               │                                    │
│       │ 메타데이터     │ Pre-signed   │                                    │
│       │ 요청           │ URL 생성     │                                    │
│       │                │               │                                    │
│       └────────────────(3)─────────────┘                                    │
│              파일 바이너리 직접 업로드 (PUT)                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  [manifest.json 업로드]    MinIO Client 직접 방식                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Frontend ──────────► Backend ──────────────────► MinIO                    │
│            Complete     │                            │                      │
│            API 호출     │ manifest.json 생성        │                      │
│                         │ & 직접 업로드              │                      │
│                         │ (MINIO_ACCESS_KEY)         │                      │
│                         └────────────────────────────┘                      │
│                            uploadBuffer() 메서드                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

| 항목 | 원본 파일 | manifest.json |
|------|-----------|---------------|
| 업로드 주체 | Frontend (브라우저) | Backend (서버) |
| 업로드 방식 | Pre-signed URL (PUT) | MinIO Client (uploadBuffer) |
| 인증 방식 | 서명된 임시 URL | MINIO_ACCESS_KEY/SECRET_KEY |
| 파일 크기 | 최대 100MB | 수 KB 이하 |
| 시점 | Step 7-8 (MinIO 직접) | Step 12 (Complete API) |

---

## 4. 파일 업로드 플로우

### 4.1 전체 시퀀스 다이어그램

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    Pre-signed URL 파일 업로드 플로우                         │
└────────────────────────────────────────────────────────────────────────────┘

[Frontend]              [Backend]              [PostgreSQL]        [MinIO]
    │                       │                        │                │
    │                       │                        │                │
    │ 1. 파일 선택          │                        │                │
    │    (file input)       │                        │                │
    │                       │                        │                │
    │ 2. POST /documents/upload-session              │                │
    │    { filename, mimeType, size }                │                │
    │ ──────────────────►   │                        │                │
    │                       │                        │                │
    │                  ┌────┴────┐                   │                │
    │                  │ Validate │                  │                │
    │                  │ - size   │                  │                │
    │                  │ - type   │                  │                │
    │                  └────┬────┘                   │                │
    │                       │                        │                │
    │                       │ 3. INSERT document     │                │
    │                       │    (status: uploading) │                │
    │                       │ ──────────────────────►│                │
    │                       │                        │                │
    │                       │ 4. Pre-signed PUT URL  │                │
    │                       │    (expires: 1 hour)   │                │
    │                       │ ───────────────────────────────────────►│
    │                       │                        │                │
    │                       │ 5. URL + signature     │                │
    │                       │ ◄───────────────────────────────────────│
    │                       │                        │                │
    │ 6. Response:          │                        │                │
    │    { documentId, versionId, uploadUrl }        │                │
    │ ◄──────────────────   │                        │                │
    │                       │                        │                │
    │ 7. PUT uploadUrl      │                        │                │
    │    (파일 바이너리)     │                        │                │
    │ ───────────────────────────────────────────────────────────────►│
    │                       │                        │                │
    │                       │                        │   ┌──────────┐ │
    │                       │                        │   │  파일    │ │
    │                       │                        │   │  저장    │ │
    │                       │                        │   └────┬─────┘ │
    │                       │                        │        │       │
    │ 8. 200 OK (MinIO)     │                        │        │       │
    │ ◄───────────────────────────────────────────────────────────────│
    │                       │                        │                │
    │ 9. POST /documents/:documentId/versions/:versionId/complete     │
    │ ──────────────────►   │                        │                │
    │                       │                        │                │
    │                       │ 10. UPDATE status      │                │
    │                       │     (uploaded)         │                │
    │                       │ ──────────────────────►│                │
    │                       │                        │                │
    │                       │ 11. INSERT             │                │
    │                       │     storage_object_files│               │
    │                       │ ──────────────────────►│                │
    │                       │                        │                │
    │                       │ 12. Generate & Upload  │                │
    │                       │     manifest.json      │                │
    │                       │ ───────────────────────────────────────►│
    │                       │                        │   (Direct PUT) │
    │                       │                        │                │
    │                       │ 13. HTTP POST to       │                │
    │                       │     Embedding Server   │                │
    │                       │ ──────────────────────────────────────► │
    │                       │                        │                │
    │                       │ 14. UPDATE status      │                │
    │                       │     (queued)           │                │
    │                       │ ──────────────────────►│                │
    │                       │                        │                │
    │ 15. Response:         │                        │                │
    │     { status: "queued" }                       │                │
    │ ◄──────────────────   │                        │                │
    │                       │                        │                │
```

### 4.2 단계별 상세 설명

#### **Step 1-2: 업로드 세션 생성**

**프론트엔드 요청:**
```javascript
const file = fileInput.files[0];

const response = await fetch('/api/documents/upload-session', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    files: [{
      filename: file.name,       // "report.pdf"
      mimeType: file.type,       // "application/pdf"
      size: file.size            // 1024000 bytes
    }]
  })
});
```

**전송 내용:**
- ✅ 파일 **메타데이터만** 전송 (실제 파일 아님)
- ✅ 파일은 브라우저 메모리에만 존재

**백엔드 검증:**
```typescript
// 1. 파일 크기 검증
if (file.size > 100 * 1024 * 1024) {
  throw new PayloadTooLargeException('파일 크기는 100MB를 초과할 수 없습니다');
}

// 2. MIME 타입 검증
const supportedTypes = ['application/pdf', 'application/vnd...', ...];
if (!supportedTypes.includes(file.mimeType)) {
  throw new UnsupportedMediaTypeException('지원하지 않는 파일 형식입니다');
}
```

---

#### **Step 3: DB 레코드 생성**

```sql
-- doc_documents 테이블
-- minio_url은 파일이 아닌 디렉토리 경로를 저장 (마지막 /로 끝남)
INSERT INTO doc_documents (id, title, minio_url, created_by)
VALUES (uuid, 'report.pdf', 'raw/dept-uuid/2026/01/doc-uuid/', userId);

-- doc_document_content 테이블
INSERT INTO doc_document_content (
  id, document_id, version_no, original_filename,
  uploader_id, file_size, mime_type, status
)
VALUES (
  uuid, documentId, 1, 'report.pdf',
  userId, 1024000, 'application/pdf', 'uploading'
);
```

**초기 상태:** `status = 'uploading'`

---

#### **Step 4-5: Pre-signed URL 생성**

```typescript
// Backend - MinioService
// 경로 구조: raw/{deptId}/{year}/{month}/{documentId}/{filename}
const basePath = `raw/${deptId}/${year}/${month}/${documentId}/`;
const objectKey = `${basePath}${filename}`;
const uploadUrl = await this.minioClient.presignedPutObject(
  'rag',           // bucket
  objectKey,       // raw/dept-uuid/2026/01/doc-uuid/report.pdf
  60 * 60          // 1시간 유효
);
```

**경로 구조 (v3.0):**
```
raw/{deptId}/{year}/{month}/{documentId}/
├── {filename}       ← 원본 파일 (Pre-signed URL로 업로드)
└── manifest.json    ← 메타데이터 파일 (Complete 시 Backend에서 직접 업로드)
```

**생성된 URL 예시:**
```
https://minio.example.com/rag/raw/dept-uuid/2026/01/doc-uuid/report.pdf?
X-Amz-Algorithm=AWS4-HMAC-SHA256&
X-Amz-Credential=AKIAIOSFODNN7EXAMPLE/20260115/us-east-1/s3/aws4_request&
X-Amz-Date=20260115T120000Z&
X-Amz-Expires=3600&
X-Amz-SignedHeaders=host&
X-Amz-Signature=abcdef1234567890...
```

**URL 특징:**
- ✅ 1시간 동안만 유효
- ✅ PUT 메서드만 허용
- ✅ 특정 객체 키에만 업로드 가능
- ✅ 암호화 서명으로 위변조 방지

---

#### **Step 6: 응답 반환**

```json
{
  "data": {
    "documentId": "doc-uuid-123",
    "uploads": [{
      "filename": "report.pdf",
      "versionId": "ver-uuid-456",
      "uploadUrl": "https://minio.../presigned-url...",
      "objectKey": "raw/dept-uuid/2026/01/doc-uuid-123/report.pdf",
      "expiresIn": 3600
    }]
  },
  "message": "업로드 URL이 생성되었습니다"
}
```

---

#### **Step 7-8: MinIO 직접 업로드**

**프론트엔드 코드:**
```javascript
const { uploadUrl } = response.data.uploads[0];

// MinIO에 직접 PUT 요청
const uploadResponse = await fetch(uploadUrl, {
  method: 'PUT',
  body: file,  // 실제 파일 바이너리
  headers: {
    'Content-Type': file.type
  }
});

if (!uploadResponse.ok) {
  throw new Error('파일 업로드 실패');
}
```

**중요:**
- ✅ Backend를 거치지 않음
- ✅ 브라우저 → MinIO 직접 전송
- ✅ 진행률 추적 가능 (XMLHttpRequest 사용 시)

---

#### **Step 9-14: 업로드 완료 처리**

**프론트엔드 요청:**
```javascript
await fetch(`/api/documents/${documentId}/versions/${versionId}/complete`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${accessToken}`
  }
});
```

**백엔드 처리:**
```typescript
// 1. 상태 업데이트: uploading → uploaded
await this.documentVersionRepository.update(versionId, {
  status: DocStatus.UPLOADED
});

// 2. storage_object_files 레코드 생성
await this.storageObjectFileRepository.save({
  objectKey,
  kind: 'raw',
  // ...
});

// 3. manifest.json 생성 및 MinIO 직접 업로드 (v3.0 추가)
const manifest = {
  documentId: document.id,
  filename: version.originalFilename,
  fileType: version.mimeType,
  fileSize: version.fileSize,
  hash: version.sha256,
  uploader: {
    id: user.id,
    name: user.name,
    deptId: user.authDeptId,
    email: user.email,
  },
  uploadedAt: new Date().toISOString(),
  title: document.title,
};
const manifestBuffer = Buffer.from(JSON.stringify(manifest, null, 2));
const manifestKey = `${document.minioUrl}manifest.json`;
await this.minioService.uploadBuffer(manifestKey, manifestBuffer, 'application/json');

// 4. Embedding Request Server에 HTTP 요청
await this.httpService.post('<embedding-server-url>/v1/embeddings', {
  documentId,
  versionId,
  s3Location: `s3://rag/${objectKey}`
}, {
  headers: {
    'Authorization': 'Bearer <token>'
  }
});

// 5. 상태 업데이트: uploaded → queued
await this.documentVersionRepository.update(versionId, {
  status: DocStatus.QUEUED,
  queuedAt: new Date()
});
```

**manifest.json 업로드 방식:**
- ✅ **Backend → MinIO 직접 업로드** (Pre-signed URL 아님)
- ✅ MinIO Client (MINIO_ACCESS_KEY, MINIO_SECRET_KEY) 사용
- ✅ 사용자는 manifest.json을 직접 보내지 않음

---

## 5. 프론트엔드 구현 가이드

### 5.1 완전한 업로드 함수

```javascript
/**
 * MinIO Pre-signed URL 방식으로 파일 업로드
 * @param {File} file - 업로드할 파일
 * @param {string} token - JWT access token
 * @returns {Promise<{documentId, versionId, status}>}
 */
async function uploadDocument(file, token) {
  try {
    // === Step 1: 업로드 세션 생성 ===
    const sessionResponse = await fetch('/api/documents/upload-session', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        files: [{
          filename: file.name,
          mimeType: file.type,
          size: file.size
        }]
      })
    });

    if (!sessionResponse.ok) {
      const error = await sessionResponse.json();
      throw new Error(error.message || '업로드 세션 생성 실패');
    }

    const session = await sessionResponse.json();
    const { documentId, uploads } = session.data;
    const { versionId, uploadUrl, objectKey } = uploads[0];

    console.log('업로드 세션 생성 완료:', { documentId, versionId });

    // === Step 2: MinIO 직접 업로드 ===
    const uploadResponse = await fetch(uploadUrl, {
      method: 'PUT',
      body: file,
      headers: {
        'Content-Type': file.type
      }
    });

    if (!uploadResponse.ok) {
      throw new Error(`MinIO 업로드 실패 (${uploadResponse.status})`);
    }

    console.log('MinIO 업로드 완료:', objectKey);

    // === Step 3: 업로드 완료 알림 ===
    const completeResponse = await fetch(
      `/api/documents/${documentId}/versions/${versionId}/complete`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    if (!completeResponse.ok) {
      const error = await completeResponse.json();
      throw new Error(error.message || '업로드 완료 처리 실패');
    }

    const result = await completeResponse.json();
    console.log('업로드 완료:', result.message);

    return {
      documentId,
      versionId,
      status: result.data.status  // "queued"
    };

  } catch (error) {
    console.error('파일 업로드 에러:', error);
    throw error;
  }
}
```

### 5.2 진행률 표시 (고급)

```javascript
/**
 * XMLHttpRequest를 사용한 업로드 (진행률 추적)
 */
function uploadWithProgress(file, uploadUrl, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    // 진행률 이벤트
    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const percentComplete = (e.loaded / e.total) * 100;
        onProgress(percentComplete);
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        resolve();
      } else {
        reject(new Error(`Upload failed: ${xhr.status}`));
      }
    });

    xhr.addEventListener('error', () => {
      reject(new Error('Network error'));
    });

    xhr.open('PUT', uploadUrl);
    xhr.setRequestHeader('Content-Type', file.type);
    xhr.send(file);
  });
}

// 사용 예시
await uploadWithProgress(file, uploadUrl, (progress) => {
  console.log(`업로드 진행: ${progress.toFixed(2)}%`);
  progressBar.style.width = `${progress}%`;
});
```

### 5.3 React 컴포넌트 예시

```jsx
import { useState } from 'react';

function DocumentUpload() {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState(null);

  const handleFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    setProgress(0);

    try {
      const token = localStorage.getItem('access_token');
      const result = await uploadDocument(file, token);

      alert(`업로드 완료! 문서 ID: ${result.documentId}`);

      // 문서 목록 페이지로 이동
      window.location.href = '/documents';

    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div>
      <h2>문서 업로드</h2>

      <input
        type="file"
        onChange={handleFileSelect}
        disabled={uploading}
        accept=".pdf,.docx,.xlsx,.pptx,.txt,.md"
      />

      {uploading && (
        <div>
          <p>업로드 중... {progress.toFixed(0)}%</p>
          <progress value={progress} max="100" />
        </div>
      )}

      {error && (
        <div style={{ color: 'red' }}>
          에러: {error}
        </div>
      )}
    </div>
  );
}
```

---

## 6. API 명세

### 6.1 POST /api/documents/upload-session

**요청:**
```http
POST /api/documents/upload-session
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "files": [{
    "filename": "document.pdf",
    "mimeType": "application/pdf",
    "size": 1024000
  }]
}
```

**응답 (201 Created):**
```json
{
  "data": {
    "documentId": "doc-uuid",
    "uploads": [{
      "filename": "document.pdf",
      "versionId": "ver-uuid",
      "uploadUrl": "https://minio.../presigned-url",
      "objectKey": "raw/dept-uuid/2026/01/doc-uuid/document.pdf",
      "expiresIn": 3600
    }]
  },
  "message": "업로드 URL이 생성되었습니다"
}
```

**에러 응답:**
```json
// 413 Payload Too Large
{
  "statusCode": 413,
  "message": "파일 크기는 100MB를 초과할 수 없습니다"
}

// 415 Unsupported Media Type
{
  "statusCode": 415,
  "message": "지원하지 않는 파일 형식입니다"
}
```

---

### 6.2 POST /api/documents/:documentId/versions/:versionId/complete

**요청:**
```http
POST /api/documents/{documentId}/versions/{versionId}/complete
Authorization: Bearer {access_token}
```

**응답 (201 Created):**
```json
{
  "data": {
    "documentId": "uuid",
    "versionId": "uuid",
    "status": "queued"
  },
  "message": "임베딩 요청이 접수되었습니다"
}
```

**에러 응답:**
```json
// 404 Not Found
{
  "statusCode": 404,
  "message": "문서 또는 버전을 찾을 수 없습니다"
}

// 403 Forbidden
{
  "statusCode": 403,
  "message": "해당 문서에 대한 권한이 없습니다"
}
```

---

### 6.3 DELETE /api/documents/:documentId (2026-01-08 추가)

**요청:**
```http
DELETE /api/documents/{documentId}
Authorization: Bearer {access_token}
```

**응답 (200 OK):**
```json
{
  "message": "문서가 삭제되었습니다"
}
```

**에러 응답:**
```json
// 404 Not Found
{
  "statusCode": 404,
  "message": "Document not found"
}

// 403 Forbidden
{
  "statusCode": 403,
  "message": "You do not have permission to delete this document"
}
```

**삭제 범위:**
- MinIO: `raw/{deptId}/{year}/{month}/{documentId}/` 하위 모든 파일 및 폴더 마커 (manifest.json 포함)
- PostgreSQL: `doc_documents` 레코드 (CASCADE로 연관 테이블 자동 삭제)

---

## 7. 다중 파일 업로드

### 7.1 다중 파일 업로드 구조 (2026-01-08 업데이트)

다중 파일 업로드 시 **각 파일마다 별도의 `versionId`가 생성**됩니다.

```
┌────────────────────────────────────────────────────────────────┐
│                    다중 파일 업로드 구조                          │
└────────────────────────────────────────────────────────────────┘

  doc_documents (1개)
       │
       ├── doc_document_content (파일 A) → versionId: "aaa-111"
       │        └── storage_object_files
       │
       ├── doc_document_content (파일 B) → versionId: "bbb-222"
       │        └── storage_object_files
       │
       └── doc_document_content (파일 C) → versionId: "ccc-333"
                └── storage_object_files
```

**요청 예시:**
```json
{
  "files": [
    { "filename": "doc1.pdf", "mimeType": "application/pdf", "size": 1024000 },
    { "filename": "doc2.docx", "mimeType": "application/vnd...", "size": 2048000 },
    { "filename": "doc3.txt", "mimeType": "text/plain", "size": 512000 }
  ]
}
```

**응답 예시:**
```json
{
  "data": {
    "documentId": "doc-uuid-123",
    "uploads": [
      {
        "filename": "doc1.pdf",
        "versionId": "ver-aaa-111",
        "uploadUrl": "https://minio.../presigned-url-1",
        "objectKey": "raw/dept-uuid/2026/01/doc-uuid-123/doc1.pdf",
        "expiresIn": 3600
      },
      {
        "filename": "doc2.docx",
        "versionId": "ver-bbb-222",
        "uploadUrl": "https://minio.../presigned-url-2",
        "objectKey": "raw/dept-uuid/2026/01/doc-uuid-123/doc2.docx",
        "expiresIn": 3600
      },
      {
        "filename": "doc3.txt",
        "versionId": "ver-ccc-333",
        "uploadUrl": "https://minio.../presigned-url-3",
        "objectKey": "raw/dept-uuid/2026/01/doc-uuid-123/doc3.txt",
        "expiresIn": 3600
      }
    ]
  }
}
```

**MinIO 디렉토리 구조 (v3.0):**
```
raw/
└── {deptId}/
    └── {year}/
        └── {month}/
            └── {documentId}/
                ├── doc1.pdf           ← 원본 파일
                ├── doc2.docx          ← 원본 파일
                ├── doc3.txt           ← 원본 파일
                └── manifest.json      ← 메타데이터 (Complete 시 생성)
```

### 7.2 버전 번호 (versionNo)

- 모든 파일의 `versionNo`는 **항상 1**입니다
- 버전 번호는 업로드 순서와 무관하게 1로 고정
- 실제 파일 식별은 `versionId` (UUID)로 수행

```sql
-- 각 파일마다 별도의 version 레코드 생성 (versionNo = 1)
INSERT INTO doc_document_content (document_id, version_no, ...) VALUES ('doc-123', 1, ...);
INSERT INTO doc_document_content (document_id, version_no, ...) VALUES ('doc-123', 1, ...);
INSERT INTO doc_document_content (document_id, version_no, ...) VALUES ('doc-123', 1, ...);
```

---

## 8. 문서 삭제 플로우 (2026-01-08 추가)

### 8.1 삭제 시퀀스 다이어그램

```
┌────────────────────────────────────────────────────────────────┐
│                    문서 삭제 플로우 (Hard Delete)                 │
└────────────────────────────────────────────────────────────────┘

[Frontend]              [Backend]              [PostgreSQL]        [MinIO]
    │                       │                        │                │
    │ DELETE /documents/:id │                        │                │
    │ ──────────────────►   │                        │                │
    │                       │                        │                │
    │                  ┌────┴────┐                   │                │
    │                  │ 권한 검증 │                  │                │
    │                  │ - Owner │                   │                │
    │                  │ - Admin │                   │                │
    │                  └────┬────┘                   │                │
    │                       │                        │                │
    │                       │ 1. deleteObjectsByPrefix                │
    │                       │    (raw/{deptId}/{year}/{month}/{docId}/)│
    │                       │ ───────────────────────────────────────►│
    │                       │                        │                │
    │                       │                        │   ┌──────────┐ │
    │                       │                        │   │ 파일 삭제 │ │
    │                       │                        │   │ + 폴더   │ │
    │                       │                        │   └────┬─────┘ │
    │                       │                        │        │       │
    │                       │ 2. 삭제 완료            │        │       │
    │                       │ ◄───────────────────────────────────────│
    │                       │                        │                │
    │                       │ 3. DELETE doc_documents │               │
    │                       │    (CASCADE 처리)      │                │
    │                       │ ──────────────────────►│                │
    │                       │                        │                │
    │                       │                   ┌────┴────────────┐   │
    │                       │                   │ CASCADE 삭제:    │   │
    │                       │                   │ - versions      │   │
    │                       │                   │ - permissions   │   │
    │                       │                   │ - favorites     │   │
    │                       │                   │ - storage_files │   │
    │                       │                   │ - rag_* 테이블들 │   │
    │                       │                   │ - alarms        │   │
    │                       │                   └────┬────────────┘   │
    │                       │                        │                │
    │ 200 OK                │                        │                │
    │ ◄──────────────────   │                        │                │
```

### 8.2 CASCADE 삭제 관계

```
doc_documents (삭제 대상)
    │
    ├── doc_document_content (CASCADE)
    │       ├── storage_object_files (CASCADE)
    │       ├── rag_embedding_jobs (CASCADE)
    │       │       └── rag_status_events (CASCADE)
    │       ├── rag_chunks (CASCADE)
    │       │       ├── rag_embeddings_index (CASCADE)
    │       │       └── rag_upsert_history (CASCADE)
    │       └── rag_processing_stats (CASCADE)
    │
    ├── doc_document_permission (CASCADE)
    ├── doc_document_favorites (CASCADE)
    ├── auth_users_alarm (CASCADE)
    └── chat_document_reference (CASCADE)
```

### 8.3 MinIO 폴더 삭제

MinIO는 실제로 "폴더"가 없고 `/`로 구분된 가상 경로를 사용합니다.
`deleteObjectsByPrefix()` 메서드로 prefix 하위의 모든 객체와 폴더 마커를 삭제합니다.

```typescript
// MinIO에서 prefix 하위 모든 파일 삭제
async deleteObjectsByPrefix(prefix: string): Promise<number> {
  // 1. prefix 하위 모든 객체 목록 조회
  const objects = await this.listObjects(prefix);

  // 2. 폴더 마커 추출 (prefix 하위의 가상 폴더들)
  const folderMarkers = extractFolderMarkers(objects, prefix);

  // 3. 모든 객체 + 폴더 마커 일괄 삭제
  await this.client.removeObjects(this.bucket, [...objectNames, ...folderMarkers, prefix]);

  return deletedCount;
}
```

### 8.4 삭제 권한

- **문서 소유자** (`created_by = userId`): 삭제 가능
- **Admin 권한** (`authority_type = 'admin'`): 삭제 가능
- **일반 사용자**: 403 Forbidden

---

## 9. 문서 다운로드 플로우 (2026-01-14 추가)

### 9.1 다운로드 시퀀스 다이어그램

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         Pre-signed URL 파일 다운로드 플로우                                │
└────────────────────────────────────────────────────────────────────────────────────────┘

[Frontend]              [Backend]               [PostgreSQL]              [MinIO + Nginx]
    │                       │                        │                           │
    │ GET /api/documents/:documentId/versions/:versionId/download                │
    │ ──────────────────►   │                        │                           │
    │                       │                        │                           │
    │                  ┌────┴────┐                   │                           │
    │                  │ JWT 검증 │                   │                           │
    │                  │ 소유권   │                   │                           │
    │                  │ 검증    │                   │                           │
    │                  └────┬────┘                   │                           │
    │                       │                        │                           │
    │                       │ 1. SELECT document     │                           │
    │                       │    & version info      │                           │
    │                       │ ──────────────────────►│                           │
    │                       │                        │                           │
    │                       │ 2. Pre-signed GET URL  │                           │
    │                       │    (expires: 1 hour)   │                           │
    │                       │ ──────────────────────────────────────────────────►│
    │                       │                        │                           │
    │                       │ 3. URL + signature     │                           │
    │                       │ ◄──────────────────────────────────────────────────│
    │                       │                        │                           │
    │                       │ 4. presignedClient가   │                           │
    │                       │    public endpoint로   │                           │
    │                       │    서명된 URL 반환      │                           │
    │                       │                        │                           │
    │ 5. Response:          │                        │                           │
    │    { downloadUrl, expiresIn }                  │                           │
    │ ◄──────────────────   │                        │                           │
    │                       │                        │                           │
    │ 6. GET downloadUrl     │                        │                           │
    │    (Nginx HTTPS)       │                        │                           │
    │ ──────────────────────────────────────────────────────────────────────────►│
    │                       │                        │                      ┌────┴────┐
    │                       │                        │                      │  Nginx  │
    │                       │                        │                      │    ↓    │
    │                       │                        │                      │  MinIO  │
    │                       │                        │                      └────┬────┘
    │                       │                        │                           │
    │ 7. 파일 바이너리       │                        │                           │
    │ ◄──────────────────────────────────────────────────────────────────────────│
    │                       │                        │                           │
```

**다이어그램 설명:**
- **Step 1**: PostgreSQL에서 문서 정보 (objectKey 포함) 조회
- **Step 6**: Frontend가 **직접 MinIO (Nginx 프록시 경유)** 에 파일 요청 (Backend 거치지 않음)

### 9.2 Nginx HTTPS 프록시 및 Presigned URL 서명 (2026-02-26 수정)

프론트엔드가 HTTPS로 서빙될 때, HTTP MinIO로 직접 요청하면 브라우저가 Mixed Content로 차단합니다.
Nginx 리버스 프록시가 HTTPS → HTTP 변환을 수행합니다.

> ⚠️ **중요:** Pre-signed URL은 서명에 Host가 포함됩니다. 서명 생성 시 Host와 실제 요청의 Host가 정확히 일치해야 합니다.

**Presigned URL 서명 방식:**

백엔드에서 `presignedClient`(public endpoint 기준)로 서명을 생성하여, 프론트엔드가 접속하는 호스트와 서명이 일치하도록 합니다.

```
서명 생성 (presignedClient): Host = storage.example.com:9000
프론트 PUT 요청:            Host = storage.example.com:9000
Nginx → MinIO 전달:         Host = storage.example.com:9000 ($http_host)
→ 서명 일치 ✅
```

**Nginx 설정 (필수):**
```nginx
server {
    listen 9000 ssl;
    location / {
        proxy_pass http://minio_api;
        proxy_set_header Host $http_host;  # $host가 아닌 $http_host (포트 포함 필수!)
    }
}
```

### 9.3 다운로드 권한 검증

- **문서 소유자** (`created_by = userId`): 다운로드 가능
- **Admin 권한** (`authority_type = 'admin'`): 다운로드 가능
- **일반 사용자**: 403 Forbidden

### 9.4 API 명세: GET /api/documents/:documentId/versions/:versionId/download

**요청:**
```http
GET /api/documents/{documentId}/versions/{versionId}/download
Authorization: Bearer {access_token}
```

**응답 (200 OK):**
```json
{
  "success": true,
  "code": "BKN04600",
  "message": "다운로드 URL이 생성되었습니다",
  "data": {
    "downloadUrl": "https://<nginx-proxy>/minio/rag/raw/dept-uuid/2026/01/doc-uuid/document.pdf?X-Amz-...",
    "expiresIn": 3600
  }
}
```

**에러 응답:**
```json
// 404 Not Found
{
  "success": false,
  "code": "BKN04220",
  "message": "문서를 찾을 수 없습니다"
}

// 403 Forbidden
{
  "success": false,
  "code": "BKN04620",
  "message": "해당 문서에 대한 다운로드 권한이 없습니다"
}
```

### 9.5 프론트엔드 구현 예시

```javascript
/**
 * 문서 다운로드
 * @param {string} documentId - 문서 ID
 * @param {string} versionId - 버전 ID
 * @param {string} token - JWT access token
 */
async function downloadDocument(documentId, versionId, token) {
  try {
    // 1. 다운로드 URL 요청
    const response = await fetch(
      `/api/documents/${documentId}/versions/${versionId}/download`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || '다운로드 URL 생성 실패');
    }

    const result = await response.json();
    const { downloadUrl } = result.data;

    // 2. 파일 다운로드 (브라우저에서 직접 다운로드)
    window.open(downloadUrl, '_blank');

    // 또는 fetch로 다운로드 후 저장
    // const fileResponse = await fetch(downloadUrl);
    // const blob = await fileResponse.blob();
    // saveAs(blob, 'document.pdf');

  } catch (error) {
    console.error('다운로드 에러:', error);
    throw error;
  }
}
```

---

## 10. 데이터베이스 스키마 변경사항 (2026-01-08)

### 10.1 sha256 컬럼 nullable 변경

`doc_document_content.sha256` 컬럼이 **nullable**로 변경되었습니다.

**이유:**
- 파일 업로드 시점에는 sha256 해시를 계산하지 않음
- Embedding Worker에서 파일 처리 후 sha256 값을 채움
- 업로드 직후에는 `null` 상태

```sql
-- 변경 전
sha256 CHAR(64) NOT NULL

-- 변경 후
sha256 CHAR(64)  -- nullable
```

### 10.2 relevance 컬럼 추가

`chat_document_reference` 테이블에 `relevance` 컬럼이 추가되었습니다.

```sql
ALTER TABLE chat_document_reference ADD COLUMN relevance FLOAT;
COMMENT ON COLUMN chat_document_reference.relevance IS
  'RAG 검색 시 Qdrant에서 반환된 유사도 점수 (0.0~1.0, 코사인 유사도)';
```

### 10.3 유사도(Relevance) 계산 원리

```
┌────────────────────────────────────────────────────────────────┐
│                    RAG 유사도 검색 과정                          │
└────────────────────────────────────────────────────────────────┘

1. 문서 임베딩 (인덱싱 시점)
   ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
   │   원본 문서   │  ───► │    청킹     │  ───► │  벡터 변환   │
   │   (PDF 등)   │       │  (Chunking)  │       │ (Embedding)  │
   └──────────────┘       └──────────────┘       └──────┬───────┘
                                                        │
                                                        ▼
                                                 ┌──────────────┐
                                                 │   Qdrant DB  │
                                                 │  (벡터 저장)  │
                                                 └──────────────┘

2. 질의 처리 (검색 시점)
   ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
   │  사용자 질문  │  ───► │  벡터 변환   │  ───► │ Qdrant 검색  │
   │              │       │ (Embedding)  │       │ (유사도 계산) │
   └──────────────┘       └──────────────┘       └──────┬───────┘
                                                        │
                                                        ▼
                                                 ┌──────────────┐
                                                 │  relevance   │
                                                 │  0.0 ~ 1.0   │
                                                 └──────────────┘
```

**코사인 유사도 공식:**
```
cosine_similarity = (A · B) / (||A|| × ||B||)

A = 질문 벡터
B = 문서 청크 벡터

결과값: 0.0 (무관) ~ 1.0 (동일)
일반적으로 0.7+ 는 높은 관련성
```

---

## 11. 상태 전이 다이어그램

```
┌────────────────────────────────────────────────────────────────┐
│                  Document Version 상태 전이                      │
└────────────────────────────────────────────────────────────────┘

    uploading ──────► uploaded ──────► queued
        │                                 │
        │                                 ▼
        │                             parsing
        │                                 │
        │                                 ▼
        │                             chunking
        │                                 │
        │                                 ▼
        │                             embedding
        │                                 │
        │                                 ▼
        │                             upserting
        │                                 │
        │                                 ▼
        └────────────────────────────► completed
                                          │
                                          ▼
                                        failed
```

**상태 설명:**
- `uploading`: 업로드 세션 생성됨, MinIO 업로드 대기 중
- `uploaded`: MinIO 업로드 완료
- `queued`: Embedding Request Server에 요청 전송됨
- `parsing`: Worker가 파일 파싱 중
- `chunking`: 문서 청킹 중
- `embedding`: 임베딩 생성 중
- `upserting`: Qdrant에 벡터 삽입 중
- `completed`: 모든 처리 완료
- `failed`: 처리 실패 (status_reason에 에러 메시지)

---

## 12. 보안 고려사항

### 12.1 Pre-signed URL 보안

| 보안 기능 | 설명 |
|----------|------|
| 시간 제한 | 1시간 후 자동 만료 |
| 메서드 제한 | PUT 메서드만 허용 |
| 객체 키 고정 | 특정 경로에만 업로드 가능 |
| 서명 검증 | MinIO가 서명 유효성 확인 |

### 12.2 Backend 검증

```typescript
// 1. JWT 인증 (모든 엔드포인트)
@UseGuards(JwtAuthGuard)

// 2. 파일 크기 검증
if (fileSize > MAX_FILE_SIZE) throw new PayloadTooLargeException();

// 3. MIME 타입 검증
if (!SUPPORTED_MIME_TYPES.includes(mimeType))
  throw new UnsupportedMediaTypeException();

// 4. 소유권 검증
if (document.createdBy !== userId)
  throw new ForbiddenException();
```

### 12.3 MinIO 권한 최소화

- ✅ `raw/*` 경로에만 업로드/다운로드/삭제 가능
- ✅ `rag` 버킷만 접근 가능
- ✅ 다운로드는 소유자/Admin만 가능 (소유권 검증)

---

## 13. 장단점 분석

### 13.1 Pre-signed URL 방식의 장점

| 항목 | 설명 |
|------|------|
| **성능** | 파일이 클라이언트 → MinIO 직접 전송 (1회) |
| **확장성** | 백엔드 부하 없이 동시 업로드 가능 |
| **비용** | 백엔드 대역폭/메모리 절약 |
| **보안** | 임시 URL, 시간 제한 |

### 13.2 단점 및 해결책

| 단점 | 해결책 |
|------|--------|
| 3단계 플로우 (복잡함) | 프론트엔드 헬퍼 함수 제공 |
| 파일 존재 검증 불가 | Worker에서 검증 처리 |
| 프론트엔드 2번 API 호출 | 헬퍼 함수로 추상화 |

---

## 14. 운영 가이드

### 14.1 에러 처리

| 시나리오 | 프론트엔드 처리 |
|----------|----------------|
| 세션 생성 실패 (413/415) | 즉시 사용자에게 에러 표시 |
| MinIO 업로드 실패 | 재시도 or 에러 표시 |
| 완료 처리 실패 | DB에 `uploading` 상태 남음 → 관리자 수동 정리 |

### 14.2 모니터링 포인트

```typescript
// 백엔드 로깅
logger.info('Upload session created', { documentId, versionId, fileSize });
logger.info('Upload completed', { documentId, status: 'queued' });
logger.error('Upload failed', { documentId, error });
```

### 14.3 운영 FAQ

**Q: Pre-signed URL이 만료되면?**
A: 새로운 업로드 세션 생성 필요 (Step 1부터 다시 시작)

**Q: MinIO 업로드는 성공했는데 complete 호출 안 하면?**
A: DB에 `status: 'uploading'` 상태로 남음. 파일은 MinIO에 존재하지만 임베딩 안 됨.

**Q: 다중 서버 환경에서는?**
A: Pre-signed URL 방식은 stateless하므로 별도 조치 불필요.

---

## 15. 관련 파일

| 파일 | 역할 |
|------|------|
| [document.controller.ts](../../src/document/document.controller.ts) | API 엔드포인트 (업로드, 삭제) |
| [document.service.ts](../../src/document/document.service.ts) | 비즈니스 로직 (다중 파일 업로드, CASCADE 삭제) |
| [minio.service.ts](../../src/external/minio/minio.service.ts) | Pre-signed URL 생성, `deleteObjectsByPrefix()` |
| [create-upload-session.dto.ts](../../src/document/dto/create-upload-session.dto.ts) | DTO 정의 |
| [doc-document-version.entity.ts](../../src/document/entities/doc-document-version.entity.ts) | 버전 엔티티 (sha256 nullable) |
| [storage-object-file.entity.ts](../../src/storage/entities/storage-object-file.entity.ts) | MinIO 파일 메타 엔티티 (CASCADE) |
| [chat-document-reference.entity.ts](../../src/chat/entities/chat-document-reference.entity.ts) | 채팅 참조 문서 엔티티 (relevance 컬럼) |
| [init-db.sql](../../scripts/init-db.sql) | DDL 스크립트 |


---

## 16. 결론

### 16.1 도입 효과

1. **성능 향상**: 파일이 백엔드를 거치지 않음
2. **확장성 확보**: MinIO가 업로드 트래픽 처리
3. **보안 강화**: 임시 URL, 권한 최소화
4. **비용 절감**: 백엔드 리소스 절약

### 16.2 권장사항

- ✅ 모든 파일 업로드: Pre-signed URL 방식 사용
- ✅ 프로덕션: Pre-signed URL 방식 권장

---

## 17. 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|----------|
| 2025-12-21 | 1.0 | 초기 작성 - Pre-signed URL 업로드 플로우 |
| 2026-01-08 | 2.0 | 다중 파일 업로드 구조 변경 (파일별 versionId) |
| 2026-01-08 | 2.0 | 문서 삭제 Hard Delete 구현 (`s3:DeleteObject` 권한 추가) |
| 2026-01-08 | 2.0 | MinIO 폴더 삭제 기능 추가 (`deleteObjectsByPrefix`) |
| 2026-01-08 | 2.0 | CASCADE 삭제 관계 정립 |
| 2026-01-08 | 2.0 | `sha256` 컬럼 nullable 변경 |
| 2026-01-08 | 2.0 | `chat_document_reference.relevance` 컬럼 추가 |
| 2026-01-08 | 2.0 | versionNo 항상 1로 고정 |
| 2026-01-08 | 2.0 | 지원 파일 형식 명세 추가 (섹션 3.3) |
| 2026-01-14 | 2.1 | 문서 다운로드 플로우 추가 (`s3:GetObject` 권한 추가) |
| 2026-01-14 | 2.1 | Pre-signed GET URL 생성 기능 추가 |
| 2026-01-14 | 2.1 | Nginx HTTPS 프록시 URL 변환 설명 추가 |
| 2026-01-15 | 2.2 | 모든 API 엔드포인트에 `/api` prefix 적용 |
| 2026-01-15 | 3.0 | MinIO 경로 구조 변경: `raw/{deptId}/{year}/{month}/{documentId}/` |
| 2026-01-15 | 3.0 | manifest.json 자동 생성 기능 추가 (업로드 완료 시 백엔드에서 생성) |
| 2026-02-26 | 3.1 | Presigned URL 서명 방식 변경: `transformToPublicUrl` 제거 → `presignedClient` 도입, Nginx `$host` → `$http_host` 수정 |

---

**문서 끝**
