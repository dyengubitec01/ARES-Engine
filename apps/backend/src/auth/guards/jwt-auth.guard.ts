import { Injectable, ExecutionContext } from '@nestjs/common';
import { AuthGuard } from '@nestjs/passport';
import { Reflector } from '@nestjs/core';
import { IS_PUBLIC_KEY } from '../decorators/public.decorator';
import { RedisService } from '../../external/redis/redis.service';
import { AuthService } from '../auth.service';
import * as express from 'express';

@Injectable()
export class JwtAuthGuard extends AuthGuard('jwt') {
  constructor(
    private reflector: Reflector,
    private redisService: RedisService,
    private authService: AuthService,
  ) {
    super();
  }

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const isPublic = this.reflector.getAllAndOverride<boolean>(IS_PUBLIC_KEY, [
      context.getHandler(),
      context.getClass(),
    ]);

    if (isPublic) {
      return true;
    }

    // 기존 JWT 검증 수행
    const result = await (super.canActivate(context) as Promise<boolean>);
    if (!result) {
      return false;
    }

    // Redis 토큰 갱신 플래그 체크
    const request = context.switchToHttp().getRequest<express.Request>();
    const user = request.user as { userId: string } | undefined;

    if (user?.userId) {
      const needsRefresh = await this.redisService.getTokenRefreshFlag(
        user.userId,
      );

      if (needsRefresh) {
        const tokens = await this.authService.regenerateTokens(user.userId);

        if (tokens) {
          const response = context
            .switchToHttp()
            .getResponse<express.Response>();
          this.authService.setTokenCookies(request, response, tokens);

          // 새 토큰의 payload로 req.user 갱신
          const newPayload = this.authService.decodeToken(tokens.accessToken);
          if (newPayload) {
            request.user = {
              userId: newPayload.sub,
              email: newPayload.email,
              name: newPayload.name,
              authorities: newPayload.authorities,
              jobTitle: newPayload.jobTitle,
              department: newPayload.department,
              authDeptId: newPayload.authDeptId,
              deptPermissions: newPayload.deptPermissions,
            };
          }
        }

        await this.redisService.deleteTokenRefreshFlag(user.userId);
      }
    }

    return true;
  }
}
