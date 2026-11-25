import { registerAs } from '@nestjs/config';
import { randomUUID } from 'crypto';
import { IncomingMessage } from 'http';
import * as path from 'path';
import type { Params } from 'nestjs-pino';

export default registerAs('logger', () => {
  const isProduction = process.env.NODE_ENV === 'production';
  const logLevel = process.env.LOG_LEVEL || (isProduction ? 'info' : 'debug');
  const logDir = process.env.LOG_DIR || './logs';

  return { isProduction, logLevel, logDir };
});

export function createLoggerConfig(
  isProduction: boolean,
  logLevel: string,
  logDir: string,
): Params {
  const transportPath = path.join(__dirname, 'log-custom-transport');

  return {
    pinoHttp: {
      level: logLevel,
      transport: {
        target: transportPath,
        options: { logDir },
      },
      genReqId: (req: IncomingMessage) =>
        (req.headers['x-correlation-id'] as string) || randomUUID(),
      autoLogging: false, // AccessLogInterceptor가 대체
      serializers: {
        req: (req: Record<string, unknown>) => ({
          id: req.id,
          method: req.method,
          url: req.url,
          remoteAddress: req.remoteAddress,
        }),
        res: (res: Record<string, unknown>) => ({
          statusCode: res.statusCode,
        }),
      },
      customProps: () => ({
        service: 'backend',
      }),
    },
  };
}
