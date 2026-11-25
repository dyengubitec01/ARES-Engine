import { registerAs } from '@nestjs/config';

export default registerAs('database', () => ({
  host: process.env.DATABASE_HOST || 'localhost',
  port: parseInt(process.env.DATABASE_PORT || '5432', 10),
  username: process.env.DATABASE_USERNAME || 'postgres',
  password: process.env.DATABASE_PW || '1234',
  database: process.env.DATABASE_NAME || 'backend',
  schema: process.env.DATABASE_SCHEMA || 'rag',
}));
