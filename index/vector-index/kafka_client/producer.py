"""Kafka 프로듀서"""
import logging
import json
from typing import Dict, Any, Optional, Union
from uuid import UUID
from tenacity import retry, stop_after_attempt, wait_exponential

# kafka-python 라이브러리 import (로컬 패키지 이름을 kafka_client로 변경하여 충돌 해결)
from kafka import KafkaProducer as KafkaProducerBase
from kafka.errors import KafkaError

from config import settings

logger = logging.getLogger(__name__)


class KafkaProducer:
    """Kafka 프로듀서 래퍼"""
    
    def __init__(self):
        kafka_config = {
            'bootstrap_servers': settings.kafka_bootstrap_servers.split(","),
            'value_serializer': lambda v: json.dumps(v, ensure_ascii=False).encode('utf-8'),
            'key_serializer': lambda k: k.encode('utf-8') if k else None,
            'acks': 'all',
            'retries': 3,
            'max_in_flight_requests_per_connection': 1,
        }
        
        # SASL 인증 설정 (운영 환경)
        if settings.kafka_security_protocol != "PLAINTEXT":
            kafka_config['security_protocol'] = settings.kafka_security_protocol
            kafka_config['sasl_mechanism'] = settings.kafka_sasl_mechanism
            # SCRAM 메커니즘에서는 sasl_plain_* 대신 일반 키 사용
            kafka_config['sasl_plain_username'] = settings.kafka_sasl_username
            kafka_config['sasl_plain_password'] = settings.kafka_sasl_password
        
        self.producer = KafkaProducerBase(**kafka_config)
        self.request_topic = settings.kafka_request_topic
        self.status_topic = settings.kafka_status_topic
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def send_embedding_request(
        self,
        job_id: Union[str, int],
        doc_content_id: Union[str, UUID],
        minio_bucket: str,
        minio_object_key: str,
        original_filename: str,
        mime_type: str,
        key: Optional[str] = None
    ) -> bool:
        """임베딩 요청 이벤트 발행"""
        try:
            job_id_str = str(job_id)
            doc_content_str = str(doc_content_id)
            payload = {
                "job_id": job_id_str,
                "doc_content_id": doc_content_str,
                "minio_bucket": minio_bucket,
                "minio_object_key": minio_object_key,
                "original_filename": original_filename,
                "mime_type": mime_type,
            }
            
            # key=None → Kafka 라운드로빈 분배 (ew-1/2/3 균등 활용)
            # job_id를 key로 쓰면 hash 충돌로 특정 파티션에만 몰려 일부 EW가 놀게 됨
            # 임베딩 작업은 job 간 순서 의존성이 없으므로 key 불필요
            kafka_key = None
            future = self.producer.send(
                self.request_topic,
                value=payload,
                key=kafka_key
            )
            
            # 전송 완료 대기
            record_metadata = future.get(timeout=10)
            logger.info(
                f"Kafka 메시지 발행 완료: topic={record_metadata.topic}, "
                f"partition={record_metadata.partition}, offset={record_metadata.offset}, "
                f"job_id={job_id}"
            )
            return True
        
        except KafkaError as e:
            logger.error(f"Kafka 메시지 발행 실패: job_id={job_id}, 에러: {e}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def send_embedding_status(
        self,
        job_id: str,  # UUID 문자열 지원
        doc_content_id: Union[str, UUID],
        status: str,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        key: Optional[str] = None
    ) -> bool:
        """임베딩 상태 이벤트 발행"""
        try:
            payload = {
                "job_id": job_id,
                "doc_content_id": str(doc_content_id),
                "status": status,
                "message": message,
                "metadata": metadata or {},
            }
            
            kafka_key = key or str(job_id)
            future = self.producer.send(
                self.status_topic,
                value=payload,
                key=kafka_key
            )
            
            # 전송 완료 대기
            record_metadata = future.get(timeout=10)
            logger.info(
                f"Kafka 상태 이벤트 발행 완료: topic={record_metadata.topic}, "
                f"status={status}, job_id={job_id}"
            )
            return True
        
        except KafkaError as e:
            logger.error(f"Kafka 상태 이벤트 발행 실패: job_id={job_id}, 에러: {e}")
            raise
    
    def flush(self):
        """프로듀서 버퍼 플러시"""
        self.producer.flush()
    
    def close(self):
        """프로듀서 종료"""
        self.producer.close()



