import uuid
from datetime import datetime
from typing import Any, Dict, List


def to_jsonable(obj: Any) -> Any:
    """재귀적으로 UUID/datetime 등을 JSON 직렬화 가능한 값으로 변환."""
    if isinstance(obj, dict):
        return {k: to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_jsonable(v) for v in obj]
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj



