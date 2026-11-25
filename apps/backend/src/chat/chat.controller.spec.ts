import { Test, TestingModule } from '@nestjs/testing';
import { lastValueFrom, toArray } from 'rxjs';
import { ChatController } from './chat.controller';
import { ChatService } from './chat.service';
import {
  ChatbotService,
  ChatbotSseEvent,
} from '../external/chatbot/chatbot.service';
import {
  ResponseCode as RC,
  ResponseMessage,
} from '../common/constants/response-codes';

describe('ChatController', () => {
  let controller: ChatController;
  let chatService: jest.Mocked<ChatService>;
  let chatbotService: jest.Mocked<ChatbotService>;

  const mockUser = { user: { userId: 'user-123' } };
  const mockSessionId = 'session-uuid-123';

  beforeEach(async () => {
    const mockChatService = {
      getSession: jest.fn(),
      getInteractions: jest.fn(),
      createInteraction: jest.fn(),
    };

    const mockChatbotService = {
      sendMessage: jest.fn(),
      healthCheck: jest.fn(),
    };

    const module: TestingModule = await Test.createTestingModule({
      controllers: [ChatController],
      providers: [
        { provide: ChatService, useValue: mockChatService },
        { provide: ChatbotService, useValue: mockChatbotService },
      ],
    }).compile();

    controller = module.get<ChatController>(ChatController);
    chatService = module.get(ChatService);
    chatbotService = module.get(ChatbotService);
  });

  describe('sendPrompt SSE Events', () => {
    beforeEach(() => {
      // Default mocks for successful flow
      chatService.getSession.mockResolvedValue({
        id: mockSessionId,
        title: 'Test Session',
        favorites: 'N',
        createdAt: new Date(),
        usersId: mockUser.user.userId,
      } as any);
      chatService.getInteractions.mockResolvedValue([]);
      chatService.createInteraction.mockResolvedValue({
        id: 'interaction-123',
        type: 'Q',
        content: 'test',
        chatTurn: 1,
        createdAt: new Date(),
      } as any);
    });

    it('[AC5] should send connected event with BKN06100 at start', async () => {
      // GIVEN: Chatbot returns a simple response
      const mockGenerator =
        async function* (): AsyncGenerator<ChatbotSseEvent> {
          yield { event: 'message', content: 'Hello' };
        };
      chatbotService.sendMessage.mockReturnValue(mockGenerator());

      // WHEN: sendPrompt is called
      const observable = controller.sendPrompt(mockUser.user as any, { cookies: {} } as any, {
        sessionId: mockSessionId,
        prompt: 'test question',
      });

      const events = await lastValueFrom(observable.pipe(toArray()));

      // THEN: First event should be 'connected' with BKN06100
      expect(events.length).toBeGreaterThan(0);
      const connectedEvent = events[0];
      expect(connectedEvent.type).toBe('connected');

      const connectedData = JSON.parse(connectedEvent.data);
      expect(connectedData.code).toBe(RC.EVENT_SUBSCRIBE_SUCCESS);
      expect(connectedData.message).toBe(
        ResponseMessage[RC.EVENT_SUBSCRIBE_SUCCESS],
      );
      expect(connectedData.data.sessionId).toBe(mockSessionId);
    });

    it('[AC6] should send close event with BKN06101 and reason "completed" on success', async () => {
      // GIVEN: Chatbot returns a simple response
      const mockGenerator =
        async function* (): AsyncGenerator<ChatbotSseEvent> {
          yield { event: 'message', content: 'Hello' };
        };
      chatbotService.sendMessage.mockReturnValue(mockGenerator());

      // WHEN: sendPrompt is called
      const observable = controller.sendPrompt(mockUser.user as any, { cookies: {} } as any, {
        sessionId: mockSessionId,
        prompt: 'test question',
      });

      const events = await lastValueFrom(observable.pipe(toArray()));

      // THEN: Last event should be 'close' with BKN06101 and reason 'completed'
      const closeEvent = events[events.length - 1];
      expect(closeEvent.type).toBe('close');

      const closeData = JSON.parse(closeEvent.data);
      expect(closeData.code).toBe(RC.EVENT_CONNECTION_CLOSED);
      expect(closeData.message).toBe(
        ResponseMessage[RC.EVENT_CONNECTION_CLOSED],
      );
      expect(closeData.data.reason).toBe('completed');
    });

    it('[AC6] should send close event with reason "error" on failure', async () => {
      // GIVEN: Session validation fails
      chatService.getSession.mockRejectedValue(new Error('Session not found'));

      // WHEN: sendPrompt is called
      const observable = controller.sendPrompt(mockUser.user as any, { cookies: {} } as any, {
        sessionId: mockSessionId,
        prompt: 'test question',
      });

      // THEN: Should emit close event with error reason before erroring
      const events: any[] = [];
      try {
        await new Promise<void>((resolve, reject) => {
          observable.subscribe({
            next: (event) => events.push(event),
            error: () => reject(new Error('observable error')),
            complete: () => resolve(),
          });
        });
      } catch {
        // Error is expected
      }

      // Find close event with error reason
      const closeEvent = events.find((e) => e.type === 'close');
      expect(closeEvent).toBeDefined();

      const closeData = JSON.parse(closeEvent.data);
      expect(closeData.code).toBe(RC.EVENT_CONNECTION_CLOSED);
      expect(closeData.data.reason).toBe('error');
    });

    it('[AC7] should pass through message events from chatbot server', async () => {
      // GIVEN: Chatbot returns multiple chunks
      const mockGenerator =
        async function* (): AsyncGenerator<ChatbotSseEvent> {
          yield { event: 'message', content: 'Hello ' };
          yield { event: 'message', content: 'World' };
        };
      chatbotService.sendMessage.mockReturnValue(mockGenerator());

      // WHEN: sendPrompt is called
      const observable = controller.sendPrompt(mockUser.user as any, { cookies: {} } as any, {
        sessionId: mockSessionId,
        prompt: 'test question',
      });

      const events = await lastValueFrom(observable.pipe(toArray()));

      // THEN: Message events should be passed through with type 'message'
      const messageEvents = events.filter((e) => e.type === 'message');
      expect(messageEvents.length).toBe(3); // 2 chunks + 1 done event

      // Verify first chunk
      const firstChunk = JSON.parse(messageEvents[0].data);
      expect(firstChunk.content).toBe('Hello ');
      expect(firstChunk.references).toBeNull();

      // Verify second chunk
      const secondChunk = JSON.parse(messageEvents[1].data);
      expect(secondChunk.content).toBe('World');

      // Verify done event
      const doneEvent = JSON.parse(messageEvents[2].data);
      expect(doneEvent.done).toBe(true);
    });

    it('should emit events in correct order: connected -> messages -> close', async () => {
      // GIVEN: Chatbot returns a response
      const mockGenerator =
        async function* (): AsyncGenerator<ChatbotSseEvent> {
          yield { event: 'message', content: 'Test' };
        };
      chatbotService.sendMessage.mockReturnValue(mockGenerator());

      // WHEN: sendPrompt is called
      const observable = controller.sendPrompt(mockUser.user as any, { cookies: {} } as any, {
        sessionId: mockSessionId,
        prompt: 'test question',
      });

      const events = await lastValueFrom(observable.pipe(toArray()));

      // THEN: Events should be in correct order
      expect(events[0].type).toBe('connected');
      expect(events[events.length - 1].type).toBe('close');

      // All middle events should be 'message'
      const middleEvents = events.slice(1, -1);
      middleEvents.forEach((event) => {
        expect(event.type).toBe('message');
      });
    });

    it('should include sessionId in connected event data', async () => {
      // GIVEN: Chatbot returns a response
      const mockGenerator =
        async function* (): AsyncGenerator<ChatbotSseEvent> {
          yield { event: 'message', content: 'Test' };
        };
      chatbotService.sendMessage.mockReturnValue(mockGenerator());

      // WHEN: sendPrompt is called with specific sessionId
      const observable = controller.sendPrompt(mockUser.user as any, { cookies: {} } as any, {
        sessionId: 'my-session-id-456',
        prompt: 'test',
      });

      chatService.getSession.mockResolvedValue({
        id: 'my-session-id-456',
        title: 'Test',
        favorites: 'N',
        createdAt: new Date(),
        usersId: mockUser.user.userId,
      } as any);

      const events = await lastValueFrom(observable.pipe(toArray()));

      // THEN: Connected event should include the sessionId
      const connectedData = JSON.parse(events[0].data);
      expect(connectedData.data.sessionId).toBe('my-session-id-456');
    });
  });
});
