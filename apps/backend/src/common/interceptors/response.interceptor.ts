import {
  Injectable,
  NestInterceptor,
  ExecutionContext,
  CallHandler,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';
import {
  RESPONSE_CODE_KEY,
  RESPONSE_MESSAGE_KEY,
} from '../decorators/response-code.decorator';
import { SSE_KEY } from '../decorators/sse.decorator';
import { ResponseCode, getResponseMessage } from '../constants/response-codes';

export interface ApiResponse<T> {
  success: boolean;
  code: string;
  message: string;
  data: T;
}

@Injectable()
export class ResponseInterceptor<T> implements NestInterceptor<
  T,
  ApiResponse<T>
> {
  constructor(private reflector: Reflector) {}

  intercept(
    context: ExecutionContext,
    next: CallHandler,
  ): Observable<ApiResponse<T>> {
    // Check if this is an SSE endpoint - skip wrapping for SSE
    const isSse = this.reflector.get(SSE_KEY, context.getHandler());
    if (isSse) {
      return next.handle();
    }

    // Get response code and message from decorator metadata
    const code = this.reflector.get<string>(
      RESPONSE_CODE_KEY,
      context.getHandler(),
    );
    const customMessage = this.reflector.get<string>(
      RESPONSE_MESSAGE_KEY,
      context.getHandler(),
    );

    return next.handle().pipe(
      map((data) => {
        // Determine the response code
        const responseCode = code || ResponseCode.UNKNOWN;

        // Determine the message (priority: custom > data.message > ResponseMessage mapping)
        let message = customMessage;
        if (!message && data && typeof data === 'object' && 'message' in data) {
          message = data.message as string;
        }
        if (!message) {
          message = getResponseMessage(responseCode as any);
        }

        // Extract actual data (handle both { data: ... } and raw data formats)
        let responseData: T;
        if (data && typeof data === 'object' && 'data' in data) {
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          const { data: innerData, message: _msg, ...rest } = data;
          responseData = (
            Object.keys(rest).length > 0
              ? { data: innerData, ...rest }
              : innerData
          ) as T;
        } else {
          responseData = data;
        }

        return {
          success: true,
          code: responseCode,
          message,
          data: responseData,
        };
      }),
    );
  }
}
