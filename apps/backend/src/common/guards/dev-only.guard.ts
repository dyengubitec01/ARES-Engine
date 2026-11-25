import {
  Injectable,
  CanActivate,
  ExecutionContext,
  NotFoundException,
} from '@nestjs/common';

/**
 * 개발 전용 엔드포인트 가드.
 * NODE_ENV === 'production' 환경에서는 404 로 위장해 차단.
 * (FORBIDDEN 대신 NOT FOUND 로 응답해 엔드포인트 존재 자체를 노출하지 않음)
 */
@Injectable()
export class DevOnlyGuard implements CanActivate {
  canActivate(_context: ExecutionContext): boolean {
    if (process.env.NODE_ENV === 'production') {
      throw new NotFoundException();
    }
    return true;
  }
}
