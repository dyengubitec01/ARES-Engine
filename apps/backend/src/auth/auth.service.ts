import { Injectable, UnauthorizedException, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { InjectRepository } from '@nestjs/typeorm';
import { In, Repository } from 'typeorm';
import { randomBytes } from 'crypto';
import { AuthUser } from './entities/auth-user.entity';
import { AuthUsersAuthority } from './entities/auth-users-authority.entity';
import { AuthUsersAuthorityPermission } from './entities/auth-users-authority-permission.entity';
import { AuthUsersDept } from './entities/auth-users-dept.entity';
import { AuthUsersDeptAuthorityPermission } from './entities/auth-users-dept-authority-permission.entity';
import { AuthUsersLoginHistory } from './entities/auth-users-login-history.entity';
import { AuthorityType } from '../common/enums';
import * as express from 'express';

interface AzureUserInfo {
  id: string;
  mail: string;
  displayName: string;
  jobTitle: string | null;
  department: string | null;
}

export interface JwtPayload {
  sub: string;
  email: string;
  name: string;
  authorities: AuthorityType[];
  jobTitle: string | null;
  department: string | null;
  authDeptId: string | null;
  deptPermissions: string[];
  iat?: number;
  exp?: number;
}

interface StoredState {
  createdAt: number;
}

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);

  // In-memory state storage for CSRF protection (5 minute TTL)
  private readonly stateStore = new Map<string, StoredState>();
  private static readonly STATE_TTL_MS = 5 * 60 * 1000; // 5 minutes

  constructor(
    private configService: ConfigService,
    private jwtService: JwtService,
    @InjectRepository(AuthUser)
    private authUserRepository: Repository<AuthUser>,
    @InjectRepository(AuthUsersAuthority)
    private authorityRepository: Repository<AuthUsersAuthority>,
    @InjectRepository(AuthUsersAuthorityPermission)
    private authorityPermissionRepository: Repository<AuthUsersAuthorityPermission>,
    @InjectRepository(AuthUsersDept)
    private authUsersDeptRepository: Repository<AuthUsersDept>,
    @InjectRepository(AuthUsersDeptAuthorityPermission)
    private deptPermissionRepository: Repository<AuthUsersDeptAuthorityPermission>,
    @InjectRepository(AuthUsersLoginHistory)
    private loginHistoryRepository: Repository<AuthUsersLoginHistory>,
  ) {
    // Clean up expired states every minute
    setInterval(() => this.cleanupExpiredStates(), 60 * 1000);
  }

  /**
   * Generate Azure AD login URL with state parameter for CSRF protection
   */
  generateLoginUrl(): { url: string; state: string } {
    const tenantId = this.configService.get<string>('auth.azure.tenantId');
    const clientId = this.configService.get<string>('auth.azure.clientId');
    const redirectUri = this.configService.get<string>(
      'auth.azure.redirectUri',
    );

    // Generate random state for CSRF protection
    const state = randomBytes(32).toString('hex');
    this.stateStore.set(state, { createdAt: Date.now() });

    const params = new URLSearchParams({
      client_id: clientId || '',
      response_type: 'code',
      redirect_uri: redirectUri || '',
      state: state,
      scope: 'openid profile email User.Read',
      response_mode: 'query',
    });

    const url = `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/authorize?${params.toString()}`;

    return { url, state };
  }

  /**
   * Validate state parameter to prevent CSRF attacks
   */
  validateState(state: string): boolean {
    const storedState = this.stateStore.get(state);
    if (!storedState) {
      return false;
    }

    // Check if state has expired
    if (Date.now() - storedState.createdAt > AuthService.STATE_TTL_MS) {
      this.stateStore.delete(state);
      return false;
    }

    // State is valid, remove it (one-time use)
    this.stateStore.delete(state);
    return true;
  }

  /**
   * Clean up expired states from memory
   */
  private cleanupExpiredStates(): void {
    const now = Date.now();
    for (const [state, data] of this.stateStore.entries()) {
      if (now - data.createdAt > AuthService.STATE_TTL_MS) {
        this.stateStore.delete(state);
      }
    }
  }

  async exchangeCodeForTokens(code: string) {
    const tenantId = this.configService.get<string>('auth.azure.tenantId');
    const clientId = this.configService.get<string>('auth.azure.clientId');
    const clientSecret = this.configService.get<string>(
      'auth.azure.clientSecret',
    );
    const redirectUri = this.configService.get<string>(
      'auth.azure.redirectUri',
    );

    const tokenUrl = `https://login.microsoftonline.com/${tenantId}/oauth2/v2.0/token`;

    const params = new URLSearchParams();
    params.append('client_id', clientId || '');
    params.append('client_secret', clientSecret || '');
    params.append('code', code);
    params.append('redirect_uri', redirectUri || '');
    params.append('grant_type', 'authorization_code');
    params.append('scope', 'openid profile email User.Read');

    let response: Response;
    try {
      response = await fetch(tokenUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: params.toString(),
      });
    } catch (fetchError) {
      this.logger.error(`Failed to connect to Azure AD: ${fetchError}`);
      throw new UnauthorizedException('Failed to connect to Azure AD');
    }

    if (!response.ok) {
      const errorBody = await response.text();
      this.logger.error(`Failed to exchange code for tokens: ${errorBody}`);
      throw new UnauthorizedException('Authentication failed');
    }

    const tokenData = (await response.json()) as {
      access_token: string;
      id_token: string;
    };

    if (!tokenData.id_token) {
      this.logger.error('No id_token received from Azure AD');
      throw new UnauthorizedException('Authentication failed - no id_token');
    }

    // Decode id_token to get basic user info
    const basicUserInfo = this.decodeIdToken(tokenData.id_token);

    // Call Graph API to get jobTitle and department
    const graphProfile = await this.fetchUserProfileFromGraph(
      tokenData.access_token,
    );

    // Merge user info
    const azureUserInfo: AzureUserInfo = {
      ...basicUserInfo,
      jobTitle: graphProfile.jobTitle,
      department: graphProfile.department,
    };

    // Find or create user in database (with department sync)
    const user = await this.findOrCreateUser(azureUserInfo);

    // 로그인 이력 기록 (fire-and-forget)
    this.recordLoginHistory(user.id).catch((err) => {
      this.logger.error(`Failed to record login history: ${err}`);
    });

    // Generate JWT tokens with user info from database
    return this.generateTokens(user, azureUserInfo);
  }

  /**
   * Decode Azure AD id_token to extract basic user info
   * id_token is a JWT with claims like sub, email, name
   */
  private decodeIdToken(idToken: string): {
    id: string;
    mail: string;
    displayName: string;
  } {
    try {
      // JWT format: header.payload.signature
      const parts = idToken.split('.');
      if (parts.length !== 3) {
        throw new Error('Invalid id_token format');
      }

      // Decode payload (base64url -> JSON)
      const payload = Buffer.from(parts[1], 'base64url').toString('utf8');
      const claims = JSON.parse(payload) as {
        sub: string;
        email?: string;
        preferred_username?: string;
        name?: string;
      };

      return {
        id: claims.sub,
        mail: (claims.email || claims.preferred_username || '').trim(),
        displayName: (claims.name || '').trim(),
      };
    } catch (error) {
      this.logger.error(`Failed to decode id_token: ${error}`);
      throw new UnauthorizedException('Invalid id_token');
    }
  }

  /**
   * Call Microsoft Graph API to get user's jobTitle and department
   */
  private async fetchUserProfileFromGraph(
    accessToken: string,
  ): Promise<{ jobTitle: string | null; department: string | null }> {
    try {
      const response = await fetch(
        'https://graph.microsoft.com/v1.0/me?$select=jobTitle,department',
        {
          headers: {
            Authorization: `Bearer ${accessToken}`,
          },
        },
      );

      if (!response.ok) {
        this.logger.warn(
          `Graph API call failed: ${response.status} ${response.statusText}`,
        );
        return { jobTitle: null, department: null };
      }

      const data = (await response.json()) as Record<string, unknown>;
      this.logger.log(`Graph API response: ${JSON.stringify(data)}`);

      return {
        jobTitle: (data.jobTitle as string)?.trim() || null,
        department: (data.department as string)?.trim() || null,
      };
    } catch (error) {
      this.logger.warn(`Failed to fetch user profile from Graph API: ${error}`);
      return { jobTitle: null, department: null };
    }
  }

  /**
   * Find existing user by email or create new user with default values
   * AC2: Auto-registration for new users
   * AC3: Existing user login
   * Also syncs department from Azure AD Graph API
   */
  private async findOrCreateUser(
    azureUserInfo: AzureUserInfo,
  ): Promise<AuthUser> {
    const email = azureUserInfo.mail;

    // Look up user by email
    let user = await this.authUserRepository.findOne({
      where: { email },
    });

    if (user) {
      // Existing user: update jobTitle from Azure AD
      if (azureUserInfo.jobTitle !== undefined) {
        const cleanJobTitle =
          azureUserInfo.jobTitle
            ?.replace(/[\u200B-\u200D\uFEFF\u00AD\u2060]/g, '')
            .trim() || null;
        if (user.jobTitle !== cleanJobTitle) {
          user.jobTitle = cleanJobTitle;
          await this.authUserRepository.save(user);
        }
      }
      this.logger.log(`Existing user logged in: ${email}`);
      return user;
    }

    // First login: sync department from Azure AD
    let deptId: string | undefined;
    if (azureUserInfo.department) {
      const dept = await this.findOrCreateDepartment(azureUserInfo.department);
      deptId = dept.id;
    }

    // Create new user with defaults per AC2
    user = this.authUserRepository.create({
      email: azureUserInfo.mail,
      name: azureUserInfo.displayName
        .replace(/[\u200B-\u200D\uFEFF\u00AD\u2060]/g, '')
        .trim(),
      jobTitle:
        azureUserInfo.jobTitle
          ?.replace(/[\u200B-\u200D\uFEFF\u00AD\u2060]/g, '')
          .trim() || null,
      ...(deptId && { authDeptId: deptId }),
    });

    await this.authUserRepository.save(user);

    // Grant default uploader permission per Story 1.3
    await this.grantDefaultUploaderPermission(user.id);

    this.logger.log(`New user registered: ${email}`);

    return user;
  }

  /**
   * Find existing department by name or create new one
   */
  private async findOrCreateDepartment(
    deptName: string,
  ): Promise<AuthUsersDept> {
    let dept = await this.authUsersDeptRepository.findOne({
      where: { deptName },
    });

    if (!dept) {
      dept = this.authUsersDeptRepository.create({ deptName });
      await this.authUsersDeptRepository.save(dept);
      this.logger.log(`New department created: ${deptName}`);
    }

    return dept;
  }

  /**
   * Grant default uploader permission to newly registered user
   */
  private async grantDefaultUploaderPermission(userId: string): Promise<void> {
    // Find uploader authority
    const uploaderAuthority = await this.authorityRepository.findOne({
      where: { authorityName: AuthorityType.UPLOADER },
    });

    if (!uploaderAuthority) {
      this.logger.error('Uploader authority not found in database');
      return;
    }

    // Create permission record
    const permission = this.authorityPermissionRepository.create({
      authorityId: uploaderAuthority.id,
      usersId: userId,
    });

    await this.authorityPermissionRepository.save(permission);
    this.logger.log(`Default uploader permission granted to user: ${userId}`);
  }

  /**
   * Get user's authorities from permission table
   */
  private async getUserAuthorities(userId: string): Promise<AuthorityType[]> {
    const permissions = await this.authorityPermissionRepository.find({
      where: { usersId: userId },
      relations: ['authority'],
    });

    return permissions.map((p) => p.authority.authorityName);
  }

  /**
   * Token expiration constants
   */
  static readonly ACCESS_TOKEN_EXPIRY = 900; // 15 minutes in seconds
  static readonly REFRESH_TOKEN_EXPIRY = 604800; // 7 days in seconds

  /**
   * Generate JWT access and refresh tokens
   * AC5: JWT Payload Structure with user.id, email, name, authorities, jobTitle, department
   * Returns tokens separately for controller to set as httpOnly cookies
   */
  /**
   * 전사 공개 부서 ID (env PUBLIC_DEPT_IDS).
   */
  getPublicDeptIds(): string[] {
    return (
      this.configService.get<string[]>('department.publicDeptIds') ?? []
    );
  }

  /**
   * 사용자의 접근 가능 부서 ID 목록 = 본인 부서 + 권한 부여 부서 + 전사 공개 부서 UNION.
   * 순수 함수 — JWT 에서 풀린 값과 env 만 결합.
   */
  getAccessibleDeptIds(
    authDeptId: string | null,
    deptPermissions: string[],
  ): string[] {
    return [
      ...new Set([
        ...(authDeptId ? [authDeptId] : []),
        ...deptPermissions,
        ...this.getPublicDeptIds(),
      ]),
    ];
  }

  /**
   * 부서 UUID 배열을 {id, name} 객체 배열로 변환.
   * 삭제/누락된 부서는 결과에서 제외.
   */
  async resolveDeptNames(
    deptIds: string[],
  ): Promise<{ id: string; name: string }[]> {
    if (!deptIds || deptIds.length === 0) return [];
    const rows = await this.authUsersDeptRepository.find({
      where: { id: In(deptIds) },
    });
    const map = new Map(rows.map((r) => [r.id, r.deptName]));
    return deptIds
      .filter((id) => map.has(id))
      .map((id) => ({ id, name: map.get(id) as string }));
  }

  async generateTokens(user: AuthUser, azureUserInfo?: AzureUserInfo) {
    const authorities = await this.getUserAuthorities(user.id);

    // Get department name if user has one
    let departmentName: string | null = null;
    if (user.authDeptId) {
      const dept = await this.authUsersDeptRepository.findOne({
        where: { id: user.authDeptId },
      });
      departmentName = dept?.deptName || null;
    }

    // Get department permissions
    const deptPermissions = await this.deptPermissionRepository.find({
      where: { usersId: user.id },
    });
    const deptPermissionIds = deptPermissions.map((p) => p.deptId);

    const payload: Omit<JwtPayload, 'iat' | 'exp'> = {
      sub: user.id,
      email: user.email,
      name: user.name || '',
      authorities,
      jobTitle: user.jobTitle || azureUserInfo?.jobTitle || null,
      department: departmentName,
      authDeptId: user.authDeptId || null,
      deptPermissions: deptPermissionIds,
    };

    const accessToken = this.jwtService.sign(payload, {
      expiresIn: AuthService.ACCESS_TOKEN_EXPIRY,
    });

    const refreshToken = this.jwtService.sign(payload, {
      expiresIn: AuthService.REFRESH_TOKEN_EXPIRY,
    });

    return {
      accessToken,
      refreshToken,
      expiresIn: AuthService.ACCESS_TOKEN_EXPIRY,
    };
  }

  /**
   * userId로 DB 재조회 후 새 토큰 발급 (Guard에서 사용)
   */
  async regenerateTokens(userId: string) {
    const user = await this.authUserRepository.findOne({
      where: { id: userId },
    });
    if (!user) {
      return null;
    }
    return this.generateTokens(user);
  }

  /**
   * JWT 토큰을 디코딩하여 payload 반환 (검증 없이)
   */
  decodeToken(token: string): JwtPayload | null {
    try {
      return this.jwtService.decode<JwtPayload>(token);
    } catch {
      return null;
    }
  }

  async refreshTokens(currentRefreshToken: string) {
    try {
      const payload = this.jwtService.verify<JwtPayload>(currentRefreshToken);

      // Look up user from database
      const user = await this.authUserRepository.findOne({
        where: { id: payload.sub },
      });

      if (!user) {
        throw new UnauthorizedException('Invalid refresh token');
      }

      // Generate new tokens with current user data and authorities
      return await this.generateTokens(user);
    } catch {
      throw new UnauthorizedException('Invalid refresh token');
    }
  }

  // ── Cookie helpers (shared by AuthController & AuthMockController) ──

  private static readonly ACCESS_TOKEN_COOKIE = 'access_token';
  private static readonly REFRESH_TOKEN_COOKIE = 'refresh_token';

  getCookieOptions(req: express.Request) {
    const isSecure = req.headers['x-forwarded-proto'] === 'https';
    return {
      httpOnly: true,
      secure: isSecure,
      sameSite: isSecure ? ('none' as const) : ('lax' as const),
      path: '/',
    };
  }

  setTokenCookies(
    req: express.Request,
    res: express.Response,
    tokens: { accessToken: string; refreshToken: string; expiresIn: number },
  ) {
    const cookieOptions = this.getCookieOptions(req);

    res.cookie(AuthService.ACCESS_TOKEN_COOKIE, tokens.accessToken, {
      ...cookieOptions,
      maxAge: tokens.expiresIn * 1000,
    });

    res.cookie(AuthService.REFRESH_TOKEN_COOKIE, tokens.refreshToken, {
      ...cookieOptions,
      maxAge: AuthService.REFRESH_TOKEN_EXPIRY * 1000,
    });
  }

  clearTokenCookies(res: express.Response) {
    res.clearCookie(AuthService.ACCESS_TOKEN_COOKIE, { path: '/' });
    res.clearCookie(AuthService.REFRESH_TOKEN_COOKIE, { path: '/' });
  }

  getRefreshTokenFromRequest(req: express.Request): string | undefined {
    return req.cookies?.[AuthService.REFRESH_TOKEN_COOKIE] as
      | string
      | undefined;
  }

  logout(userId: string) {
    this.logger.log(`User ${userId} logged out`);
    return { message: 'Logged out successfully' };
  }

  /**
   * 개발/테스트용 목 로그인: "홍길동" 사용자로 토큰 생성
   */
  async generateMockTokens() {
    const mockUser = await this.authUserRepository.findOne({
      where: { name: '홍길동' },
    });

    if (!mockUser) {
      throw new UnauthorizedException(
        'Mock user "홍길동" not found in database',
      );
    }

    this.logger.log(`Mock login: ${mockUser.email}`);
    return this.generateTokens(mockUser);
  }

  private async recordLoginHistory(userId: string): Promise<void> {
    await this.loginHistoryRepository
      .createQueryBuilder()
      .insert()
      .values({
        userId,
        uniqueLoginDate: () => 'CURRENT_DATE',
      })
      .orIgnore()
      .execute();
  }
}
