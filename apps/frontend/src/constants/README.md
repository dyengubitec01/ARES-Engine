# 프론트엔드 커스텀 코드 체계 (FRN)

## 개요

프론트엔드에서 발생하는 모든 에러와 상태를 체계적으로 관리하기 위한 커스텀 코드 시스템입니다.

## 코드 구조

```
FRN + AABBCD (총 6자리 숫자)
```

- **AA (대분류)**: 기능 영역
  - `01`: 인증 (Auth)
  - `02`: 문서 (Document)
  - `03`: 채팅 (Chat)
  - `04`: 공통/네트워크 (Common)

- **BB (중분류)**: 처리 단계
  - `01`: 유효성 검사 (Validation)
  - `02`: API/상태 전환 (API/State)
  - `03`: 로컬 로직 (Local Logic)

- **CD (소분류)**: 상세 분류
  - `00`: 정상
  - `20~79`: 예외
  - `80~99`: 기타

## 사용 방법

### 1. 에러 발생 시

```typescript
import { createCustomError } from '../lib/customError';
import { DOCUMENT_CODES } from '../constants/customCodes';

// 에러 생성
throw createCustomError(
  DOCUMENT_CODES.DOC_INVALID_FILE_TYPE,
  '사용자 정의 메시지 (선택)',
  { detail: 'some detail' }, // 선택
  originalError // 원본 에러 (선택)
);
```

### 2. 사용자에게 에러 표시

```typescript
import { formatErrorMessage } from '../lib/customError';

// 코드가 포함된 에러 메시지 반환
const message = formatErrorMessage(error);
// 예: "지원하지 않는 파일 형식입니다. (코드: FRN020120)"

alert(message);
```

### 3. 백엔드 에러 코드 매핑

```typescript
import { mapBackendCodeToFrontend } from '../constants/customCodes';

const backendCode = 'BKN040120';
const frontendCode = mapBackendCodeToFrontend(backendCode);
// 반환: 'FRN020121' (FILE_SIZE_EXCEEDED)
```

## 주요 코드 목록

### 인증 관련 (FRN01XXXX)

| 코드 | 이름 | 설명 |
|------|------|------|
| FRN010120 | AUTH_USER_NOT_FOUND | 사용자 정보를 불러올 수 없습니다 |
| FRN010121 | AUTH_INVALID_OAUTH_PARAMS | 인증 정보가 올바르지 않습니다 |
| FRN010220 | AUTH_FAILED | 인증에 실패했습니다 |
| FRN010221 | AUTH_ACCESS_DENIED | 접근 권한이 없습니다 |
| FRN010222 | AUTH_OAUTH_CALLBACK_FAILED | 로그인 처리 중 오류 발생 |
| FRN010223 | AUTH_TOKEN_REFRESH_FAILED | 토큰 갱신 실패 |

### 문서 관련 (FRN02XXXX)

| 코드 | 이름 | 설명 |
|------|------|------|
| FRN020120 | DOC_INVALID_FILE_TYPE | 지원하지 않는 파일 형식 |
| FRN020121 | DOC_FILE_SIZE_EXCEEDED | 파일 크기 초과 |
| FRN020122 | DOC_INVALID_FILE_EXTENSION | 지원하지 않는 확장자 |
| FRN020220 | DOC_UPLOAD_SESSION_FAILED | 업로드 세션 생성 실패 |
| FRN020221 | DOC_DUPLICATE_FILE | 중복 파일 존재 |
| FRN020222 | DOC_MINIO_UPLOAD_FAILED | MinIO 업로드 실패 |
| FRN020223 | DOC_UPLOAD_COMPLETE_FAILED | 업로드 완료 보고 실패 |
| FRN020225 | DOC_EMBEDDING_REQUEST_FAILED | 임베딩 요청 실패 |
| FRN020226 | DOC_FAVORITE_TOGGLE_FAILED | 문서 즐겨찾기 처리 실패 |

### 채팅 관련 (FRN03XXXX)

| 코드 | 이름 | 설명 |
|------|------|------|
| FRN030120 | CHAT_EMPTY_MESSAGE | 메시지를 입력해주세요 |
| FRN030121 | CHAT_NO_ROOM_SELECTED | 채팅방을 먼저 생성해주세요 |
| FRN030122 | CHAT_INVALID_ROOM_UUID | 유효하지 않은 채팅방 ID |
| FRN030220 | CHAT_ROOM_CREATE_FAILED | 채팅방 생성 실패 |
| FRN030221 | CHAT_ROOM_NOT_FOUND | 존재하지 않는 채팅방 |
| FRN030222 | CHAT_MESSAGE_SEND_FAILED | 메시지 전송 실패 |
| FRN030223 | CHAT_SSE_STREAM_ERROR | SSE 스트리밍 오류 |
| FRN030320 | CHAT_FAVORITE_TOGGLE_FAILED | 채팅방 즐겨찾기 변경 실패 |

### 공통/네트워크 (FRN04XXXX)

| 코드 | 이름 | 설명 |
|------|------|------|
| FRN040220 | COMMON_NETWORK_ERROR | 서버 연결 불가 |
| FRN040221 | COMMON_TIMEOUT_ERROR | 응답 시간 초과 |
| FRN040222 | COMMON_HTTP_ERROR | HTTP 오류 |
| FRN040223 | COMMON_RESPONSE_BODY_NULL | 응답 본문 없음 |

## 백엔드 코드 매핑

프론트엔드는 백엔드 에러 코드를 받아서 자체 FRN 코드로 변환합니다:

| 백엔드 코드 | 프론트엔드 코드 | 설명 |
|-------------|-----------------|------|
| BKN040120 | FRN020121 (DOC_FILE_SIZE_EXCEEDED) | 파일 크기 초과 |
| BKN040121 | FRN020120 (DOC_INVALID_FILE_TYPE) | 지원하지 않는 파일 형식 |
| BKN040123 | FRN020221 (DOC_DUPLICATE_FILE) | 중복 파일 존재 |
| BKN000120 | FRN020123 (DOC_FILE_VALIDATION_FAILED) | 파일 유효성 검증 실패 |

## 에러 객체 구조

```typescript
interface CustomError extends Error {
  code: FRNCodeValue;          // FRN 코드
  message: string;              // 사용자 친화적 메시지
  detail?: any;                 // 추가 상세 정보
  originalError?: any;          // 원본 에러 (디버깅용)
}
```

## 파일 구조

```
src/
├── constants/
│   └── customCodes.ts         # 모든 FRN 코드 정의
├── lib/
│   └── customError.ts         # 에러 생성 및 처리 유틸리티
└── [각 기능 폴더]
    └── *.ts/*.tsx             # FRN 코드 사용
```

## 주의사항

1. **기존 로직 유지**: 모든 비즈니스 로직은 변경되지 않았습니다.
2. **에러 속성 보존**: CustomError는 `message` 속성을 포함하므로 기존 코드와 호환됩니다.
3. **원본 에러 보존**: `originalError` 필드에 원본 에러가 저장되어 디버깅이 가능합니다.
4. **백엔드 독립성**: 백엔드 에러 코드는 별도로 유지되며, 필요시 매핑됩니다.

## 예제

### 파일 업로드 에러 처리

```typescript
try {
  await uploadFile(file);
} catch (error: any) {
  if (isCustomError(error)) {
    console.log('FRN 코드:', error.code);
    console.log('메시지:', error.message);
    alert(formatErrorMessage(error)); // "파일 크기가 제한을 초과했습니다. (코드: FRN020121)"
  }
}
```

### 채팅 메시지 전송 유효성 검사

```typescript
if (!activeRoomId) {
  alert(formatErrorMessage(createCustomError(CHAT_CODES.CHAT_NO_ROOM_SELECTED)));
  return;
}
```

### 백엔드 에러 변환

```typescript
const backendCode = error.response?.data?.code;
const frontendCode = backendCode ? mapBackendCodeToFrontend(backendCode) : null;

throw createCustomError(
  frontendCode || DOCUMENT_CODES.DOC_UPLOAD_SESSION_FAILED,
  error.response?.data?.message,
  undefined,
  error
);
```
