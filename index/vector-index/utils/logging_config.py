"""
로깅 설정 유틸리티
년도/월/날짜별 로그 파일 자동 생성 및 관리
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

_KST = timezone(timedelta(hours=9))


def _kst_converter(timestamp):
    return datetime.fromtimestamp(timestamp, tz=_KST).timetuple()


class DailyRotatingFileHandler(TimedRotatingFileHandler):
    """날짜별로 로그 파일을 생성하는 핸들러 (년도/월/날짜.log 구조)"""
    
    def __init__(self, base_dir: str, service_name: str):
        """
        Args:
            base_dir: 로그 베이스 디렉토리 (예: 'api/logs', 'workers/logs')
            service_name: 서비스 이름 (예: 'er', 'ew-1')
        """
        self.base_dir = Path(base_dir)
        self.service_name = service_name
        
        # 초기 로그 파일 경로 생성
        log_file = self._get_log_file_path()
        
        # 부모 클래스 초기화 (자정마다 로테이션)
        super().__init__(
            filename=str(log_file),
            when='midnight',
            interval=1,
            backupCount=0,  # 백업 파일 자동 삭제 안함 (년도/월 폴더로 관리)
            encoding='utf-8',
            utc=False
        )
    
    def _get_log_file_path(self) -> Path:
        """현재 날짜 기준 로그 파일 경로 생성"""
        now = datetime.now()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        day = now.strftime('%Y-%m-%d')
        
        # 년도/월 폴더 생성
        log_dir = self.base_dir / year / month
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 로그 파일명: {service_name}-YYYY-MM-DD.log
        return log_dir / f"{self.service_name}-{day}.log"
    
    def doRollover(self):
        """로그 로테이션 시 새로운 경로로 파일 변경"""
        if self.stream:
            self.stream.close()
            self.stream = None
        
        # 새로운 로그 파일 경로 생성
        new_log_file = self._get_log_file_path()
        self.baseFilename = str(new_log_file)
        
        # 새 파일 스트림 열기
        if not self.delay:
            self.stream = self._open()


def setup_logging(
    service_name: str,
    log_dir: str = "logs",
    level: int = logging.INFO,
    console_output: bool = True
) -> logging.Logger:
    """
    로깅 설정 초기화
    
    Args:
        service_name: 서비스 이름 (예: 'er', 'ew-1')
        log_dir: 로그 디렉토리 경로 (기본값: 'logs')
        level: 로그 레벨 (기본값: INFO)
        console_output: 콘솔 출력 여부 (기본값: True)
    
    Returns:
        설정된 root logger
    """
    # Root logger 가져오기
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 기존 핸들러 제거
    root_logger.handlers.clear()
    
    # 로그 포맷 설정 (asctime은 KST 고정)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    formatter.converter = _kst_converter
    
    # 1. 파일 핸들러 추가 (날짜별 로테이션)
    file_handler = DailyRotatingFileHandler(log_dir, service_name)
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # 2. 콘솔 핸들러 추가 (선택적)
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # 3. 외부 라이브러리 로그 레벨 조정
    logging.getLogger("kafka").setLevel(logging.WARNING)
    logging.getLogger("kafka.conn").setLevel(logging.WARNING)
    logging.getLogger("kafka.coordinator").setLevel(logging.WARNING)
    logging.getLogger("kafka.cluster").setLevel(logging.WARNING)
    
    logging.getLogger("transformers").setLevel(logging.ERROR)
    logging.getLogger("transformers.modeling_utils").setLevel(logging.ERROR)
    logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)
    logging.getLogger("transformers.configuration_utils").setLevel(logging.ERROR)
    logging.getLogger("transformers.modeling_utils").propagate = False
    
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("minio").setLevel(logging.WARNING)
    
    root_logger.info(f"로깅 초기화 완료: service={service_name}, log_dir={log_dir}")
    
    return root_logger
