# Test Suite Documentation

## Overview

This project uses **Jest** for both unit and E2E/integration testing following NestJS best practices.

## Test Structure

```
src/
├── auth/
│   └── auth.service.spec.ts    # AuthService unit tests
├── chat/
│   └── chat.service.spec.ts    # ChatService unit tests
└── ...

test/
├── app.e2e-spec.ts             # Basic app E2E test
├── auth.e2e-spec.ts            # Auth API integration tests
├── chat.e2e-spec.ts            # Chat API integration tests
├── jest-e2e.json               # E2E Jest configuration
└── README.md                   # This file
```

## Running Tests

### Unit Tests

```bash
# Run all unit tests
npm run test

# Run with coverage
npm run test:cov

# Run in watch mode
npm run test:watch

# Run specific test file
npm run test -- --testPathPatterns="auth.service.spec"
npm run test -- --testPathPatterns="chat.service.spec"
```

### E2E Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run specific E2E test file
npm run test:e2e -- --testPathPatterns="auth.e2e-spec"
npm run test:e2e -- --testPathPatterns="chat.e2e-spec"
```

### Run by Priority

```bash
# Run P0 tests only (critical paths)
npm run test -- --testNamePattern="\[P0\]"

# Run P0 + P1 tests
npm run test -- --testNamePattern="\[P0\]|\[P1\]"

# Run all prioritized tests
npm run test -- --testNamePattern="\[P"
```

## Priority Tags

All tests are tagged with priority levels in their test names:

- **[P0]**: Critical paths - run on every commit
- **[P1]**: High priority - run on PR to main
- **[P2]**: Medium priority - run nightly
- **[P3]**: Low priority - run on-demand

## Test Patterns

### Given-When-Then Format

All tests follow the Given-When-Then format for clarity:

```typescript
it('[P1] should return new tokens for valid refresh token', async () => {
  // GIVEN: Valid refresh token payload
  const mockPayload = { sub: 'user-123', email: 'user@example.com' };
  mockJwtService.verify.mockReturnValue(mockPayload);

  // WHEN: Refreshing tokens
  const result = await service.refreshTokens('valid-refresh-token');

  // THEN: Returns new access and refresh tokens
  expect(result).toHaveProperty('accessToken');
  expect(result).toHaveProperty('refreshToken');
});
```

### Mocking Dependencies

Use Jest mocks for external dependencies:

```typescript
const mockRepository = {
  create: jest.fn(),
  save: jest.fn(),
  find: jest.fn(),
  findOne: jest.fn(),
  remove: jest.fn(),
};

beforeEach(async () => {
  const module: TestingModule = await Test.createTestingModule({
    providers: [
      YourService,
      { provide: getRepositoryToken(YourEntity), useValue: mockRepository },
    ],
  }).compile();
});
```

### E2E Testing with Supertest

```typescript
it('[P1] should return 200 for authenticated user', async () => {
  const response = await request(app.getHttpServer())
    .get('/auth/me')
    .set('Authorization', `Bearer ${validAccessToken}`);

  expect(response.status).toBe(200);
  expect(response.body.data).toHaveProperty('userId');
});
```

## Test Coverage

Current test coverage:

| Module | Service | Controller | E2E |
|--------|---------|------------|-----|
| Auth   | ✅      | -          | ✅  |
| Chat   | ✅      | -          | ✅  |

## Writing New Tests

1. Create test file with `.spec.ts` suffix for unit tests
2. Use Given-When-Then format for clarity
3. Add priority tag to test name: `[P0]`, `[P1]`, `[P2]`, or `[P3]`
4. Mock external dependencies (repositories, services)
5. Clear mocks in `afterEach()`

## Common Issues

### Database Connection in E2E Tests

E2E tests require a running database. Make sure Docker is running:

```bash
docker-compose up -d postgres
```

### JWT Token for E2E Tests

Generate test tokens in `beforeAll()`:

```typescript
validAccessToken = jwtService.sign(
  { sub: 'test-user-id', email: 'test@example.com', name: 'Test User' },
  { expiresIn: '15m' },
);
```
