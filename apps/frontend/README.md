# Frontend Server

**사내 지식 베이스(RAG)를 활용한 LLM 챗봇 및 관리자 기능을 제공하는 웹 클라이언트**
---

## 프로젝트 개요
### 역할
- 사내 문서 및 지식 베이스를 기반으로 한 대화형 AI 챗봇 인터페이스 제공
- 실시간 스트리밍 채팅 응답 (SSE - Server-Sent Events)
- 문서 업로드 및 관리 기능 (MinIO Presigned URL 기반)
- 관리자 대시보드 (사용자 관리, 권한 관리, 문서 저장소 관리)
- 서비스 점검 모드 및 업데이트 공지 시스템

### 의존 관계 및 통신

```
┌─────────────────┐
│   Frontend      │
│  (React + Vite) │
└────────┬────────┘
         │
         │ HTTPS
         │ (Proxy: /api → Backend)
         ↓
┌─────────────────┐
│ Gateway (Nginx) │
└────────┬────────┘
         │
         │ REST API + SSE
         ↓
┌─────────────────┐
│     Backend     │
│    (Nest.js)    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│   Auth Service  │
│ (JWT + OAuth2.0)│
│ (Azure AD 연동)  │
└─────────────────┘
```

#### 통신 방식
- **Gateway (Nginx)**: 모든 API 요청의 진입점 (`/api` 프록시)
- **Backend (Nest.js)**: REST API 통신 및 채팅 스트리밍 (SSE)
- **Auth**: JWT 기반 인증 (Azure AD 연동 - OAuth 2.0)
- **Refresh Token**: HttpOnly 쿠키를 통한 자동 갱신 메커니즘


## 주요 기능

### 1. 사용자 기능
- **채팅**
  - 실시간 스트리밍 응답 (SSE)
  - 채팅방 생성/삭제
  - 채팅 히스토리 관리
  - 채팅방 즐겨찾기
  - 채팅방 제목 변경/삭제
  - 메시지 피드백 (좋아요/싫어요)
  - AI 사고 과정 시각화
  - 참조 문서 추적

- **문서 관리**
  - 다중 파일 업로드 (MinIO Presigned URL 기반)
  - 업로드 진행률 표시
  - SHA-256 파일 해시 검증
  - 문서 상태 추적 (uploading → uploaded → parsing → embedding → completed)
  - RAG 임베딩 토글 (지식 베이스 참조 on/off)
  - 문서 다운로드
  - 내 문서 / 부서 문서 / 즐겨찾기 3가지 뷰

- **오류 리포트**
  - 사용자 오류 제보 기능
  - FRN 코드 기반 에러 추적 시스템

- **만족도 조사**
  - 서비스 만족도 설문 기능

### 2. 관리자 기능
- **사용자 관리**
  - 사용자 목록 조회 (페이지네이션)
  - 사용자별 권한 관리 (admin, user)

- **권한 관리**
  - 역할 기반 접근 제어 (RBAC)
  - 부서별 권한 관리
  - Admin 전용 페이지 보호

- **문서 저장소 관리**
  - 전체 문서 목록 조회
  - 문서 삭제 및 상태 관리 (system 권한 필요)
  - 문서 메타데이터 조회
  - 정렬 기능


## 기술 스택

### 코어 프레임워크
- **React** `18.3.1` - UI 라이브러리
- **TypeScript** `5.6.3` - 타입 안정성
- **Vite** `6.4.1` - 빌드 도구 및 개발 서버

### 주요 라이브러리
- **react-router-dom** `7.10.1` - 클라이언트 사이드 라우팅
- **axios** `1.13.2` - HTTP 클라이언트 (자동 토큰 갱신 인터셉터 포함)
- **react-markdown** `10.1.0` - 마크다운 렌더링
- **remark-gfm** `4.0.1` / **remark-breaks** `4.0.0` - 마크다운 확장 플러그인
- **@tiptap/react** `3.20.4` - 리치 텍스트 에디터 (이미지 지원 포함)

### 개발 도구
- **ESLint** `9.39.1` - 코드 품질 관리
- **TypeScript ESLint** `8.49.0` - TypeScript 린팅
- **@vitejs/plugin-react** `4.7.0` - React Fast Refresh
- **vite-plugin-svgr** `5.2.0` - SVG → React 컴포넌트 변환 (다크모드 아이콘 색상 제어용)

### 버전 관리
- 모든 의존성은 **고정**(Pinned)되어 있습니다.
- 캐럿(`^`)이나 틸드(`~`) 없이 고정된 버전을 사용하여 빌드 안정성 보장


## 시스템 아키텍처

### 인증 흐름 (Azure AD OAuth 2.0 + JWT)

```
1. 사용자 로그인 시도
   ↓
2. Frontend → Backend: Azure AD 로그인 URL 요청
   ↓
3. Azure AD OAuth 페이지로 리다이렉트
   ↓
4. 사용자 인증 후 콜백 URL로 리다이렉트 (/auth/callback?code=...)
   ↓
5. Frontend → Backend: Authorization Code 전송
   ↓
6. Backend: Access Token + Refresh Token 발급
   - Access Token: 메모리에 저장 (짧은 유효기간)
   - Refresh Token: HttpOnly 쿠키 (긴 유효기간)
   ↓
7. 이후 모든 API 요청에 자동으로 인증 처리
```

### 자동 토큰 갱신 메커니즘
- **401 에러 감지** → 자동으로 `/auth/refresh` 호출
- **Refresh Token**을 이용한 새로운 Access Token 발급
- **실패한 요청 큐 관리**: 토큰 갱신 중 발생한 요청들을 큐에 저장 후 재시도
- **갱신 실패 시**: 자동 로그아웃 및 로그인 페이지로 리다이렉트

### 에러 핸들링 (FRN 코드 시스템)
프론트엔드 자체 에러 코드 체계를 사용하여 에러를 추적합니다.

```
FRN + AABBCD
  AA: 기능 영역 (01=Auth, 02=Document, 03=Chat, 04=Common)
  BB: 처리 단계 (01=Validation, 02=API/State, 03=Local Logic)
  CD: 세부 에러 코드
```


## 로컬 개발 환경 설정

### 필수 환경

#### 1. Node.js 버전
```bash
# 권장 버전
Node.js: v24.11.1

# 버전 확인
node --version
```

#### 2. Package Manager
```bash
# npm 사용 (package-lock.json 기준)
npm --version
```

### 설치 및 실행

#### 1. 의존성 설치
```bash
# 프로젝트 루트 디렉토리에서 실행
npm install
```

#### 2. 환경 변수 설정
`.env` 파일을 프로젝트 루트에 생성하고 아래 내용을 추가하세요:

```bash
# 백엔드 API 기본 주소
VITE_API_URL=https://127.0.0.1/
```

#### 3. 개발 서버 실행
```bash
npm run dev
```

개발 서버가 실행되면 다음 주소로 접속할 수 있습니다:
- **네트워크**: http://0.0.0.0:5173 (모든 네트워크 인터페이스에서 접근 가능)

#### 4. 프로덕션 빌드
```bash
# TypeScript 컴파일 + Vite 빌드
npm run build

# 빌드 결과 미리보기
npm run preview
```

#### 5. 코드 린팅
```bash
npm run lint
```

## 프로젝트 구조

```
src/
├── assets/                        # 정적 리소스
│   ├── icons/                     # UI 아이콘 (SVG)
│   ├── admin/                     # 관리자 아이콘
│   ├── chats/                     # 채팅 관련 아이콘
│   ├── docs/                      # 문서 관련 아이콘
│   ├── sidebar/                   # 사이드바 전용 아이콘 (fold, notification, light/dark)
│   ├── status/                    # 문서 상태 아이콘
│   ├── errors/                    # 에러 페이지 일러스트
│   └── index.ts                   # 에셋 배럴 파일
│
├── components/                    # 재사용 가능한 공통 컴포넌트
│   ├── AppSidebar.tsx             # 메인 사이드바 (채팅/문서/관리자 네비게이션)
│   └── common/                    # 공통 UI 컴포넌트
│       ├── CustomModal.tsx        # 범용 알림/확인 모달
│       ├── DropdownMenu.tsx       # 드롭다운 메뉴
│       ├── ErrorReportButton.tsx  # 오류 리포트 버튼
│       ├── ErrorReportModal.tsx   # 오류 리포트 모달
│       ├── MaintenanceOverlay.tsx # 서비스 점검 오버레이
│       ├── NewChatButton.tsx      # 새 채팅 버튼 (그라데이션)
│       ├── NotificationButton.tsx # 알림 버튼 + 드롭다운 (사이드바 헤더)
│       ├── Pagination.tsx         # 페이지네이션
│       ├── ProfileSection.tsx     # 사용자 프로필 + 다크모드 토글 버튼
│       ├── SidebarShell.tsx       # 사이드바 스크롤/레이아웃 셸
│       ├── Skeleton.tsx           # 로딩 스켈레톤
│       ├── SortToggleButton.tsx   # 정렬 토글 버튼
│       ├── StatusBadge.tsx        # 문서 상태 뱃지
│       ├── SurveyForm.tsx         # 만족도 조사 폼
│       ├── TableSkeleton.tsx      # 테이블 로딩 스켈레톤
│       ├── TiptapEditor.tsx       # 리치 텍스트 에디터
│       └── UpdateNoticeModal.tsx  # 서비스 업데이트 공지 모달
│
├── constants/                     # 애플리케이션 상수
│   └── customCodes.ts             # FRN 에러 코드 정의
│
├── contexts/                      # React Context 프로바이더
│   ├── ModalContext.tsx            # 전역 모달/알림 관리
│   └── ThemeContext.tsx            # 라이트/다크 테마 전환
│
├── features/                      # 기능 모듈 (Feature-based Architecture)
│   ├── admin/                     # 관리자 기능
│   │   ├── AdminAuthority.tsx     # 권한 관리
│   │   ├── AdminDocumentStorage.tsx # 문서 저장소 관리
│   │   ├── AdminUserManagement.tsx  # 사용자 관리
│   │   ├── DeptAddModal.tsx       # 부서 추가 모달
│   │   └── types.ts               # 관리자 타입 정의
│   │
│   ├── auth/                      # 인증 기능
│   │   ├── AuthContext.tsx        # 인증 상태 관리 (useAuth 훅)
│   │   ├── LoginCallback.tsx      # OAuth 콜백 핸들러
│   │   └── LoginPage.tsx          # 로그인 페이지
│   │
│   ├── chat/                      # 채팅 기능
│   │   ├── ChatInput.tsx          # 메시지 입력 (자동 높이 조절)
│   │   ├── ChatLayout.tsx         # 채팅 페이지 레이아웃
│   │   ├── ChatMessageList.tsx    # 메시지 목록 (피드백 버튼 포함)
│   │   ├── ChatRoomList.tsx       # 채팅방 사이드바 목록
│   │   ├── ChatRoomsContext.tsx   # 채팅방 상태 관리
│   │   └── types.ts               # 채팅 타입 정의
│   │
│   └── documents/                 # 문서 관리 기능
│       ├── MyDocumentsList.tsx    # 문서 목록 (그리드 레이아웃)
│       ├── useDocumentUpload.ts   # 파일 업로드 훅 (세션 기반)
│       ├── useKnowledgeToggle.ts  # RAG 참조 토글 훅
│       └── types.ts               # 문서 타입 및 유효성 검사 상수
│
├── hooks/                         # 커스텀 React 훅
│   ├── useAlarms.ts               # 알림 조회/읽음 처리 (폴링 + visibilitychange)
│   └── useMediaQuery.ts           # 반응형 디자인 브레이크포인트 훅
│
├── layouts/                       # 페이지 레이아웃
│   ├── AuthLayout.tsx             # 로그인 페이지 레이아웃
│   └── PageLayout.tsx             # 메인 앱 레이아웃 (접이식 사이드바)
│
├── lib/                           # 유틸리티 라이브러리
│   ├── apiClient.ts               # Axios 인스턴스 (토큰 갱신 인터셉터)
│   ├── customError.ts             # FRN 에러 코드 핸들링
│   └── fileUtils.ts               # 파일 유틸리티 (해시, 사이즈 포맷, 날짜 포맷)
│
├── pages/                         # 페이지 컴포넌트
│   ├── AdminMainPage.tsx          # 관리자 대시보드
│   ├── ChatPage.tsx               # 채팅 페이지
│   ├── ErrorPage.tsx              # 에러/접근 거부 페이지
│   └── MyDocumentsPage.tsx        # 내 문서 관리 페이지
│
├── routes/                        # 라우팅 설정
│   ├── AppRoutes.tsx              # 라우트 정의 (역할 기반 접근 제어)
│   └── ProtectedRoute.tsx         # 인증 필요 라우트 보호 HOC
│
├── services/                      # API 서비스 레이어
│   ├── admin.service.ts           # 관리자 API (사용자/권한/문서 관리)
│   ├── auth.service.ts            # 인증 API (로그인 URL, 프로필, 로그아웃)
│   ├── board.service.ts           # 게시판/설문 API
│   ├── chat.service.ts            # 채팅 API (SSE 스트리밍, 채팅방 CRUD)
│   └── document.service.ts        # 문서 API (다운로드, 참조 토글)
│
├── styles/                        # 스타일 정의
│   ├── buttonStyles.ts            # 버튼 스타일 및 색상 상수 (그라데이션 버튼 공통)
│   └── theme.css                  # 디자인 토큰 (라이트/다크 CSS 변수)
│
├── types/                         # 전역 타입 정의
│   └── index.ts                   # 공통 인터페이스 (ApiResponse, User)
│
├── App.tsx                        # 루트 컴포넌트 (프로바이더 구성)
├── App.css                        # 전역 스타일
├── main.tsx                       # 앱 엔트리 포인트
└── index.css                      # 기본 CSS
```

### 주요 디렉토리 설명

#### `src/features/`
- **기능 중심 구조 (Feature-based Architecture)**
- 각 기능별로 컴포넌트, 훅, 타입을 모듈화
- 코드 응집도 향상 및 유지보수 용이

#### `src/services/`
- **API 통신 로직 분리**
- 백엔드 엔드포인트와 1:1 매핑
- 비즈니스 로직과 UI 로직 분리

#### `src/lib/apiClient.ts`
- **Axios 인스턴스 설정**
- 자동 토큰 갱신 인터셉터
- 401 에러 핸들링 및 요청 큐 관리
- 타임아웃 30초

#### `src/contexts/`
- **전역 상태 관리** (Context API)
- 모달 시스템: Promise 기반 alert/confirm API
- 테마 시스템: 라이트/다크 모드 (localStorage 영속화)

#### `src/components/common/`
- **재사용 가능한 UI 컴포넌트**
- 서비스 점검 오버레이, 로딩 스켈레톤, 상태 뱃지 등


## 환경 변수 설정

### `.env` 파일 구성

```bash
# 백엔드 API 기본 주소 (Gateway를 통한 접근)
VITE_API_URL=https://BACKEND_SERVER_URL/
```

### Vite 환경 변수 규칙
- `VITE_` 접두사가 붙은 변수만 클라이언트 코드에서 접근 가능
- `import.meta.env.VITE_API_URL` 형태로 사용


## 빌드 및 배포

### 프로덕션 빌드

```bash
# TypeScript 컴파일 + Vite 빌드
npm run build

# 결과물: dist/ 디렉토리에 생성
```

### 빌드 결과물 구조

```
dist/
├── assets/
│   ├── index-[hash].js      # 번들된 JavaScript
│   ├── index-[hash].css     # 번들된 CSS
│   └── ...
├── index.html                # 엔트리 HTML
└── ...
```

### Docker 배포
프로젝트에 `Dockerfile`, `docker-compose.yml`, `docker-compose.dev.yml`, `nginx.conf`가 포함되어 있어 컨테이너 기반 배포를 지원합니다.

### 배포 시 주의사항

#### 1. 환경 변수 설정
프로덕션 환경에서는 `.env.production` 파일 사용:

```bash
VITE_API_URL=https://production.example.com/
```

#### 2. SPA 라우팅 설정
모든 경로를 `index.html`로 리다이렉트하도록 웹 서버 설정:

**Nginx 예시:**
```nginx
location / {
  try_files $uri $uri/ /index.html;
}
```

#### 3. API Proxy 설정
프로덕션에서는 Nginx 등에서 `/api` 경로를 백엔드로 프록시:

```nginx
location /api/ {
  proxy_pass https://backend.example.com/;
  proxy_set_header Host $host;
  proxy_set_header X-Real-IP $remote_addr;
}
```

### 빌드 최적화

- **Code Splitting**: 라우트별 자동 코드 분할
- **Tree Shaking**: 사용하지 않는 코드 제거
- **Minification**: JavaScript, CSS 압축
- **Asset Optimization**: 이미지 및 폰트 최적화


## 개발 가이드

### 코딩 컨벤션

#### 1. 파일 명명 규칙
- **컴포넌트**: PascalCase (예: `ChatInput.tsx`)
- **서비스/유틸**: camelCase (예: `auth.service.ts`)
- **타입 정의**: `types.ts`
- **아이콘 import**: 아래 "아이콘 사용 규칙" 참고

#### 2. 아이콘 사용 규칙
아이콘은 **두 가지 방식**을 상황에 맞춰 선택합니다.

**A. URL 방식 (`<img>`)** — 색이 항상 고정일 때
```tsx
import { chatIcon } from '../../assets/chats';
<img src={chatIcon} alt="..." />
```
- 예: 그라데이션 버튼 위의 흰색 아이콘, 활성 상태 전용 고정 색 아이콘
- 배럴 파일(`assets/icons/index.ts` 등)을 통해 import

**B. SVGR 컴포넌트 방식 (`?react`)** — 테마/상태에 따라 색이 바뀌어야 할 때
```tsx
import DocIcon from '../../assets/icons/doc.svg?react';
<DocIcon width={20} height={20} style={{ color: 'var(--icon-color)' }} />
```
- SVG 파일의 `stroke`/`fill`을 `currentColor`로 편집
- `color` CSS 속성으로 외부 제어 (CSS 변수 `--icon-color`, `--icon-active-color` 활용)
- 다크모드 자동 반영 가능
- `vite-plugin-svgr`가 빌드 타임에 React 컴포넌트로 변환

**선택 기준**: "이 SVG 파일이 다른 곳에서 다른 색으로도 쓰일 수 있는가?"
- 있다 / 테마 대응 필요 → **B (SVGR)**
- 없다 / 항상 한 색 고정 → **A (URL)**

#### 3. 컴포넌트 구조
```typescript
// 1. Import (외부 라이브러리)
import React from 'react';

// 2. Import (내부 모듈)
import { useAuth } from '../auth/AuthContext';

// 3. 타입 정의
interface Props {
  // ...
}

// 4. 컴포넌트 정의
function Component({ props }: Props) {
  // ...
}

// 5. Export
export default Component;
```

#### 4. TypeScript 사용 권장사항
- `any` 타입 사용 최소화
- 인터페이스 우선, 필요 시 타입 별칭 사용
- 제네릭을 활용한 타입 안정성 확보

### 테마 / 다크 모드

라이트/다크 모드는 `src/styles/theme.css`에 정의된 CSS 변수 기반으로 동작합니다.

#### 작동 방식
- `ThemeContext`(`src/contexts/ThemeContext.tsx`)가 `<html data-theme="light|dark">` 속성을 토글
- `theme.css`의 `:root`(라이트)와 `[data-theme='dark']`(다크) 블록이 동일 변수에 다른 값을 할당
- 사용자 선택은 `localStorage`에 저장되어 새로고침 후에도 유지

#### 주요 디자인 토큰
```
--color-grayscale-*   : 회색조 팔레트 (다크에서 반전)
--color-primary-*     : 보라 팔레트 (다크에서 반전)
--icon-color          : 일반 아이콘 기본 색 (라이트 #292B2F / 다크 #F7F7F7)
--icon-active-color   : 선택·hover 상태 아이콘 색 (라이트 #626BF7 / 다크 #B4BDFA)
--main-gradient       : 메인 영역 배경 그라데이션 (테마별 별도 지정)
```

#### 일관성 규칙
- 컴포넌트에서 hex 색을 **하드코딩하지 않음** — 모두 `var(--...)` 사용
- 그라데이션 버튼 (New Chat, 제출 등)은 **의도적으로** 라이트/다크 동일 보라색 유지
  (`src/styles/buttonStyles.ts`의 `GRADIENT` 상수는 hex로 고정)
- 아이콘 색은 위 "아이콘 사용 규칙" 참고

### Git 브랜치 전략
```
main (production)
  ↑
develop (development)
  ↑
feature/기능명 (feature branches)
```


## 트러블슈팅

### 1. 토큰 갱신 실패
**증상**: 로그인 후 자동으로 로그아웃됨

**해결방법**:
- 브라우저 쿠키 확인 (Refresh Token이 HttpOnly 쿠키로 저장되어야 함)
- 백엔드 `/auth/refresh` 엔드포인트 정상 동작 확인
- `withCredentials: true` 설정 확인

### 2. CORS 에러
**증상**: API 요청 시 CORS 에러 발생

**해결방법**:
- 백엔드에서 CORS 설정 확인
- `withCredentials: true` 사용 시 백엔드에서 `Access-Control-Allow-Credentials: true` 설정 필요
- 개발 환경에서는 Vite Proxy 사용

### 3. SSE 스트리밍 끊김
**증상**: 채팅 응답이 중간에 끊김

**해결방법**:
- 네트워크 타임아웃 설정 확인 (30초 이상 권장)
- Nginx 등 프록시 서버의 버퍼링 설정 확인
- `X-Accel-Buffering: no` 헤더 추가

### 4. 빌드 에러
**증상**: `npm run build` 실패

**해결방법**:
```bash
# node_modules 삭제 후 재설치
rm -rf node_modules package-lock.json
npm install

# TypeScript 에러 확인
npm run lint
```

**마지막 업데이트**: 2026-04-24
