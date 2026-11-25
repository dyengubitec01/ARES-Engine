import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication, ValidationPipe } from '@nestjs/common';
import request from 'supertest';
import { App } from 'supertest/types';
import { JwtService } from '@nestjs/jwt';
import { DataSource } from 'typeorm';
import { AppModule } from '../src/app.module';
import { ChatSession } from '../src/chat/entities/chat-session.entity';

describe('Chat API (e2e)', () => {
  let app: INestApplication<App>;
  let jwtService: JwtService;
  let dataSource: DataSource;
  let validAccessToken: string;
  let otherUserToken: string;
  const testUserId = 'test-user-id';
  const otherUserId = 'other-user-id';

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    app.useGlobalPipes(new ValidationPipe({ whitelist: true }));
    await app.init();

    jwtService = moduleFixture.get<JwtService>(JwtService);
    dataSource = moduleFixture.get<DataSource>(DataSource);

    // Generate valid tokens for testing
    validAccessToken = jwtService.sign(
      { sub: testUserId, email: 'test@example.com', name: 'Test User' },
      { expiresIn: '15m' },
    );

    otherUserToken = jwtService.sign(
      { sub: otherUserId, email: 'other@example.com', name: 'Other User' },
      { expiresIn: '15m' },
    );
  });

  afterAll(async () => {
    // Clean up test data
    if (dataSource?.isInitialized) {
      await dataSource
        .getRepository(ChatSession)
        .delete({ usersId: testUserId });
      await dataSource
        .getRepository(ChatSession)
        .delete({ usersId: otherUserId });
    }
    await app.close();
  });

  describe('POST /chat/sessions', () => {
    it('[P1] should create chat session for authenticated user', async () => {
      // GIVEN: Valid access token and session data
      const createDto = { title: 'Test Session', modelName: 'gpt-4' };

      // WHEN: Creating a session
      const response = await request(app.getHttpServer())
        .post('/chat/sessions')
        .set('Authorization', `Bearer ${validAccessToken}`)
        .send(createDto);

      // THEN: Returns 201 with created session
      expect(response.status).toBe(201);
      expect(response.body).toHaveProperty('data');
      expect(response.body.data).toHaveProperty('id');
      expect(response.body.data).toHaveProperty('title', 'Test Session');
      expect(response.body.data).toHaveProperty('modelName', 'gpt-4');
      expect(response.body.data).toHaveProperty('userId', testUserId);
    });

    it('[P1] should return 401 for unauthenticated request', async () => {
      // GIVEN: No authentication
      const createDto = { title: 'Test Session', modelName: 'gpt-4' };

      // WHEN: Attempting to create session
      const response = await request(app.getHttpServer())
        .post('/chat/sessions')
        .send(createDto);

      // THEN: Returns 401 Unauthorized
      expect(response.status).toBe(401);
    });
  });

  describe('GET /chat/sessions', () => {
    it('[P1] should return user sessions for authenticated user', async () => {
      // GIVEN: Authenticated user with sessions
      // WHEN: Getting sessions
      const response = await request(app.getHttpServer())
        .get('/chat/sessions')
        .set('Authorization', `Bearer ${validAccessToken}`);

      // THEN: Returns 200 with session list
      expect(response.status).toBe(200);
      expect(response.body).toHaveProperty('data');
      expect(Array.isArray(response.body.data)).toBe(true);
    });

    it('[P1] should return 401 for unauthenticated request', async () => {
      // GIVEN: No authentication
      // WHEN: Getting sessions
      const response = await request(app.getHttpServer()).get('/chat/sessions');

      // THEN: Returns 401 Unauthorized
      expect(response.status).toBe(401);
    });

    it('[P2] should only return sessions owned by user', async () => {
      // GIVEN: User A creates a session
      const createDto = { title: 'User A Session', modelName: 'gpt-4' };
      await request(app.getHttpServer())
        .post('/chat/sessions')
        .set('Authorization', `Bearer ${validAccessToken}`)
        .send(createDto);

      // WHEN: User B gets their sessions
      const response = await request(app.getHttpServer())
        .get('/chat/sessions')
        .set('Authorization', `Bearer ${otherUserToken}`);

      // THEN: Should not include User A's session
      expect(response.status).toBe(200);
      const sessionTitles = response.body.data.map(
        (s: { title: string }) => s.title,
      );
      expect(sessionTitles).not.toContain('User A Session');
    });
  });

  describe('GET /chat/sessions/:sessionId', () => {
    let testSessionId: string;

    beforeAll(async () => {
      // Create a test session
      const createDto = { title: 'Get Test Session', modelName: 'gpt-4' };
      const response = await request(app.getHttpServer())
        .post('/chat/sessions')
        .set('Authorization', `Bearer ${validAccessToken}`)
        .send(createDto);
      testSessionId = response.body.data.id;
    });

    it('[P1] should return session for owner', async () => {
      // GIVEN: Session owned by user
      // WHEN: Getting session
      const response = await request(app.getHttpServer())
        .get(`/chat/sessions/${testSessionId}`)
        .set('Authorization', `Bearer ${validAccessToken}`);

      // THEN: Returns 200 with session
      expect(response.status).toBe(200);
      expect(response.body.data).toHaveProperty('id', testSessionId);
    });

    it('[P1] should return 404 for non-owner', async () => {
      // GIVEN: Session owned by different user
      // WHEN: Other user tries to get session
      const response = await request(app.getHttpServer())
        .get(`/chat/sessions/${testSessionId}`)
        .set('Authorization', `Bearer ${otherUserToken}`);

      // THEN: Returns 404 Not Found
      expect(response.status).toBe(404);
    });

    it('[P1] should return 404 for non-existent session', async () => {
      // GIVEN: Invalid session ID
      const fakeId = '00000000-0000-0000-0000-000000000000';

      // WHEN: Getting non-existent session
      const response = await request(app.getHttpServer())
        .get(`/chat/sessions/${fakeId}`)
        .set('Authorization', `Bearer ${validAccessToken}`);

      // THEN: Returns 404 Not Found
      expect(response.status).toBe(404);
    });
  });

  describe('DELETE /chat/sessions/:sessionId', () => {
    let deleteSessionId: string;

    beforeEach(async () => {
      // Create a session to delete
      const createDto = { title: 'Delete Test Session', modelName: 'gpt-4' };
      const response = await request(app.getHttpServer())
        .post('/chat/sessions')
        .set('Authorization', `Bearer ${validAccessToken}`)
        .send(createDto);
      deleteSessionId = response.body.data.id;
    });

    it('[P1] should delete session for owner', async () => {
      // GIVEN: Session owned by user
      // WHEN: Deleting session
      const response = await request(app.getHttpServer())
        .delete(`/chat/sessions/${deleteSessionId}`)
        .set('Authorization', `Bearer ${validAccessToken}`);

      // THEN: Returns 200 with success message
      expect(response.status).toBe(200);
      expect(response.body.data).toHaveProperty(
        'message',
        'Chat session deleted',
      );

      // THEN: Session no longer exists
      const getResponse = await request(app.getHttpServer())
        .get(`/chat/sessions/${deleteSessionId}`)
        .set('Authorization', `Bearer ${validAccessToken}`);
      expect(getResponse.status).toBe(404);
    });

    it('[P1] should return 404 for non-owner', async () => {
      // GIVEN: Session owned by different user
      // WHEN: Other user tries to delete session
      const response = await request(app.getHttpServer())
        .delete(`/chat/sessions/${deleteSessionId}`)
        .set('Authorization', `Bearer ${otherUserToken}`);

      // THEN: Returns 404 Not Found
      expect(response.status).toBe(404);
    });

    it('[P1] should return 401 for unauthenticated request', async () => {
      // GIVEN: No authentication
      // WHEN: Attempting to delete session
      const response = await request(app.getHttpServer()).delete(
        `/chat/sessions/${deleteSessionId}`,
      );

      // THEN: Returns 401 Unauthorized
      expect(response.status).toBe(401);
    });
  });

  describe('GET /chat/sessions/:sessionId/interactions', () => {
    let interactionSessionId: string;

    beforeAll(async () => {
      // Create a test session for interactions
      const createDto = {
        title: 'Interaction Test Session',
        modelName: 'gpt-4',
      };
      const response = await request(app.getHttpServer())
        .post('/chat/sessions')
        .set('Authorization', `Bearer ${validAccessToken}`)
        .send(createDto);
      interactionSessionId = response.body.data.id;
    });

    it('[P2] should return empty array for session with no interactions', async () => {
      // GIVEN: Session with no interactions
      // WHEN: Getting interactions
      const response = await request(app.getHttpServer())
        .get(`/chat/sessions/${interactionSessionId}/interactions`)
        .set('Authorization', `Bearer ${validAccessToken}`);

      // THEN: Returns 200 with empty array
      expect(response.status).toBe(200);
      expect(response.body.data).toEqual([]);
    });

    it('[P1] should return 404 for non-owner', async () => {
      // GIVEN: Session owned by different user
      // WHEN: Other user tries to get interactions
      const response = await request(app.getHttpServer())
        .get(`/chat/sessions/${interactionSessionId}/interactions`)
        .set('Authorization', `Bearer ${otherUserToken}`);

      // THEN: Returns 404 Not Found
      expect(response.status).toBe(404);
    });
  });
});
