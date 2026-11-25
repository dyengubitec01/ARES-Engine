import { registerAs } from '@nestjs/config';

export default registerAs('department', () => ({
  publicDeptIds: (process.env.PUBLIC_DEPT_IDS || '')
    .split(',')
    .map((s) => s.trim())
    .filter((s) => s.length > 0),
}));
