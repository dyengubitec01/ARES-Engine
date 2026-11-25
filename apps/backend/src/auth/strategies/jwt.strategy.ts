import { Injectable, UnauthorizedException } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy, StrategyOptionsWithRequest } from 'passport-jwt';
import { ConfigService } from '@nestjs/config';
import * as express from 'express';
import { JwtPayload } from '../auth.service';

// Cookie name for access token
const ACCESS_TOKEN_COOKIE = 'access_token';

/**
 * Custom extractor that reads JWT from httpOnly cookie
 * Falls back to Authorization header for API testing tools
 */
const cookieExtractor = (req: express.Request): string | null => {
  // First try to get from cookie
  const cookieToken = req?.cookies?.[ACCESS_TOKEN_COOKIE] as string | undefined;
  if (cookieToken) {
    return cookieToken;
  }
  // Fallback to Authorization header for testing/API clients
  const authHeader = req?.headers?.authorization;
  if (authHeader?.startsWith('Bearer ')) {
    return authHeader.substring(7);
  }
  return null;
};

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(configService: ConfigService) {
    const options: StrategyOptionsWithRequest = {
      jwtFromRequest: ExtractJwt.fromExtractors([cookieExtractor]),
      ignoreExpiration: false,
      secretOrKey:
        configService.get<string>('auth.jwt.secret') || 'default-secret',
      passReqToCallback: true,
    };
    super(options);
  }

  validate(_req: express.Request, payload: JwtPayload) {
    if (!payload.sub) {
      throw new UnauthorizedException('Invalid token');
    }

    return {
      userId: payload.sub,
      email: payload.email,
      name: payload.name,
      authorities: payload.authorities,
      jobTitle: payload.jobTitle,
      department: payload.department,
      authDeptId: payload.authDeptId,
      deptPermissions: payload.deptPermissions,
    };
  }
}
