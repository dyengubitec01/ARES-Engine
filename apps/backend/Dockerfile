# Node.js 24.6.0 기반 이미지
FROM node:24.6.0-alpine AS builder

# 작업 디렉토리 설정
WORKDIR /app

# 패키지 파일 복사 및 의존성 설치
COPY package*.json ./
RUN npm ci

# 소스 복사 및 빌드
COPY . .
RUN npm run build

# --- Production Stage ---
FROM node:24.6.0-alpine AS production

WORKDIR /app

# 프로덕션 의존성만 설치
COPY package*.json ./
RUN npm ci --only=production

# 빌드 결과물 복사
COPY --from=builder /app/dist ./dist

# 포트 노출
EXPOSE 8080

# 환경변수 설정
ENV NODE_ENV=production

# 애플리케이션 실행 (이미 빌드된 dist 직접 실행)
CMD ["node", "dist/main.js"]
