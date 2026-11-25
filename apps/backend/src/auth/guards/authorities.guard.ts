import {
  Injectable,
  CanActivate,
  ExecutionContext,
  ForbiddenException,
} from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { AUTHORITIES_KEY } from '../decorators/authorities.decorator';
import { AuthorityType } from '../../common/enums';

const AUTHORITY_ERROR_MESSAGES: Record<string, string> = {
  [AuthorityType.ADMIN]: '관리자 권한이 필요합니다',
  [AuthorityType.UPLOADER]: '업로드 권한이 없습니다',
};

@Injectable()
export class AuthoritiesGuard implements CanActivate {
  constructor(private reflector: Reflector) {}

  canActivate(context: ExecutionContext): boolean {
    const requiredAuthorities = this.reflector.getAllAndOverride<
      AuthorityType[]
    >(AUTHORITIES_KEY, [context.getHandler(), context.getClass()]);

    if (!requiredAuthorities || requiredAuthorities.length === 0) {
      return true;
    }

    const { user } = context.switchToHttp().getRequest();

    if (!user || !user.authorities) {
      throw new ForbiddenException('권한 정보가 없습니다');
    }

    // ADMIN 권한은 모든 API 접근 허용
    if (user.authorities.includes(AuthorityType.ADMIN)) {
      return true;
    }

    const hasAuthority = requiredAuthorities.some((auth) =>
      user.authorities.includes(auth),
    );

    if (!hasAuthority) {
      const message =
        AUTHORITY_ERROR_MESSAGES[requiredAuthorities[0]] ?? '권한이 부족합니다';
      throw new ForbiddenException(message);
    }

    return true;
  }
}
