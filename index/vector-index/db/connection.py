"""데이터베이스 연결 관리"""
import logging
from urllib.parse import quote_plus
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from typing import Generator

from config import settings
from models.rdb_models import Base

logger = logging.getLogger(__name__)

# 데이터베이스 URL 구성
if settings.postgres_url:
    database_url = settings.postgres_url
else:
    # 비밀번호에 특수문자가 있을 경우 URL 인코딩
    encoded_password = quote_plus(settings.postgres_password)
    database_url = (
        f"postgresql://{settings.postgres_user}:{encoded_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )

# 데이터베이스 엔진 생성 (스키마 설정 포함)
engine = create_engine(
    database_url,
    pool_pre_ping=True,
    connect_args={
        "options": f"-csearch_path={settings.postgres_schema},public"
    }
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Database:
    """데이터베이스 클래스"""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def create_tables(self):
        """테이블 생성"""
        Base.metadata.create_all(bind=self.engine)
        logger.info("데이터베이스 테이블 생성 완료")


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """데이터베이스 세션 컨텍스트 매니저"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()






