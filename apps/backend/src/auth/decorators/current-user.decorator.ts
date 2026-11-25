import { createParamDecorator, ExecutionContext } from '@nestjs/common';
import type { AuthenticatedUser } from '../types/authenticated-user';

/**
 * @CurrentUser() — JwtAuthGuard 통과 후 req.user 에 박힌 AuthenticatedUser 를 그대로 꺼내는 데코레이터.
 * 컨트롤러 핸들러에서 inline 타입 정의 없이 사용.
 *
 * @example
 *   async findDocuments(@CurrentUser() user: AuthenticatedUser) { ... }
 */
export const CurrentUser = createParamDecorator(
  (_data: unknown, ctx: ExecutionContext): AuthenticatedUser => {
    const request = ctx.switchToHttp().getRequest();
    return request.user as AuthenticatedUser;
  },
);
