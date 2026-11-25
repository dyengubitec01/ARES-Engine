import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { ChatController } from './chat.controller';
import { ChatService } from './chat.service';
import { ChatSession } from './entities/chat-session.entity';
import { ChatInteraction } from './entities/chat-interaction.entity';
import { ChatDocumentReference } from './entities/chat-document-reference.entity';
import { AuthUser } from '../auth/entities/auth-user.entity';
import { DocDocumentExclude } from '../document/entities/doc-document-exclude.entity';
import { DocDocumentContent } from '../document/entities/doc-document-content.entity';
import { ChatbotModule } from '../external/chatbot/chatbot.module';
import { ToolsModule } from '../external/tools/tools.module';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      ChatSession,
      ChatInteraction,
      ChatDocumentReference,
      AuthUser,
      DocDocumentExclude,
      DocDocumentContent,
    ]),
    ChatbotModule,
    ToolsModule,
  ],
  controllers: [ChatController],
  providers: [ChatService],
  exports: [ChatService],
})
export class ChatModule {}
