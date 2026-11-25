// import { Controller, Get, Query, Req, Res } from '@nestjs/common';
// import { ConfigService } from '@nestjs/config';
// import { ApiTags, ApiOperation, ApiResponse } from '@nestjs/swagger';
// import * as express from 'express';
// import { AuthService } from './auth.service';
// import { Public } from './decorators/public.decorator';
// import { ResponseCode } from '../common/decorators/response-code.decorator';
// import { ResponseCode as RC } from '../common/constants/response-codes';
//
// @ApiTags('auth-mock')
// @Controller('auth/mock')
// export class AuthMockController {
//   constructor(
//     private readonly authService: AuthService,
//     private readonly configService: ConfigService,
//   ) {}
//
//   @Public()
//   @Get('login-url')
//   @ResponseCode(RC.AUTH_LOGIN_SUCCESS)
//   @ApiOperation({ summary: '개발/테스트용 목 로그인 URL (홍길동 자동 인증)' })
//   @ApiResponse({ status: 200, description: 'Mock login — 토큰 즉시 발급' })
//   async getLoginUrl(
//     @Req() req: express.Request,
//     @Res({ passthrough: true }) res: express.Response,
//   ) {
//     const tokens = await this.authService.generateMockTokens();
//     this.authService.setTokenCookies(req, res, tokens);
//
//     const frontendUrl = this.configService.get<string>('auth.frontendUrl');
//     return {
//       data: { url: frontendUrl },
//       message: 'Mock login successful, redirect to frontend',
//     };
//   }
//
//   @Public()
//   @Get('callback')
//   @ApiOperation({
//     summary: '개발/테스트용 목 콜백 (홍길동 자동 인증 + 리다이렉트)',
//   })
//   @ApiResponse({
//     status: 302,
//     description: 'Mock login — 프론트엔드로 리다이렉트',
//   })
//   async callback(
//     @Query('code') _code: string,
//     @Query('state') _state: string,
//     @Req() req: express.Request,
//     @Res() res: express.Response,
//   ) {
//     const tokens = await this.authService.generateMockTokens();
//     this.authService.setTokenCookies(req, res, tokens);
//
//     const frontendUrl = this.configService.get<string>('auth.frontendUrl');
//     return res.redirect(`${frontendUrl}`);
//   }
// }
