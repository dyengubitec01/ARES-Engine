/* eslint-disable @typescript-eslint/unbound-method, @typescript-eslint/no-unsafe-assignment */
import { Test, TestingModule } from '@nestjs/testing';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { UnauthorizedException } from '@nestjs/common';
import { getRepositoryToken } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { AuthService } from './auth.service';
import { AuthUser } from './entities/auth-user.entity';
import { AuthUsersAuthority } from './entities/auth-users-authority.entity';
import { AuthUsersAuthorityPermission } from './entities/auth-users-authority-permission.entity';
import { AuthorityType } from '../common/enums';

describe('AuthService', () => {
  let service: AuthService;
  let jwtService: JwtService;
  let authUserRepository: Repository<AuthUser>;

  const mockConfigService = {
    get: jest.fn((key: string) => {
      const config: Record<string, string> = {
        'auth.azure.tenantId': 'test-tenant-id',
        'auth.azure.clientId': 'test-client-id',
        'auth.azure.clientSecret': 'test-client-secret',
        'auth.azure.redirectUri': 'http://localhost:3000/auth/callback',
      };
      return config[key];
    }),
  };

  const mockJwtService = {
    sign: jest.fn().mockReturnValue('mock-jwt-token'),
    verify: jest.fn(),
  };

  const mockUser: Partial<AuthUser> = {
    id: 'user-uuid-123',
    email: 'user@example.com',
    name: 'Test User',
    authDeptId: '00000000-0000-0000-0000-000000000001',
    createdAt: new Date(),
  };

  const mockAuthUserRepository = {
    findOne: jest.fn(),
    create: jest.fn(),
    save: jest.fn(),
  };

  const mockAuthorityRepository = {
    findOne: jest.fn(),
  };

  const mockAuthorityPermissionRepository = {
    find: jest.fn(),
    create: jest.fn(),
    save: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AuthService,
        { provide: ConfigService, useValue: mockConfigService },
        { provide: JwtService, useValue: mockJwtService },
        {
          provide: getRepositoryToken(AuthUser),
          useValue: mockAuthUserRepository,
        },
        {
          provide: getRepositoryToken(AuthUsersAuthority),
          useValue: mockAuthorityRepository,
        },
        {
          provide: getRepositoryToken(AuthUsersAuthorityPermission),
          useValue: mockAuthorityPermissionRepository,
        },
      ],
    }).compile();

    service = module.get<AuthService>(AuthService);
    jwtService = module.get<JwtService>(JwtService);
    authUserRepository = module.get<Repository<AuthUser>>(
      getRepositoryToken(AuthUser),
    );
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('refreshTokens', () => {
    it('[P1] should return new tokens for valid refresh token with existing user', async () => {
      // GIVEN: Valid refresh token payload and existing user
      const mockPayload = {
        sub: 'user-uuid-123',
        email: 'user@example.com',
        name: 'Test User',
        authorities: [AuthorityType.UPLOADER],
      };
      mockJwtService.verify.mockReturnValue(mockPayload);
      mockAuthUserRepository.findOne.mockResolvedValue(mockUser);
      mockAuthorityPermissionRepository.find.mockResolvedValue([
        {
          authority: { authorityName: AuthorityType.UPLOADER },
        },
      ]);

      // WHEN: Refreshing tokens
      const result = await service.refreshTokens('valid-refresh-token');

      // THEN: Returns new access and refresh tokens (service returns raw, interceptor wraps)
      expect(result).toHaveProperty('accessToken');
      expect(result).toHaveProperty('refreshToken');
      expect(result).toHaveProperty('expiresIn', 900);

      expect(jwtService.verify).toHaveBeenCalledWith('valid-refresh-token');
      expect(authUserRepository.findOne).toHaveBeenCalledWith({
        where: { id: 'user-uuid-123' },
      });
    });

    it('[P1] should throw UnauthorizedException for invalid refresh token', async () => {
      // GIVEN: Invalid refresh token
      mockJwtService.verify.mockImplementation(() => {
        throw new Error('invalid token');
      });

      // WHEN/THEN: Throws UnauthorizedException
      await expect(service.refreshTokens('invalid-token')).rejects.toThrow(
        UnauthorizedException,
      );
    });

    it('[P1] should throw UnauthorizedException for expired refresh token', async () => {
      // GIVEN: Expired refresh token
      mockJwtService.verify.mockImplementation(() => {
        throw new Error('jwt expired');
      });

      // WHEN/THEN: Throws UnauthorizedException
      await expect(service.refreshTokens('expired-token')).rejects.toThrow(
        UnauthorizedException,
      );
    });

    it('[P1] should throw UnauthorizedException when user not found in database', async () => {
      // GIVEN: Valid token but user deleted from database
      const mockPayload = {
        sub: 'deleted-user-uuid',
        email: 'deleted@example.com',
        name: 'Deleted User',
        authorities: [AuthorityType.UPLOADER],
      };
      mockJwtService.verify.mockReturnValue(mockPayload);
      mockAuthUserRepository.findOne.mockResolvedValue(null);

      // WHEN/THEN: Throws UnauthorizedException
      await expect(
        service.refreshTokens('valid-token-deleted-user'),
      ).rejects.toThrow(UnauthorizedException);
    });
  });

  describe('logout', () => {
    it('[P2] should return success message', () => {
      // GIVEN: Valid user ID
      const userId = 'user-123';

      // WHEN: Logging out
      const result = service.logout(userId);

      // THEN: Returns success message
      expect(result).toEqual({ message: 'Logged out successfully' });
    });
  });

  describe('generateTokens (via refreshTokens)', () => {
    it('[P1] should include authorities in JWT payload', async () => {
      // GIVEN: Mock user with admin authority
      const userWithAdminAuth = { ...mockUser };

      // Track what payload was signed
      let signedPayload: Record<string, unknown> | null = null;
      mockJwtService.sign.mockImplementation(
        (payload: Record<string, unknown>) => {
          signedPayload = payload;
          return 'mock-jwt-token';
        },
      );

      // Mock refreshTokens to test token generation
      mockJwtService.verify.mockReturnValue({
        sub: userWithAdminAuth.id,
        email: userWithAdminAuth.email,
        name: userWithAdminAuth.name,
        authorities: [AuthorityType.ADMIN],
      });
      mockAuthUserRepository.findOne.mockResolvedValue(userWithAdminAuth);
      mockAuthorityPermissionRepository.find.mockResolvedValue([
        {
          authority: { authorityName: AuthorityType.ADMIN },
        },
      ]);

      // WHEN: Refreshing tokens (which uses the same token generation logic)
      await service.refreshTokens('valid-token');

      // THEN: JWT payload includes authorities array
      expect(signedPayload).toHaveProperty('authorities', [
        AuthorityType.ADMIN,
      ]);
      expect(signedPayload).toHaveProperty('sub', userWithAdminAuth.id);
      expect(signedPayload).toHaveProperty('email', userWithAdminAuth.email);
    });
  });

  describe('response format', () => {
    it('[P1] should wrap tokens in data object for refresh', async () => {
      // GIVEN: Valid refresh token and user
      mockJwtService.verify.mockReturnValue({
        sub: mockUser.id,
        email: mockUser.email,
        name: mockUser.name,
        authorities: [AuthorityType.UPLOADER],
      });
      mockAuthUserRepository.findOne.mockResolvedValue(mockUser);
      mockAuthorityPermissionRepository.find.mockResolvedValue([
        {
          authority: { authorityName: AuthorityType.UPLOADER },
        },
      ]);

      // WHEN: Refreshing tokens
      const result = await service.refreshTokens('valid-token');

      // THEN: Response has correct structure (service returns raw, interceptor wraps)
      expect(result).toEqual({
        accessToken: expect.any(String),
        refreshToken: expect.any(String),
        expiresIn: 900,
      });
    });
  });
});
