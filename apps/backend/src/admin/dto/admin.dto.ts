import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsUUID,
  IsOptional,
  IsInt,
  IsString,
  Min,
  Max,
  IsArray,
  IsEnum,
  ArrayMinSize,
} from 'class-validator';
import { Type } from 'class-transformer';
import { AuthorityType } from '../../common/enums';

// ============================================================
// Story 3.2: 사용자 목록 조회
// ============================================================

export class UserListQueryDto {
  @ApiPropertyOptional({ description: '페이지 번호', default: 1 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  page?: number = 1;

  @ApiPropertyOptional({ description: '페이지당 항목 수', default: 20 })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number = 20;

  @ApiPropertyOptional({ description: '이름 또는 이메일 검색' })
  @IsOptional()
  @IsString()
  search?: string;
}

export class UserPermissionDto {
  @ApiProperty({ description: '권한 부여 레코드 ID (삭제 시 사용)' })
  permissionId: string;

  @ApiProperty({ description: '권한 ID' })
  authorityId: string;

  @ApiProperty({ description: '권한 이름', enum: AuthorityType })
  authorityName: AuthorityType;
}

export class UserDeptPermissionDto {
  @ApiProperty({ description: '부서 권한 매핑 ID' })
  id: string;

  @ApiProperty({ description: '부서 ID' })
  deptId: string;

  @ApiProperty({ description: '부서명' })
  deptName: string;

  @ApiProperty({ description: '생성일' })
  createdAt: Date;
}

export class UserDeptPermissionListResponseDto {
  @ApiProperty({ type: [UserDeptPermissionDto] })
  data: UserDeptPermissionDto[];
}

export class UserWithAuthoritiesDto {
  @ApiProperty({ description: '사용자 ID' })
  id: string;

  @ApiProperty({ description: '이메일' })
  email: string;

  @ApiProperty({ description: '이름' })
  name: string;

  @ApiProperty({ description: '부서', nullable: true })
  department: string | null;

  @ApiProperty({ description: '권한 목록 (이름만)', type: [String] })
  authorities: AuthorityType[];

  @ApiProperty({
    description: '권한 상세 목록 (ID 포함)',
    type: [UserPermissionDto],
  })
  permissions: UserPermissionDto[];

  @ApiProperty({
    description: '부서 권한 목록',
    type: [UserDeptPermissionDto],
  })
  deptPermissions: UserDeptPermissionDto[];

  @ApiProperty({ description: '생성일' })
  createdAt: Date;
}

export class UserListResponseDto {
  @ApiProperty({ type: [UserWithAuthoritiesDto] })
  data: UserWithAuthoritiesDto[];

  @ApiProperty({ description: '전체 사용자 수' })
  total: number;

  @ApiProperty({ description: '현재 페이지' })
  page: number;

  @ApiProperty({ description: '페이지당 항목 수' })
  limit: number;
}

// ============================================================
// Story 3.3: 권한 일괄 부여
// ============================================================

export class GrantAuthoritiesDto {
  @ApiProperty({ description: '사용자 ID' })
  @IsUUID()
  usersId: string;

  @ApiProperty({
    description: '부여할 권한 타입 배열',
    enum: AuthorityType,
    isArray: true,
    example: ['uploader', 'admin'],
  })
  @IsArray()
  @ArrayMinSize(1)
  @IsEnum(AuthorityType, { each: true })
  authorityTypes: AuthorityType[];
}

export class GrantAuthoritiesResponseDto {
  @ApiProperty({ description: '부여된 권한 수' })
  grantedCount: number;

  @ApiProperty({ description: '부여된 권한 목록', type: [String] })
  grantedAuthorities: AuthorityType[];

  @ApiProperty({ description: '이미 있던 권한 (스킵됨)', type: [String] })
  skippedAuthorities: AuthorityType[];

  @ApiProperty()
  message: string;
}

// ============================================================
// Story 3.4: 권한 회수
// ============================================================

export class RevokeAuthoritiesDto {
  @ApiProperty({ description: '사용자 ID' })
  @IsUUID()
  usersId: string;

  @ApiProperty({
    description: '회수할 권한 타입 배열',
    enum: AuthorityType,
    isArray: true,
    example: ['uploader', 'admin'],
  })
  @IsArray()
  @ArrayMinSize(1)
  @IsEnum(AuthorityType, { each: true })
  authorityTypes: AuthorityType[];
}

export class RevokeAuthoritiesResponseDto {
  @ApiProperty({ description: '회수된 권한 수' })
  revokedCount: number;

  @ApiProperty({ description: '회수된 권한 목록', type: [String] })
  revokedAuthorities: AuthorityType[];

  @ApiProperty()
  message: string;
}

// ============================================================
// 부서 권한 관리
// ============================================================

export class GrantDeptPermissionsDto {
  @ApiProperty({ description: '사용자 ID' })
  @IsUUID()
  usersId: string;

  @ApiProperty({
    description: '부여할 부서 ID 배열',
    type: [String],
    example: ['uuid-1', 'uuid-2'],
  })
  @IsArray()
  @ArrayMinSize(1)
  @IsUUID('4', { each: true })
  deptIds: string[];
}

export class GrantDeptPermissionsResponseDto {
  @ApiProperty({ description: '부여된 부서 권한 수' })
  grantedCount: number;

  @ApiProperty({ description: '부여된 부서 ID 목록', type: [String] })
  grantedDeptIds: string[];

  @ApiProperty({ description: '이미 있던 부서 (스킵됨)', type: [String] })
  skippedDeptIds: string[];

  @ApiProperty()
  message: string;
}

export class RevokeDeptPermissionsDto {
  @ApiProperty({ description: '사용자 ID' })
  @IsUUID()
  usersId: string;

  @ApiProperty({
    description: '회수할 부서 ID 배열',
    type: [String],
    example: ['uuid-1', 'uuid-2'],
  })
  @IsArray()
  @ArrayMinSize(1)
  @IsUUID('4', { each: true })
  deptIds: string[];
}

export class RevokeDeptPermissionsResponseDto {
  @ApiProperty({ description: '회수된 부서 권한 수' })
  revokedCount: number;

  @ApiProperty({ description: '회수된 부서 ID 목록', type: [String] })
  revokedDeptIds: string[];

  @ApiProperty()
  message: string;
}

// ============================================================
// 부서 권한 일괄 설정 (PUT - 덮어쓰기)
// ============================================================

export class SetDeptPermissionsDto {
  @ApiProperty({
    description: '설정할 부서 ID 배열 (빈 배열이면 전체 제거)',
    type: [String],
    example: ['uuid-1', 'uuid-2'],
  })
  @IsArray()
  @IsUUID('4', { each: true })
  deptIds: string[];
}

export class SetDeptPermissionsResponseDto {
  @ApiProperty({ description: '설정된 부서 ID 목록', type: [String] })
  deptIds: string[];

  @ApiProperty({ description: '설정된 부서 권한 수' })
  count: number;
}

// ============================================================
// Story 3.5: 권한 목록 조회
// ============================================================

export class AuthorityDto {
  @ApiProperty({ description: '권한 ID' })
  id: string;

  @ApiProperty({ description: '권한 이름', enum: AuthorityType })
  authorityName: AuthorityType;

  @ApiProperty({ description: '생성일' })
  createdAt: Date;
}

export class AuthorityListResponseDto {
  @ApiProperty({ type: [AuthorityDto] })
  data: AuthorityDto[];
}
