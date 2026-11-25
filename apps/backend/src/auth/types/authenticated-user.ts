import { AuthorityType } from '../../common/enums';

/**
 * JwtStrategy.validate 가 req.user 에 주입하는 인증된 사용자 정보.
 * 모든 컨트롤러는 이 타입을 단일 소스로 사용 (`@CurrentUser() user: AuthenticatedUser`).
 */
export interface AuthenticatedUser {
  userId: string;
  email: string;
  name: string;
  authorities: AuthorityType[];
  jobTitle: string | null;
  department: string | null;
  authDeptId: string | null;
  deptPermissions: string[];
}
