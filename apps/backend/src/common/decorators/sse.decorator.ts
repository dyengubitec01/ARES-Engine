import { applyDecorators, SetMetadata, Sse as NestSse } from '@nestjs/common';

export const SSE_KEY = 'sse';

/**
 * NestJS @Sse() + SetMetadata('sse', true)
 * ResponseInterceptor / AccessLogInterceptor에서 SSE 감지용
 */
export function Sse(path?: string): MethodDecorator {
  return applyDecorators(SetMetadata(SSE_KEY, true), NestSse(path));
}
