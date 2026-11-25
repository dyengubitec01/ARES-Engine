import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { DocDocumentContent } from '../../document/entities/doc-document-content.entity';
import { ChatInteraction } from './chat-interaction.entity';

/**
 * 해당 답변에 어떤 문서(버전)들이 참조 되었는지 기록
 */
@Entity('chat_document_reference')
export class ChatDocumentReference {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Index('idx_chat_document_reference_doc_content_id')
  @Column({ name: 'document_content_id', type: 'uuid' })
  documentContentId: string;

  @Index('idx_chat_document_reference_chat_interaction_id')
  @Column({ name: 'chat_interaction_id', type: 'uuid' })
  chatInteractionId: string;

  @Column({ name: 'relevance', type: 'float', nullable: true })
  relevance: number | null;

  @Column({ name: 'location', type: 'varchar', length: 255, nullable: true })
  location: string | null;

  @CreateDateColumn({ name: 'created_at', type: 'timestamptz' })
  createdAt: Date;

  // Relations
  @ManyToOne(
    () => DocDocumentContent,
    (content) => content.chatDocumentReferences,
    {
      onDelete: 'CASCADE',
    },
  )
  @JoinColumn({ name: 'document_content_id' })
  docContent: DocDocumentContent;

  @ManyToOne(
    () => ChatInteraction,
    (interaction) => interaction.documentReferences,
    { onDelete: 'CASCADE' },
  )
  @JoinColumn({ name: 'chat_interaction_id' })
  interaction: ChatInteraction;
}
