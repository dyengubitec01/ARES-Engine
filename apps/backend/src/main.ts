import 'dotenv/config';
import { NestFactory } from '@nestjs/core';
import { ValidationPipe, Logger } from '@nestjs/common';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import { Logger as PinoLogger } from 'nestjs-pino';
import cookieParser from 'cookie-parser';
import { AppModule } from './app.module';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, { bufferLogs: true });
  app.useLogger(app.get(PinoLogger));
  const logger = new Logger('Bootstrap');

  // Set global API prefix
  app.setGlobalPrefix('api');

  // Enable cookie parsing for httpOnly JWT tokens
  app.use(cookieParser());

  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
    }),
  );

  app.enableCors({
    origin: process.env.CORS_ORIGIN?.split(',').map((o) => o.trim()) || [],
    credentials: true,
  });

  const config = new DocumentBuilder()
    .setTitle('Backend API')
    .setDescription('AI Gateway Backend API Documentation')
    .setVersion('1.0')
    .addBearerAuth()
    .addCookieAuth('access_token')
    .build();

  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('api/api-docs', app, document, {
    swaggerOptions: {
      withCredentials: true,
    },
  });

  // Kafka consumer는 KafkaModule의 EmbeddingStatusConsumer에서 직접 관리

  const port = process.env.PORT ?? 3000;
  await app.listen(port, '0.0.0.0');

  logger.log(`Application listening on port ${port} (0.0.0.0)`);
  logger.log(`Swagger docs: http://localhost:${port}/api/api-docs`);
}
bootstrap();
