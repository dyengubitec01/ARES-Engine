import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
  Inject,
  Optional,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { Observable } from 'rxjs';
import { tap, finalize } from 'rxjs/operators';
import { Request, Response } from 'express';
import { SSE_KEY } from '../decorators/sse.decorator';
import { LogFileRotator } from '../../config/log-file-rotator';

/** Fields to mask in request/response body */
const SENSITIVE_FIELDS = [
  'password',
  'token',
  'secret',
  'authorization',
  'cookie',
  'accesstoken',
  'refreshtoken',
];

const MAX_BODY_LENGTH = 100;

export const LOG_FILE_ROTATOR = 'LOG_FILE_ROTATOR';

@Injectable()
export class AccessLogInterceptor implements NestInterceptor {
  constructor(
    private reflector: Reflector,
    @Optional() @Inject(LOG_FILE_ROTATOR) private rotator?: LogFileRotator,
  ) {}

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const ctx = context.switchToHttp();
    const req = ctx.getRequest<Request>();
    const res = ctx.getResponse<Response>();
    const start = Date.now();

    const controller = context.getClass().name;
    const handler = context.getHandler().name;

    // SSE endpoints: track first/last event and chunk count
    const isSse = this.reflector.get(SSE_KEY, context.getHandler());
    if (isSse) {
      let chunks = 0;
      let firstEvent: string | undefined;
      let lastEvent: string | undefined;
      let content = '';

      return next.handle().pipe(
        tap((event: any) => {
          chunks++;
          const type = event?.type || event?.event;
          if (type) {
            if (!firstEvent) firstEvent = type;
            lastEvent = type;
          }
          // Collect message content for log preview
          if (type === 'message' && event?.data) {
            try {
              const parsed = JSON.parse(event.data);
              if (parsed?.content) content += parsed.content;
            } catch {
              // skip unparseable data
            }
          }
        }),
        finalize(() => {
          const preview = content
            ? content.length > MAX_BODY_LENGTH
              ? content.substring(0, MAX_BODY_LENGTH) + '...'
              : content
            : '-';
          const summary = `[SSE | first: ${firstEvent || '-'} | last: ${lastEvent || '-'} | chunks: ${chunks} | content: ${preview}]`;
          this.writeLog(req, res, controller, handler, summary, start);
        }),
      );
    }

    // Normal endpoints: log once on complete or error
    let responseBody: unknown;
    return next.handle().pipe(
      tap({
        next: (body) => {
          responseBody = body;
        },
        error: (err) => {
          responseBody = {
            message:
              err instanceof Error ? err.message : 'Internal Server Error',
          };
        },
      }),
      finalize(() => {
        this.writeLog(req, res, controller, handler, responseBody, start);
      }),
    );
  }

  private writeLog(
    req: Request,
    res: Response,
    controller: string,
    handler: string,
    body: unknown,
    start: number,
  ): void {
    const date = this.formatDate(new Date());
    const userId = this.getUserId(req);
    const method = req.method;
    const url = req.originalUrl || req.url;
    const handlerName = `${controller}.${handler}`;
    const reqBody = this.formatBody(req.body);
    const resBody = this.formatBody(body, false);
    const status = res.statusCode;
    const duration = Date.now() - start;

    const log =
      `[SERVICE] backend | ` +
      `[DATE] ${date} | ` +
      `[USER] ${userId} | ` +
      `[METHOD] ${method} | ` +
      `[URL] ${url} | ` +
      `[HANDLER] ${handlerName} | ` +
      `[REQ] ${reqBody} | ` +
      `[RES] ${resBody} | ` +
      `[STATUS] ${status} | ` +
      `[TIME] ${duration}ms`;

    const line = log + '\n';
    process.stdout.write(line);
    this.rotator?.write(line);
  }

  private getUserId(req: Request): string {
    const user = req.user as { userId?: string } | undefined;
    return user?.userId || 'unauthenticated';
  }

  private formatDate(date: Date): string {
    const y = date.getFullYear();
    const M = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    const h = String(date.getHours()).padStart(2, '0');
    const m = String(date.getMinutes()).padStart(2, '0');
    const s = String(date.getSeconds()).padStart(2, '0');
    return `${y}-${M}-${d} ${h}:${m}:${s}`;
  }

  private formatBody(body: unknown, truncate = true): string {
    if (typeof body === 'string') {
      if (!truncate) return body;
      return body.length > MAX_BODY_LENGTH
        ? body.substring(0, MAX_BODY_LENGTH) + '...'
        : body;
    }
    if (!body || (typeof body === 'object' && Object.keys(body).length === 0)) {
      return '-';
    }

    try {
      const masked = this.maskSensitive(body);
      const str = JSON.stringify(masked);
      if (truncate && str.length > MAX_BODY_LENGTH) {
        return str.substring(0, MAX_BODY_LENGTH) + '...';
      }
      return str;
    } catch {
      return '-';
    }
  }

  private maskSensitive(obj: unknown): unknown {
    if (obj === null || obj === undefined) return obj;
    if (typeof obj !== 'object') return obj;
    if (Array.isArray(obj)) return obj.map((item) => this.maskSensitive(item));

    const masked: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      if (SENSITIVE_FIELDS.includes(key.toLowerCase())) {
        masked[key] = '***';
      } else if (typeof value === 'object' && value !== null) {
        masked[key] = this.maskSensitive(value);
      } else {
        masked[key] = value;
      }
    }
    return masked;
  }
}
