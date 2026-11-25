import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import request from 'supertest';
import { App } from 'supertest/types';
import { JwtService } from '@nestjs/jwt';
import { AppModule } from '../src/app.module';

describe('Auth API (e2e)', () => {
  let app: INestApplication<App>;
  let jwtService: JwtService;
  let validAccessToken: string;
  let validRefreshToken: string;

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ whitelist: true }));
    await app.init();

    jwtService = moduleFixture.get<JwtService>(JwtService);

    // Generate valid tokens for testing
    const payload = {
      sub: 'test-user-id',
      email: 'test@example.com',
      name: 'Test User',
    };

    validAccessToken = jwtService.sign(payload, { expiresIn: '15m' });
    validRefreshToken = jwtService.sign(payload, { expiresIn: '7d' });
  });

  afterAll(async () => {
    await app.close();
  });

  describe('POST /auth/refresh', () => {
    it('[P0] should return new tokens for valid refresh token', async () => {
      // GIVEN: Valid refresh token
      const refreshDto = { refreshToken: validRefreshToken };

      // WHEN: Refreshing tokens
      const response = await request(app.getHttpServer())
        .post('/auth/refresh')
        .send(refreshDto);

      // THEN: Returns 200 with new tokens
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('accessToken');
      expect(response.body).toHaveProperty('refreshToken');
      expect(response.body).toHaveProperty('expiresIn');
    });

    it('[P1] should return 401 for invalid refresh token', async () => {
      // GIVEN: Invalid refresh token
      const refreshDto = { refreshToken: 'invalid-token' };

      // WHEN: Attempting to refresh
      const response = await request(app.getHttpServer())
        .post('/auth/refresh')
        .send(refreshDto);

      // THEN: Returns 401 Unauthorized
      expect(response.status).toBe(401);
    });

    it('[P1] should return 401 for expired refresh token', async () => {
      // GIVEN: Expired refresh token
      const expiredToken = jwtService.sign(
        { sub: 'test', email: 'test@test.com', name: 'Test' },
        { expiresIn: '-1s' },
      );
      const refreshDto = { refreshToken: expiredToken };

      // WHEN: Attempting to refresh with expired token
      const response = await request(app.getHttpServer())
        .post('/auth/refresh')
        .send(refreshDto);

      // THEN: Returns 401 Unauthorized
      expect(response.status).toBe(401);
    });
  });

  describe('POST /auth/logout', () => {
    it('[P1] should return 200 for authenticated user', async () => {
      // GIVEN: Valid access token
      // WHEN: Logging out
      const response = await request(app.getHttpServer())
        .post('/auth/logout')
        .set('Authorization', `Bearer ${validAccessToken}`);

      // THEN: Returns 200 with success message
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty(
        'message',
        'Logged out successfully',
      );
    });

    it('[P1] should return 401 for unauthenticated request', async () => {
      // GIVEN: No authentication
      // WHEN: Attempting to logout
      const response = await request(app.getHttpServer()).post('/auth/logout');

      // THEN: Returns 401 Unauthorized
      expect(response.status).toBe(401);
    });

    it('[P1] should return 401 for invalid access token', async () => {
      // GIVEN: Invalid access token
      // WHEN: Attempting to logout
      const response = await request(app.getHttpServer())
        .post('/auth/logout')
        .set('Authorization', 'Bearer invalid-token');

      // THEN: Returns 401 Unauthorized
      expect(response.status).toBe(401);
    });
  });

  describe('GET /auth/me', () => {
    it('[P1] should return user info for authenticated user', async () => {
      // GIVEN: Valid access token
      // WHEN: Getting profile
      const response = await request(app.getHttpServer())
        .get('/auth/me')
        .set('Authorization', `Bearer ${validAccessToken}`);

      // THEN: Returns 200 with user data
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('data');
      expect(response.body.data).toHaveProperty('userId', 'test-user-id');
      expect(response.body.data).toHaveProperty('email', 'test@example.com');
      expect(response.body.data).toHaveProperty('name', 'Test User');
    });

    it('[P1] should return 401 for unauthenticated request', async () => {
      // GIVEN: No authentication
      // WHEN: Getting profile
      const response = await request(app.getHttpServer()).get('/auth/me');

      // THEN: Returns 401 Unauthorized
      expect(response.status).toBe(401);
    });
  });
});
