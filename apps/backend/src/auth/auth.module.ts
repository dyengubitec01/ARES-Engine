import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { JwtModule } from '@nestjs/jwt';
import { PassportModule } from '@nestjs/passport';
import { TypeOrmModule } from '@nestjs/typeorm';
import { AuthController } from './auth.controller';
// import { AuthMockController } from './auth-mock.controller';
import { AuthService } from './auth.service';
import { JwtStrategy } from './strategies/jwt.strategy';
import { AuthUser } from './entities/auth-user.entity';
import { AuthUsersAuthority } from './entities/auth-users-authority.entity';
import { AuthUsersAuthorityPermission } from './entities/auth-users-authority-permission.entity';
import { AuthUsersDept } from './entities/auth-users-dept.entity';
import { AuthUsersDeptAuthorityPermission } from './entities/auth-users-dept-authority-permission.entity';
import { AuthUsersLoginHistory } from './entities/auth-users-login-history.entity';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      AuthUser,
      AuthUsersAuthority,
      AuthUsersAuthorityPermission,
      AuthUsersDept,
      AuthUsersDeptAuthorityPermission,
      AuthUsersLoginHistory,
    ]),
    PassportModule.register({ defaultStrategy: 'jwt' }),
    JwtModule.registerAsync({
      imports: [ConfigModule],
      useFactory: (configService: ConfigService) => ({
        secret: configService.get<string>('auth.jwt.secret'),
        signOptions: {
          expiresIn: 900,
        },
      }),
      inject: [ConfigService],
    }),
  ],
  controllers: [AuthController],
  providers: [AuthService, JwtStrategy],
  exports: [AuthService, JwtModule],
})
export class AuthModule {}
