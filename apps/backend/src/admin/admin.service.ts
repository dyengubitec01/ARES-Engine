import { Injectable, Logger, HttpStatus } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { In, Repository } from 'typeorm';
import { AuthUser } from '../auth/entities/auth-user.entity';
import { AuthUsersAuthority } from '../auth/entities/auth-users-authority.entity';
import { AuthUsersAuthorityPermission } from '../auth/entities/auth-users-authority-permission.entity';
import { AuthUsersDept } from '../auth/entities/auth-users-dept.entity';
import { AuthUsersDeptAuthorityPermission } from '../auth/entities/auth-users-dept-authority-permission.entity';
import { AuthorityType } from '../common/enums';
import { BusinessException } from '../common/exceptions/business.exception';
import {
  ResponseCode,
  getHttpStatus,
} from '../common/constants/response-codes';
import {
  UserListQueryDto,
  UserWithAuthoritiesDto,
  GrantAuthoritiesDto,
  RevokeAuthoritiesDto,
  UserDeptPermissionDto,
} from './dto/admin.dto';
import { RedisService } from '../external/redis/redis.service';

@Injectable()
export class AdminService {
  private readonly logger = new Logger(AdminService.name);

  constructor(
    @InjectRepository(AuthUser)
    private userRepository: Repository<AuthUser>,
    @InjectRepository(AuthUsersAuthority)
    private authorityRepository: Repository<AuthUsersAuthority>,
    @InjectRepository(AuthUsersDept)
    private deptRepository: Repository<AuthUsersDept>,
    @InjectRepository(AuthUsersAuthorityPermission)
    private permissionRepository: Repository<AuthUsersAuthorityPermission>,
    @InjectRepository(AuthUsersDeptAuthorityPermission)
    private deptPermissionRepository: Repository<AuthUsersDeptAuthorityPermission>,
    private readonly redisService: RedisService,
  ) {}

  /**
   * 전체 부서 목록 조회
   */
  async getDeptList() {
    const depts = await this.deptRepository.find({
      order: { deptName: 'ASC' },
    });
    return depts.map((d) => ({ id: d.id, deptName: d.deptName }));
  }

  /**
   * Story 3.2: 사용자 목록 조회
   */
  async getUserList(query: UserListQueryDto): Promise<{
    data: UserWithAuthoritiesDto[];
    total: number;
    page: number;
    limit: number;
  }> {
    const { page = 1, limit = 20, search } = query;
    const skip = (page - 1) * limit;

    // Build query with optional search
    const queryBuilder = this.userRepository
      .createQueryBuilder('u')
      .leftJoinAndSelect('u.authDept', 'dept')
      .orderBy('u.createdAt', 'DESC');

    if (search) {
      // 검색 시 전체 결과 반환 (페이지네이션 없음)
      queryBuilder.where('(u.name ILIKE :search OR u.email ILIKE :search)', {
        search: `%${search}%`,
      });
    } else {
      // 검색 없으면 페이지네이션 적용
      queryBuilder.skip(skip).take(limit);
    }

    const [users, total] = await queryBuilder.getManyAndCount();

    // Get authorities and dept permissions for each user
    const usersWithAuthorities: UserWithAuthoritiesDto[] = await Promise.all(
      users.map(async (user) => {
        const [permissionRecords, deptPermissionRecords] = await Promise.all([
          this.permissionRepository.find({
            where: { usersId: user.id },
            relations: ['authority'],
          }),
          this.deptPermissionRepository.find({
            where: { usersId: user.id },
            relations: ['dept'],
            order: { createdAt: 'ASC' },
          }),
        ]);

        const authorities = permissionRecords.map(
          (p) => p.authority.authorityName,
        );
        const permissions = permissionRecords.map((p) => ({
          permissionId: p.id,
          authorityId: p.authorityId,
          authorityName: p.authority.authorityName,
        }));
        const deptPermissions = deptPermissionRecords.map((p) => ({
          id: p.id,
          deptId: p.deptId,
          deptName: p.dept.deptName,
          createdAt: p.createdAt,
        }));

        return {
          id: user.id,
          email: user.email,
          name: user.name || '',
          jobTitle: user.jobTitle || null,
          department: user.authDept?.deptName || null,
          authorities,
          permissions,
          deptPermissions,
          createdAt: user.createdAt,
        };
      }),
    );

    return {
      data: usersWithAuthorities,
      total,
      page: search ? 1 : page,
      limit: search ? total : limit,
    };
  }

  /**
   * Story 3.3: 권한 일괄 부여
   * 사용자 ID와 권한 타입 배열로 일괄 부여
   */
  async grantAuthorities(dto: GrantAuthoritiesDto): Promise<{
    grantedCount: number;
    grantedAuthorities: AuthorityType[];
    skippedAuthorities: AuthorityType[];
    message: string;
  }> {
    const { usersId, authorityTypes } = dto;

    // Check if user exists
    const user = await this.userRepository.findOne({
      where: { id: usersId },
    });
    if (!user) {
      throw new BusinessException(
        ResponseCode.ADMIN_USER_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.ADMIN_USER_NOT_FOUND),
      );
    }

    // Find authorities by type
    const authorities = await this.authorityRepository.find({
      where: authorityTypes.map((type) => ({ authorityName: type })),
    });

    if (authorities.length === 0) {
      throw new BusinessException(
        ResponseCode.ADMIN_AUTHORITY_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.ADMIN_AUTHORITY_NOT_FOUND),
      );
    }

    // Get existing permissions for this user
    const existingPermissions = await this.permissionRepository.find({
      where: { usersId },
    });
    const existingAuthorityIds = new Set(
      existingPermissions.map((p) => p.authorityId),
    );

    // Separate authorities to grant and skip
    const toGrant = authorities.filter((a) => !existingAuthorityIds.has(a.id));
    const toSkip = authorities.filter((a) => existingAuthorityIds.has(a.id));

    // Create new permissions
    if (toGrant.length > 0) {
      const newPermissions = toGrant.map((authority) =>
        this.permissionRepository.create({
          usersId,
          authorityId: authority.id,
        }),
      );
      await this.permissionRepository.save(newPermissions);
    }

    const grantedAuthorities = toGrant.map((a) => a.authorityName);
    const skippedAuthorities = toSkip.map((a) => a.authorityName);

    if (toGrant.length > 0) {
      this.logger.log(
        `권한 부여 완료: 사용자=${usersId}, 부여=[${grantedAuthorities.join(', ')}]` +
          (skippedAuthorities.length > 0
            ? `, 스킵=[${skippedAuthorities.join(', ')}]`
            : ''),
      );
    }

    // Build message
    let message = '';
    if (toGrant.length > 0 && toSkip.length > 0) {
      message = `${toGrant.length}개의 권한이 부여되었습니다. 이미 존재하는 권한: [${skippedAuthorities.join(', ')}]`;
    } else if (toGrant.length > 0) {
      message = `${toGrant.length}개의 권한이 부여되었습니다`;
    } else {
      message = `이미 존재하는 권한입니다: [${skippedAuthorities.join(', ')}]`;
    }

    // 권한 변경 시 토큰 갱신 플래그 설정
    if (toGrant.length > 0) {
      await this.redisService.setTokenRefreshFlag(usersId);
    }

    return {
      grantedCount: toGrant.length,
      grantedAuthorities,
      skippedAuthorities,
      message,
    };
  }

  /**
   * Story 3.4: 권한 일괄 회수
   * 사용자 ID와 권한 타입 배열로 일괄 회수
   */
  async revokeAuthorities(dto: RevokeAuthoritiesDto): Promise<{
    revokedCount: number;
    revokedAuthorities: AuthorityType[];
    message: string;
  }> {
    const { usersId, authorityTypes } = dto;

    // Check if user exists
    const user = await this.userRepository.findOne({
      where: { id: usersId },
    });
    if (!user) {
      throw new BusinessException(
        ResponseCode.ADMIN_USER_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.ADMIN_USER_NOT_FOUND),
      );
    }

    // Find authorities by type
    const authorities = await this.authorityRepository.find({
      where: authorityTypes.map((type) => ({ authorityName: type })),
    });

    if (authorities.length === 0) {
      throw new BusinessException(
        ResponseCode.ADMIN_AUTHORITY_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.ADMIN_AUTHORITY_NOT_FOUND),
      );
    }

    const authorityIds = authorities.map((a) => a.id);

    // Find permissions to revoke
    const permissionsToRevoke = await this.permissionRepository
      .createQueryBuilder('p')
      .where('p.users_id = :usersId', { usersId })
      .andWhere('p.authority_id IN (:...authorityIds)', { authorityIds })
      .getMany();

    if (permissionsToRevoke.length === 0) {
      throw new BusinessException(
        ResponseCode.ADMIN_AUTHORITY_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.ADMIN_AUTHORITY_NOT_FOUND),
      );
    }

    // Revoke permissions
    await this.permissionRepository.remove(permissionsToRevoke);

    const revokedAuthorities = authorities
      .filter((a) => permissionsToRevoke.some((p) => p.authorityId === a.id))
      .map((a) => a.authorityName);

    this.logger.log(
      `권한 회수 완료: 사용자=${usersId}, 회수=[${revokedAuthorities.join(', ')}]`,
    );

    // 권한 변경 시 토큰 갱신 플래그 설정
    await this.redisService.setTokenRefreshFlag(usersId);

    return {
      revokedCount: permissionsToRevoke.length,
      revokedAuthorities,
      message: `${permissionsToRevoke.length}개의 권한이 회수되었습니다`,
    };
  }

  /**
   * 사용자 부서 권한 조회
   */
  async setDeptPermissions(
    userId: string,
    deptIds: string[],
  ): Promise<{ deptIds: string[]; count: number }> {
    const user = await this.userRepository.findOne({ where: { id: userId } });
    if (!user) {
      throw new BusinessException(
        ResponseCode.ADMIN_DEPT_PERMISSION_USER_NOT_FOUND,
        undefined,
        HttpStatus.NOT_FOUND,
      );
    }

    // deptIds 유효성 검증
    if (deptIds.length > 0) {
      const depts = await this.deptRepository.find({ where: { id: In(deptIds) } });
      if (depts.length !== deptIds.length) {
        throw new BusinessException(
          ResponseCode.ADMIN_DEPT_PERMISSION_DEPT_NOT_FOUND,
          undefined,
          HttpStatus.NOT_FOUND,
        );
      }
    }

    // 기존 권한 전체 삭제 후 새 목록으로 교체
    await this.deptPermissionRepository.delete({ usersId: userId });

    if (deptIds.length > 0) {
      const newPermissions = deptIds.map((deptId) =>
        this.deptPermissionRepository.create({ usersId: userId, deptId }),
      );
      await this.deptPermissionRepository.save(newPermissions);
    }

    this.logger.log(
      `부서 권한 설정: 사용자=${userId}, 부서=[${deptIds.join(', ')}]`,
    );

    // 부서 권한 변경 시 토큰 갱신 플래그 설정
    await this.redisService.setTokenRefreshFlag(userId);

    return { deptIds, count: deptIds.length };
  }

  async getUserDeptPermissions(
    userId: string,
  ): Promise<{ data: UserDeptPermissionDto[] }> {
    const user = await this.userRepository.findOne({
      where: { id: userId },
    });
    if (!user) {
      throw new BusinessException(
        ResponseCode.ADMIN_DEPT_PERMISSION_USER_NOT_FOUND,
        undefined,
        HttpStatus.NOT_FOUND,
      );
    }

    const permissions = await this.deptPermissionRepository.find({
      where: { usersId: userId },
      relations: ['dept'],
      order: { createdAt: 'ASC' },
    });

    return {
      data: permissions.map((p) => ({
        id: p.id,
        deptId: p.deptId,
        deptName: p.dept.deptName,
        createdAt: p.createdAt,
      })),
    };
  }

  /**
   * Story 3.5: 권한 목록 조회
   */
  async getAuthorityList(): Promise<{
    data: { id: string; authorityName: AuthorityType; createdAt: Date }[];
  }> {
    const authorities = await this.authorityRepository.find({
      order: { createdAt: 'ASC' },
    });

    return {
      data: authorities.map((auth) => ({
        id: auth.id,
        authorityName: auth.authorityName,
        createdAt: auth.createdAt,
      })),
    };
  }
}
