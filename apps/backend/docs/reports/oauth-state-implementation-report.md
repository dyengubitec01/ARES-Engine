# OAuth State Parameter 도입 보고서

**작성일:** 2025-12-15
**작성자:** SM Agent (Bob)
**프로젝트:** backend - 사내 AI 게이트웨이

---

## 1. 개요

본 보고서는 Azure AD OAuth 2.0 로그인 구현 시 **State Parameter 방식**을 도입한 배경, 구현 방법, 그리고 보안상의 이점을 설명합니다.

---

## 2. 도입 배경

### 2.1 기존 OAuth 플로우의 보안 취약점

초기 OAuth 구현에서는 다음과 같은 단순한 플로우를 사용했습니다:

```
1. 프론트엔드 → Azure AD 로그인 페이지로 리다이렉트
2. 사용자 인증 완료 → Azure가 authorization code와 함께 콜백
3. 백엔드가 code를 받아 토큰 교환
```

이 방식은 **CSRF (Cross-Site Request Forgery)** 공격에 취약합니다:

```
공격 시나리오:
1. 공격자가 자신의 Azure 계정으로 로그인하여 authorization code 획득
2. 피해자에게 해당 code가 포함된 콜백 URL을 클릭하도록 유도
3. 피해자의 세션이 공격자의 계정으로 로그인됨
4. 피해자가 입력하는 모든 데이터가 공격자 계정에 저장됨
```

### 2.2 State Parameter의 필요성

OAuth 2.0 RFC 6749에서는 **state parameter**를 권장합니다:

> "The state parameter is used to maintain state between the request and callback.
> It SHOULD be used to prevent cross-site request forgery."

---

## 3. 구현 방식

### 3.1 State 생성 및 검증 로직

**백엔드 메모리 저장소 + 쿠키 이중 검증 방식** 채택

```typescript
// AuthService - State 관리
private readonly stateStore = new Map<string, { createdAt: number }>();
private static readonly STATE_TTL_MS = 5 * 60 * 1000; // 5분

generateLoginUrl(): { url: string; state: string } {
  const state = randomBytes(32).toString('hex');  // 64자 랜덤 문자열
  this.stateStore.set(state, { createdAt: Date.now() });
  // ... Azure 로그인 URL 생성
  return { url, state };
}

validateState(state: string): boolean {
  const storedState = this.stateStore.get(state);
  if (!storedState) return false;
  if (Date.now() - storedState.createdAt > STATE_TTL_MS) {
    this.stateStore.delete(state);
    return false;
  }
  this.stateStore.delete(state);  // 일회성 사용
  return true;
}
```

### 3.2 인증 플로우

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        OAuth 2.0 + State 인증 플로우                          │
└─────────────────────────────────────────────────────────────────────────────┘

[Frontend]                    [Backend]                      [Azure AD]
    │                             │                              │
    │  1. GET /auth/login-url     │                              │
    │ ─────────────────────────►  │                              │
    │                             │                              │
    │                        ┌────┴────┐                         │
    │                        │ Generate │                        │
    │                        │ state    │                        │
    │                        │ (64 hex) │                        │
    │                        └────┬────┘                         │
    │                             │                              │
    │  2. { authUrl }             │                              │
    │    + Set-Cookie: oauth_state│                              │
    │ ◄─────────────────────────  │                              │
    │                             │                              │
    │  3. window.location = authUrl (브라우저 리다이렉트)         │
    │ ──────────────────────────────────────────────────────────►│
    │                             │                              │
    │                             │     [User authenticates]     │
    │                             │                              │
    │                             │  4. GET /auth/callback       │
    │                             │     ?code=xxx&state=yyy      │
    │                             │     + Cookie: oauth_state    │
    │                             │ ◄────────────────────────────│
    │                             │                              │
    │                        ┌────┴────┐                         │
    │                        │ Validate │                        │
    │                        │ state x2 │                        │
    │                        │ (cookie  │                        │
    │                        │  + store)│                        │
    │                        └────┬────┘                         │
    │                             │                              │
    │                             │  5. Exchange code for token  │
    │                             │ ────────────────────────────►│
    │                             │                              │
    │                             │  6. Azure tokens + user info │
    │                             │ ◄────────────────────────────│
    │                             │                              │
    │                        ┌────┴────┐                         │
    │                        │ Generate │                        │
    │                        │ our JWT  │                        │
    │                        │ tokens   │                        │
    │                        └────┬────┘                         │
    │                             │                              │
    │  7. 302 Redirect to Frontend                               │
    │     + Set-Cookie: access_token, refresh_token (httpOnly)   │
    │ ◄─────────────────────────  │                              │
    │                             │                              │
    │  8. GET /auth/me (로그인 상태 확인)                          │
    │ ─────────────────────────►  │                              │
    │                             │                              │
```

**핵심 포인트:**
- Azure AD는 **백엔드** `/auth/callback`으로 직접 리다이렉트 (프론트 경유 X)
- redirect_uri 설정: `http://localhost:3000/auth/callback` (백엔드 URL)
- 프론트엔드는 로그인 완료 후 메인 페이지로 자동 리다이렉트됨

### 3.3 이중 검증 메커니즘

| 검증 단계 | 위치 | 목적 |
|----------|------|------|
| 1차 검증 | Cookie vs Query | 요청 발신자가 동일 브라우저인지 확인 |
| 2차 검증 | Memory Store | 서버가 발급한 유효한 state인지 확인 |

```typescript
// AuthController - Callback 처리
@Get('callback')
async callback(@Query('state') state, @Req() req, @Res() res) {
  const storedState = req.cookies?.['oauth_state'];

  // 1차: 쿠키와 쿼리 파라미터 비교
  if (!state || !storedState || state !== storedState) {
    throw new UnauthorizedException('Invalid state - possible CSRF attack');
  }

  // 2차: 백엔드 저장소 검증 (일회성, TTL 확인)
  if (!this.authService.validateState(state)) {
    throw new UnauthorizedException('State expired or already used');
  }

  // 검증 통과 → 토큰 교환 진행
}
```

---

## 4. 보안상의 이점

### 4.1 CSRF 공격 방어

| 공격 시도 | State 없음 | State 있음 |
|----------|------------|------------|
| 공격자가 자신의 code로 피해자 세션 탈취 | ❌ 취약 | ✅ 방어 |
| 외부 사이트에서 콜백 URL 호출 | ❌ 취약 | ✅ 방어 |

**방어 원리:**
- 공격자는 피해자 브라우저의 `oauth_state` 쿠키 값을 알 수 없음
- 공격자가 만든 콜백 URL의 state와 피해자 쿠키의 state가 불일치
- 백엔드 저장소에 없는 state는 즉시 거부

### 4.2 Replay Attack 방어

```typescript
this.stateStore.delete(state);  // 검증 후 즉시 삭제
```

- 동일한 state로 여러 번 콜백 시도 불가
- **일회성 사용** 보장

### 4.3 만료 기반 보안

```typescript
if (Date.now() - storedState.createdAt > STATE_TTL_MS) {
  return false;  // 5분 초과 시 거부
}
```

- 오래된 로그인 시도 자동 만료
- 로그인 URL 공유로 인한 악용 방지

### 4.4 httpOnly 쿠키와의 시너지

| 보안 기능 | 역할 |
|----------|------|
| State Parameter | OAuth 플로우 CSRF 방어 |
| httpOnly Cookie | XSS 공격으로부터 토큰 보호 |
| SameSite=Lax | OAuth 리다이렉트 호환성 + CSRF 방어 |

**삼중 보안 체계 구축**

---

## 4.5 SameSite 쿠키 설정: Strict vs Lax

### 문제 상황 (2025-12-21 발견)

초기 구현에서 `sameSite: 'strict'` 설정으로 인해 OAuth 콜백 시 쿠키가 전달되지 않는 문제 발생:

```
=== OAuth State Validation Debug ===
Query state: bc317c56bb0e76b8f6d36b69078c261ca07aa5e0059ede7d17fd32d3fd61b2de
Cookie state: undefined
All cookies: {}
State match: false
====================================
```

**원인:**
- Azure AD (`login.microsoftonline.com`)는 외부 도메인
- `sameSite: 'strict'`는 외부 사이트에서의 모든 요청에 대해 쿠키 전송 차단
- Azure 콜백 시 브라우저가 `oauth_state` 쿠키를 전송하지 않음

### SameSite 속성 비교

| 속성 | 동작 | OAuth 호환성 | 보안 수준 |
|------|------|-------------|----------|
| **`strict`** | 완전히 같은 사이트에서만 쿠키 전송 | ❌ **불가능** | 최고 |
| **`lax`** | 외부 사이트에서 GET 요청으로 돌아올 때 쿠키 전송 | ✅ **가능** | 높음 |
| **`none`** | 모든 요청에 쿠키 전송 (HTTPS 필수) | ✅ 가능 | 낮음 |

### 해결 방법: sameSite: 'lax' 적용

```typescript
// auth.controller.ts
const COOKIE_OPTIONS = {
  httpOnly: true,
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'lax' as const, // Changed from 'strict' to 'lax'
  path: '/',
};
```

### Lax의 동작 방식

```
1. 프론트: GET /auth/login-url
   → 백엔드: oauth_state 쿠키 설정 (sameSite: lax)
   → 브라우저: 쿠키 저장

2. 프론트: window.location = authUrl (Azure로 리다이렉트)
   → 사용자: Azure 로그인 완료

3. Azure → 백엔드: GET /auth/callback?code=...&state=...
   → ✅ sameSite: lax는 외부에서 GET으로 돌아오는 것 허용
   → 브라우저: oauth_state 쿠키 자동 전송 (백엔드 도메인이므로)
   → 백엔드: state 검증 성공!

4. 백엔드 → 프론트: 302 Redirect + JWT 쿠키 설정
   → 프론트: 메인 페이지로 돌아옴 (로그인 완료)
```

### 보안성 검토

**Lax는 여전히 안전합니다:**

- ❌ **차단**: 외부 사이트에서 POST/PUT/DELETE 요청 시 쿠키 전송 안 됨
- ✅ **허용**: 외부 사이트에서 GET 요청으로 돌아올 때만 쿠키 전송
- **CSRF 방어 유지**: State 이중 검증 (쿠키 + 메모리 저장소)은 그대로 동작
- **OAuth 2.0 호환**: Azure AD 콜백 시나리오에 최적화

### Azure State 파라미터 전달 방식

Azure AD는 **state 파라미터를 해석하지 않고 그대로 반환**합니다:

```
1. 백엔드 → Azure 로그인 URL 생성
   https://login.microsoftonline.com/.../authorize?
     state=bc317c56bb0e76b8f6d36b69078c261ca07aa5e0059ede7d17fd32d3fd61b2de
     &client_id=xxx&redirect_uri=...

2. 사용자 → Azure 인증

3. Azure → 백엔드 콜백
   http://localhost:3000/auth/callback?
     code=AUTHORIZATION_CODE
     &state=bc317c56bb0e76b8f6d36b69078c261ca07aa5e0059ede7d17fd32d3fd61b2de
     (우리가 보낸 state를 그대로 돌려줌)
```

**OAuth 2.0 RFC 6749 명세:**
> "The authorization server includes this value when redirecting the user-agent back to the client."

즉, Azure는 state를 단순히 에코(echo)하는 역할만 하며, 검증은 백엔드의 책임입니다.

---

## 5. 현재 로그인 API 구조

### 5.1 엔드포인트 목록

| Method | Endpoint | 설명 | 인증 |
|--------|----------|------|------|
| GET | /auth/login-url | Azure 로그인 URL 생성 | Public |
| GET | /auth/callback | OAuth 콜백 처리 | Public |
| POST | /auth/refresh | 토큰 갱신 | Public |
| POST | /auth/logout | 로그아웃 | JWT |
| GET | /auth/profile | 사용자 정보 | JWT |

### 5.2 토큰 관리

| 토큰 | 만료 시간 | 저장 위치 | 용도 |
|------|----------|----------|------|
| access_token | 15분 | httpOnly Cookie | API 인증 |
| refresh_token | 7일 | httpOnly Cookie | 토큰 갱신 |
| oauth_state | 5분 | httpOnly Cookie + Memory | CSRF 방어 |

### 5.3 제거된 API

| Endpoint | 제거 사유 |
|----------|----------|
| POST /auth/login | callback이 동일 기능 + state 검증 포함 |

---

## 6. 결론

### 6.1 도입 효과

1. **보안 강화**: CSRF, Replay Attack 방어
2. **표준 준수**: OAuth 2.0 RFC 6749 권장사항 충족
3. **코드 간소화**: 중복 API 제거 (POST /auth/login)

### 6.2 운영 고려사항

- **메모리 저장소**: 현재 단일 서버 환경에 적합
- **다중 서버 환경**: Redis 등 분산 저장소로 전환 필요
- **State 정리**: setInterval로 만료된 state 자동 정리 구현됨

---

## 7. 관련 파일

| 파일 | 역할 |
|------|------|
| [auth.service.ts](../../src/auth/auth.service.ts) | State 생성/검증, 토큰 관리 |
| [auth.controller.ts](../../src/auth/auth.controller.ts) | 로그인 API 엔드포인트 |
| [jwt-auth.guard.ts](../../src/auth/guards/jwt-auth.guard.ts) | JWT 검증 가드 |

---

**문서 끝**
