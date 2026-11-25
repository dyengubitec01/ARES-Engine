import { Test, TestingModule } from '@nestjs/testing';
import { getRepositoryToken } from '@nestjs/typeorm';
import { NotFoundException, ForbiddenException } from '@nestjs/common';
import { ChatService } from './chat.service';
import { ChatSession } from './entities/chat-session.entity';
import { ChatInteraction } from './entities/chat-interaction.entity';
import { ChatDocumentReference } from './entities/chat-document-reference.entity';
import { AuthUser } from '../auth/entities/auth-user.entity';
import { DocDocumentExclude } from '../document/entities/doc-document-exclude.entity';
import { RedisService } from '../external/redis/redis.service';
import { ToolsService } from '../external/tools/tools.service';

describe('ChatService', () => {
  let service: ChatService;

  // DDL: chat_session (id, title, favorites, users_id, created_at)
  const mockSession: Partial<ChatSession> = {
    id: 'session-123',
    title: null,
    usersId: 'user-123',
    favorites: 'N',
    createdAt: new Date(),
  };

  // DDL: chat_interaction (id, type, content, chat_turn, feedback, session_id, created_at)
  const mockInteraction: Partial<ChatInteraction> = {
    id: 'interaction-123',
    sessionId: 'session-123',
    type: 'Q',
    content: 'Hello',
    chatTurn: 1,
    feedback: 'N',
    createdAt: new Date(),
  };

  // DDL: chat_document_reference (id, document_content_id, chat_interaction_id, relevance, created_at)
  const mockDocRef: Partial<ChatDocumentReference> = {
    id: 'ref-123',
    documentContentId: 'doc-123',
    chatInteractionId: 'interaction-123',
    relevance: 0.95,
    createdAt: new Date(),
  };

  const mockSessionRepository = {
    create: jest.fn(),
    save: jest.fn(),
    find: jest.fn(),
    findOne: jest.fn(),
    remove: jest.fn(),
    createQueryBuilder: jest.fn(),
  };

  const mockInteractionRepository = {
    create: jest.fn(),
    save: jest.fn(),
    find: jest.fn(),
    findOne: jest.fn(),
    createQueryBuilder: jest.fn(),
  };

  const mockDocumentRefRepository = {
    create: jest.fn(),
    save: jest.fn(),
    find: jest.fn(),
    findOne: jest.fn(),
    remove: jest.fn(),
  };

  const mockAuthUserRepository = {
    findOne: jest.fn(),
  };

  const mockRedisService = {
    getSessionSummary: jest.fn(),
    deleteSessionSummary: jest.fn(),
    healthCheck: jest.fn(),
  };

  const mockToolsService = {
    summarizeHistory: jest.fn(),
    healthCheck: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        ChatService,
        {
          provide: getRepositoryToken(ChatSession),
          useValue: mockSessionRepository,
        },
        {
          provide: getRepositoryToken(ChatInteraction),
          useValue: mockInteractionRepository,
        },
        {
          provide: getRepositoryToken(ChatDocumentReference),
          useValue: mockDocumentRefRepository,
        },
        {
          provide: getRepositoryToken(AuthUser),
          useValue: mockAuthUserRepository,
        },
        {
          provide: getRepositoryToken(DocDocumentExclude),
          useValue: {},
        },
        {
          provide: RedisService,
          useValue: mockRedisService,
        },
        {
          provide: ToolsService,
          useValue: mockToolsService,
        },
      ],
    }).compile();

    service = module.get<ChatService>(ChatService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  // ============================================================
  // Story 2.10: Redis Context Cache Tests
  // ============================================================

  describe('getSessionContext', () => {
    it('[AC1] should return summary from Redis cache when hit', async () => {
      // GIVEN: Redis has cached summary
      const sessionId = 'session-123';
      const cachedSummary = '이전 대화 요약본입니다.';
      mockRedisService.getSessionSummary.mockResolvedValue(cachedSummary);

      // WHEN: Getting session context
      const result = await service.getSessionContext(sessionId);

      // THEN: Returns cached summary with source 'redis'
      expect(result).toEqual({
        summary: cachedSummary,
        isFirstQuestion: false,
        source: 'redis',
      });
      expect(mockRedisService.getSessionSummary).toHaveBeenCalledWith(
        sessionId,
      );
      expect(mockInteractionRepository.find).not.toHaveBeenCalled();
      expect(mockToolsService.summarizeHistory).not.toHaveBeenCalled();
    });

    it('[AC2] should call Tools API when cache miss + history exists', async () => {
      // GIVEN: Redis cache miss, but RDB has history
      const sessionId = 'session-123';
      const history = [
        { id: '1', type: 'Q', content: '안녕', chatTurn: 1 },
        { id: '2', type: 'A', content: '안녕하세요!', chatTurn: 1 },
      ];
      const toolsSummary = 'Tools가 생성한 요약본입니다.';

      mockRedisService.getSessionSummary.mockResolvedValue(null);
      mockInteractionRepository.find.mockResolvedValue(history);
      mockToolsService.summarizeHistory.mockResolvedValue(toolsSummary);

      // WHEN: Getting session context
      const result = await service.getSessionContext(sessionId);

      // THEN: Returns Tools summary with source 'tools'
      expect(result).toEqual({
        summary: toolsSummary,
        isFirstQuestion: false,
        source: 'tools',
      });
      expect(mockRedisService.getSessionSummary).toHaveBeenCalledWith(
        sessionId,
      );
      expect(mockInteractionRepository.find).toHaveBeenCalledWith({
        where: { sessionId },
        order: { chatTurn: 'ASC', createdAt: 'ASC' },
      });
      expect(mockToolsService.summarizeHistory).toHaveBeenCalledWith(
        sessionId,
        [
          { type: 'Q', content: '안녕', chatTurn: 1 },
          { type: 'A', content: '안녕하세요!', chatTurn: 1 },
        ],
      );
    });

    it('[AC3] should skip Tools API when cache miss + no history (first question)', async () => {
      // GIVEN: Redis cache miss and RDB has no history
      const sessionId = 'session-new';

      mockRedisService.getSessionSummary.mockResolvedValue(null);
      mockInteractionRepository.find.mockResolvedValue([]);

      // WHEN: Getting session context
      const result = await service.getSessionContext(sessionId);

      // THEN: Returns null summary with isFirstQuestion true
      expect(result).toEqual({
        summary: null,
        isFirstQuestion: true,
        source: 'none',
      });
      expect(mockRedisService.getSessionSummary).toHaveBeenCalledWith(
        sessionId,
      );
      expect(mockInteractionRepository.find).toHaveBeenCalled();
      expect(mockToolsService.summarizeHistory).not.toHaveBeenCalled();
    });
  });

  describe('deleteSession', () => {
    it('[AC4] should delete Redis cache when deleting session', async () => {
      // GIVEN: User owns the session
      const usersId = 'user-123';
      const sessionId = 'session-123';
      mockSessionRepository.findOne.mockResolvedValue({
        ...mockSession,
        usersId,
      });
      mockSessionRepository.remove.mockResolvedValue(undefined);
      mockRedisService.deleteSessionSummary.mockResolvedValue(true);

      // WHEN: Deleting session
      const result = await service.deleteSession(usersId, sessionId);

      // THEN: Redis cache is deleted and returns success message
      expect(mockRedisService.deleteSessionSummary).toHaveBeenCalledWith(
        sessionId,
      );
      expect(mockSessionRepository.remove).toHaveBeenCalled();
      expect(result).toEqual({ message: '채팅방이 삭제되었습니다' });
    });

    it('[P1] should throw NotFoundException when session not found', async () => {
      // GIVEN: Session does not exist
      const usersId = 'user-123';
      const sessionId = 'non-existent';
      mockSessionRepository.findOne.mockResolvedValue(null);

      // WHEN/THEN: Throws NotFoundException
      await expect(service.deleteSession(usersId, sessionId)).rejects.toThrow(
        NotFoundException,
      );
      expect(mockRedisService.deleteSessionSummary).not.toHaveBeenCalled();
    });

    it('[P1] should throw ForbiddenException when user is not owner', async () => {
      // GIVEN: Session belongs to another user
      const usersId = 'other-user';
      const sessionId = 'session-123';
      mockSessionRepository.findOne.mockResolvedValue(mockSession);

      // WHEN/THEN: Throws ForbiddenException
      await expect(service.deleteSession(usersId, sessionId)).rejects.toThrow(
        ForbiddenException,
      );
      expect(mockRedisService.deleteSessionSummary).not.toHaveBeenCalled();
    });
  });

  // ============================================================
  // Existing Tests (Updated)
  // ============================================================

  describe('createSession', () => {
    it('[P1] should create and return a new chat session', async () => {
      // GIVEN: Valid user and session data
      const usersId = 'user-123';
      const dto = { favorites: 'N' };
      const mockUser = {
        id: usersId,
        name: '홍길동',
        authDept: { deptName: '기술연구소' },
      };
      mockAuthUserRepository.findOne.mockResolvedValue(mockUser);
      mockSessionRepository.create.mockReturnValue(mockSession);
      mockSessionRepository.save.mockResolvedValue(mockSession);

      // WHEN: Creating a session
      const result = await service.createSession(usersId, dto);

      // THEN: Returns created session with user info
      expect(result).toEqual({
        id: mockSession.id,
        title: mockSession.title,
        userName: '홍길동',
        userDept: '기술연구소',
        createdAt: mockSession.createdAt,
      });
      expect(mockSessionRepository.create).toHaveBeenCalledWith({
        usersId,
        favorites: 'N',
      });
      expect(mockSessionRepository.save).toHaveBeenCalled();
    });
  });

  describe('getSession', () => {
    it('[P1] should return session for valid id', async () => {
      // GIVEN: Valid session exists
      const usersId = 'user-123';
      const sessionId = 'session-123';
      mockSessionRepository.findOne.mockResolvedValue(mockSession);

      // WHEN: Getting session
      const result = await service.getSession(usersId, sessionId);

      // THEN: Returns session
      expect(result).toEqual(mockSession);
      expect(mockSessionRepository.findOne).toHaveBeenCalledWith({
        where: { id: sessionId, usersId },
      });
    });

    it('[P1] should throw NotFoundException for invalid session id', async () => {
      // GIVEN: Session does not exist
      const usersId = 'user-123';
      const sessionId = 'invalid-session';
      mockSessionRepository.findOne.mockResolvedValue(null);

      // WHEN/THEN: Throws NotFoundException
      await expect(service.getSession(usersId, sessionId)).rejects.toThrow(
        NotFoundException,
      );
    });
  });

  describe('getInteractions', () => {
    it('[P2] should return interactions for valid session ordered by chatTurn and createdAt', async () => {
      // GIVEN: Valid session with interactions
      const usersId = 'user-123';
      const sessionId = 'session-123';
      const interactions = [mockInteraction];
      mockSessionRepository.findOne.mockResolvedValue(mockSession);
      mockInteractionRepository.find.mockResolvedValue(interactions);

      // WHEN: Getting interactions
      const result = await service.getInteractions(usersId, sessionId);

      // THEN: Returns interactions ordered by chatTurn ASC, createdAt ASC
      expect(result).toEqual(interactions);
      expect(mockInteractionRepository.find).toHaveBeenCalledWith({
        where: { sessionId },
        order: { chatTurn: 'ASC', createdAt: 'ASC' },
      });
    });

    it('[P2] should throw NotFoundException for invalid session', async () => {
      // GIVEN: Session does not exist
      const usersId = 'user-123';
      const sessionId = 'invalid-session';
      mockSessionRepository.findOne.mockResolvedValue(null);

      // WHEN/THEN: Throws NotFoundException
      await expect(service.getInteractions(usersId, sessionId)).rejects.toThrow(
        NotFoundException,
      );
    });
  });

  describe('createInteraction', () => {
    it('[P2] should create and return interaction with auto chatTurn', async () => {
      // GIVEN: Valid interaction data, no previous interactions
      const sessionId = 'session-123';
      const dto = {
        type: 'Q' as const,
        content: 'Hello',
      };
      mockInteractionRepository.findOne.mockResolvedValue(null);
      mockInteractionRepository.create.mockReturnValue(mockInteraction);
      mockInteractionRepository.save.mockResolvedValue(mockInteraction);

      // WHEN: Creating interaction
      const result = await service.createInteraction(sessionId, dto);

      // THEN: Returns created interaction
      expect(result).toEqual(mockInteraction);
      expect(mockInteractionRepository.create).toHaveBeenCalledWith({
        sessionId,
        type: 'Q',
        content: 'Hello',
        chatTurn: 1,
      });
    });
  });

  describe('addDocumentReference', () => {
    it('[P2] should create new document reference', async () => {
      // GIVEN: No existing reference
      const chatInteractionId = 'interaction-123';
      const documentId = 'doc-123';
      mockDocumentRefRepository.findOne.mockResolvedValue(null);
      mockDocumentRefRepository.create.mockReturnValue(mockDocRef);
      mockDocumentRefRepository.save.mockResolvedValue(mockDocRef);

      // WHEN: Adding document reference
      const result = await service.addDocumentReference(
        chatInteractionId,
        documentId,
      );

      // THEN: Returns created reference
      expect(result).toEqual(mockDocRef);
      expect(mockDocumentRefRepository.create).toHaveBeenCalledWith({
        chatInteractionId,
        documentId,
        relevance: null,
      });
      expect(mockDocumentRefRepository.save).toHaveBeenCalled();
    });

    it('[P2] should return existing document reference', async () => {
      // GIVEN: Reference already exists
      const chatInteractionId = 'interaction-123';
      const documentId = 'doc-123';
      mockDocumentRefRepository.findOne.mockResolvedValue(mockDocRef);

      // WHEN: Adding document reference
      const result = await service.addDocumentReference(
        chatInteractionId,
        documentId,
      );

      // THEN: Returns existing reference without creating new
      expect(result).toEqual(mockDocRef);
      expect(mockDocumentRefRepository.create).not.toHaveBeenCalled();
    });
  });
});
