"""Kafka 클라이언트 모듈"""
# 순환 참조 방지를 위해 lazy import 사용
# 필요할 때만 import하도록 변경

__all__ = [
    "KafkaProducer",
    "KafkaConsumerWrapper",
]

def __getattr__(name):
    """Lazy import를 위한 함수"""
    if name == "KafkaProducer":
        from .producer import KafkaProducer
        return KafkaProducer
    elif name == "KafkaConsumerWrapper":
        from .consumer import KafkaConsumerWrapper
        return KafkaConsumerWrapper
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")




