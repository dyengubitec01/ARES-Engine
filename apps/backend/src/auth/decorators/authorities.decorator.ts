import { SetMetadata } from '@nestjs/common';
import { AuthorityType } from '../../common/enums';

export const AUTHORITIES_KEY = 'authorities';
export const Authorities = (...authorities: AuthorityType[]) =>
  SetMetadata(AUTHORITIES_KEY, authorities);
