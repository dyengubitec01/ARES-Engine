"""Kafka 컨슈머"""
import logging
import json
from typing import Callable, Optional

# kafka-python 라이브러리 import (로컬 패키지 이름을 kafka_client로 변경하여 충돌 해결)
from kafka import KafkaConsumer as KafkaConsumerBase
from kafka.structs import TopicPartition, OffsetAndMetadata
from kafka.errors import KafkaError

from config import settings

logger = logging.getLogger(__name__)


class KafkaConsumerWrapper:
    """Kafka 컨슈머 래퍼"""
    
    def __init__(
        self,
        topic: str,
        group_id: Optional[str] = None,
        auto_offset_reset: str = 'earliest'  # 'earliest': 처음부터 읽기, 'latest': 새 메시지만 읽기
    ):
        self.topic = topic
        bootstrap_servers = settings.kafka_bootstrap_servers.split(",")
        consumer_group = group_id or settings.kafka_consumer_group
        
        logger.info(
            f"Kafka Consumer 초기화: topic={topic}, "
            f"bootstrap_servers={bootstrap_servers}, "
            f"group_id={consumer_group}, "
            f"auto_offset_reset={auto_offset_reset}"
        )
        
        kafka_config = {
            'bootstrap_servers': bootstrap_servers,
            'group_id': consumer_group,
            'value_deserializer': lambda m: json.loads(m.decode('utf-8')),
            'key_deserializer': lambda k: k.decode('utf-8') if k else None,
            'auto_offset_reset': auto_offset_reset,
            'enable_auto_commit': False,
            'max_poll_interval_ms': 300000,  # 5분
            'max_poll_records': 1,
            'session_timeout_ms': 60000,
        }
        
        # SASL 인증 설정 (운영 환경)
        if settings.kafka_security_protocol != "PLAINTEXT":
            kafka_config['security_protocol'] = settings.kafka_security_protocol
            kafka_config['sasl_mechanism'] = settings.kafka_sasl_mechanism
            # SCRAM 메커니즘에서는 sasl_plain_* 대신 일반 키 사용
            kafka_config['sasl_plain_username'] = settings.kafka_sasl_username
            kafka_config['sasl_plain_password'] = settings.kafka_sasl_password
        
        self.consumer = KafkaConsumerBase(topic, **kafka_config)
        
        logger.info(f"Kafka Consumer 초기화 완료: topic={topic}")

    def poll(self, timeout_ms: int = 500, max_records: int = 1):
        """poll 래퍼"""
        return self.consumer.poll(timeout_ms=timeout_ms, max_records=max_records)
    
    def end_offsets(self, partitions):
        """end_offsets 래퍼"""
        return self.consumer.end_offsets(partitions)
    
    def get_pending_count(self, last_record=None) -> int:
        """대기 중인 메시지 개수 확인 (할당된 파티션만)
        
        Args:
            last_record: 방금 poll한 레코드 (더 정확한 계산을 위해)
        """
        try:
            # 할당된 파티션 가져오기
            assigned = self.consumer.assignment()
            if not assigned:
                return 0
            
            total_lag = 0
            for tp in assigned:
                # 마지막 오프셋
                end_offsets = self.consumer.end_offsets([tp])
                end_offset = end_offsets.get(tp, 0)
                
                # 방금 읽은 레코드가 있으면 그 다음 offset 기준으로 계산
                if last_record and last_record.partition == tp.partition:
                    next_offset = last_record.offset + 1
                    lag = end_offset - next_offset
                else:
                    # 현재 위치 (다음 읽을 offset)
                    position = self.consumer.position(tp)
                    lag = end_offset - position
                
                total_lag += max(0, lag)
            
            return total_lag
        except Exception as e:
            logger.error(f"대기 메시지 개수 확인 실패: {e}")
            return 0
    
    def get_total_pending_count(self, last_record=None) -> int:
        """토픽 전체 파티션의 대기 중인 메시지 개수 확인 (모든 파티션 합산)
        
        Args:
            last_record: 방금 poll한 레코드 (더 정확한 계산을 위해)
        """
        try:
            # 토픽의 모든 파티션 정보 가져오기
            partitions = self.consumer.partitions_for_topic(self.topic)
            if not partitions:
                return 0
            
            # 모든 파티션의 TopicPartition 객체 생성
            all_partitions = [TopicPartition(self.topic, p) for p in partitions]
            
            # 모든 파티션의 끝 오프셋 가져오기
            end_offsets = self.consumer.end_offsets(all_partitions)
            
            total_lag = 0
            for tp in all_partitions:
                end_offset = end_offsets.get(tp, 0)
                
                # 방금 읽은 레코드가 해당 파티션이면 그 다음 offset 기준으로 계산
                if last_record and last_record.partition == tp.partition:
                    next_offset = last_record.offset + 1
                    lag = end_offset - next_offset
                else:
                    # 현재 컨슈머 그룹의 커밋된 오프셋 가져오기
                    try:
                        committed = self.consumer.committed(tp)
                        current_offset = committed if committed is not None else 0
                    except Exception:
                        # 할당되지 않은 파티션은 committed() 조회 실패 가능
                        # 이 경우 end_offset을 그대로 사용 (전체 메시지 수)
                        current_offset = 0
                    
                    lag = end_offset - current_offset
                
                total_lag += max(0, lag)
            
            return total_lag
        except Exception as e:
            logger.error(f"전체 파티션 대기 메시지 개수 확인 실패: {e}")
            return 0

    def commit_offsets(self, records):
        """
        명시적 커밋 (records: ConsumerRecord 또는 Iterable[ConsumerRecord])
        leader_epoch 인자를 포함해 OffsetAndMetadata 생성
        """
        if not records:
            return
        if not isinstance(records, (list, tuple)):
            records = [records]

        offsets = {}
        for rec in records:
            tp = TopicPartition(rec.topic, rec.partition)
            offsets[tp] = OffsetAndMetadata(rec.offset + 1, "", -1)  # commit next offset

        if offsets:
            self.consumer.commit(offsets=offsets)
    
    def close(self):
        """컨슈머 종료"""
        self.consumer.close()

