import {
  Controller,
  Post,
  HttpCode,
  HttpStatus,
  Get,
  Query,
  Req,
  Res,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import {
  ApiTags,
  ApiOperation,
  ApiResponse,
  ApiCookieAuth,
  ApiQuery,
} from '@nestjs/swagger';
import * as express from 'express';
import { AuthService } from './auth.service';
import { Public } from './decorators/public.decorator';
import { CurrentUser } from './decorators/current-user.decorator';
import type { AuthenticatedUser } from './types/authenticated-user';
import { ResponseCode } from '../common/decorators/response-code.decorator';
import { ResponseCode as RC } from '../common/constants/response-codes';
import * as Examples from './swagger-examples/auth.examples';

// State cookie name for CSRF protection
const STATE_COOKIE = 'oauth_state';

@ApiTags('auth')
@Controller('auth')
export class AuthController {
  constructor(
    private readonly authService: AuthService,
    private readonly configService: ConfigService,
  ) {}

  /**
   * Generate Azure AD login URL with state parameter for CSRF protection
   * Frontend calls this first, then redirects user to the returned URL
   */
  @Public()
  @Get('login-url')
  @ResponseCode(RC.AUTH_LOGIN_SUCCESS)
  @ApiOperation({ summary: 'Azure AD 로그인 URL 조회 (CSRF 방어 포함)' })
  @ApiResponse({
    status: 200,
    description: 'Returns Azure AD login URL and state for CSRF protection',
    schema: { example: Examples.GetLoginUrlSuccessExample },
  })
  async getLoginUrl(
    @Req() req: express.Request,
    @Res({ passthrough: true }) res: express.Response,
  ) {
    const { url, state } = this.authService.generateLoginUrl();
    const cookieOptions = this.authService.getCookieOptions(req);

    // Store state in httpOnly cookie for validation on callback
    res.cookie(STATE_COOKIE, state, {
      ...cookieOptions,
      maxAge: 5 * 60 * 1000, // 5 minutes
    });

    return {
      data: { url },
      message: 'Redirect user to this URL for Azure AD login',
    };
  }

  /**
   * Azure AD OAuth callback endpoint
   * Azure redirects here after user authentication
   * Validates state parameter, exchanges code for tokens, redirects to frontend
   */
  @Public()
  @Get('callback')
  @ApiOperation({
    summary: 'Azure AD OAuth 콜백 (state 검증 및 토큰 교환)',
  })
  @ApiQuery({ name: 'code', description: 'Authorization code from Azure AD' })
  @ApiQuery({
    name: 'state',
    description: 'State parameter for CSRF validation',
  })
  @ApiResponse({
    status: 302,
    description:
      'Login successful, redirects to frontend with tokens in cookies',
  })
  @ApiResponse({
    status: 401,
    description: 'Invalid state or authorization code',
  })
  async callback(
    @Query('code') code: string,
    @Query('state') state: string,
    @Req() req: express.Request,
    @Res() res: express.Response,
  ) {
    // Get state from cookie for CSRF validation
    const storedState = req.cookies?.[STATE_COOKIE] as string | undefined;

    // Validate state matches (CSRF protection)
    if (!state || !storedState || state !== storedState) {
      throw new UnauthorizedException(
        'Invalid state parameter - possible CSRF attack',
      );
    }

    // Validate state in backend store
    if (!this.authService.validateState(state)) {
      throw new UnauthorizedException('State expired or already used');
    }

    // Clear state cookie
    res.clearCookie(STATE_COOKIE, { path: '/' });

    // Exchange code for tokens
    const tokens = await this.authService.exchangeCodeForTokens(code);
    this.authService.setTokenCookies(req, res, tokens);

    // Redirect to frontend
    const frontendUrl = this.configService.get<string>('auth.frontendUrl');
    return res.redirect(`${frontendUrl}`);
  }

  @Public()
  @Post('refresh')
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.AUTH_TOKEN_REFRESH_SUCCESS)
  @ApiOperation({ summary: '토큰 갱신 (refresh_token 쿠키 사용)' })
  @ApiResponse({
    status: 200,
    description: 'Token refreshed, new tokens set in httpOnly cookies',
    schema: { example: Examples.RefreshSuccessExample },
  })
  @ApiResponse({ status: 401, description: 'Invalid refresh token' })
  async refresh(
    @Req() req: express.Request,
    @Res({ passthrough: true }) res: express.Response,
  ) {
    const refreshToken = this.authService.getRefreshTokenFromRequest(req);
    if (!refreshToken) {
      throw new UnauthorizedException('Refresh token not found');
    }

    const tokens = await this.authService.refreshTokens(refreshToken);
    this.authService.setTokenCookies(req, res, tokens);

    return {
      data: { expiresIn: tokens.expiresIn },
      message: 'Token refreshed',
    };
  }

  @Post('logout')
  @HttpCode(HttpStatus.OK)
  @ResponseCode(RC.AUTH_LOGOUT_SUCCESS)
  @ApiCookieAuth()
  @ApiOperation({ summary: '로그아웃 및 토큰 쿠키 삭제' })
  @ApiResponse({
    status: 200,
    description: 'Logout successful',
    schema: { example: Examples.LogoutSuccessExample },
  })
  logout(
    @CurrentUser() user: AuthenticatedUser,
    @Res({ passthrough: true }) res: express.Response,
  ) {
    this.authService.clearTokenCookies(res);
    return this.authService.logout(user.userId);
  }

  @Get('me')
  @ResponseCode(RC.AUTH_PROFILE_SUCCESS)
  @ApiCookieAuth()
  @ApiOperation({ summary: '현재 사용자 정보 조회' })
  @ApiResponse({
    status: 200,
    description: 'Current user info',
    schema: { example: Examples.GetProfileSuccessExample },
  })
  async getProfile(@CurrentUser() user: AuthenticatedUser) {
    const { deptPermissions, ...rest } = user;
    const deptPermissionsDetail =
      await this.authService.resolveDeptNames(deptPermissions ?? []);
    return {
      data: {
        ...rest,
        deptPermissions: deptPermissionsDetail,
      },
    };
  }
}
