"""Stage base — pipeline synthesizer가 순차 실행하는 단위 stage들의 인터페이스.

각 stage는 함수:
    stage(question, ctx, chunks_db, **state) -> ctx

ctx (mutable dict, 단계 간 공유):
    필수:
        candidates  : List[int]    (retriever가 준 초기 후보)
        usages      : List[dict]   (각 stage의 LLM usage 누적)
        calls       : int          (LLM 호출 수)
    선택 (stages가 추가/소비):
        relevant_chunks : List[int]  (relevance_filter 출력)
        claims          : str        (claim_extraction 출력)
        answer          : str        (single_shot / reduce / verify 출력)
        draft           : str        (verify가 참고할 초안)

이 인터페이스로 stage를 자유 조합 가능:
    - [single_shot]                       → vector 단일 생성
    - [single_shot, verify]               → draft + verify
    - [relevance_filter, claim_extraction, reduce]  → lazy_qt 풀버전
    - [single_shot, verify, verify]       → 검증 2번 (실험용)
"""
from typing import Callable, Dict


STAGES: Dict[str, Callable] = {}


def register(name: str):
    """Stage 함수를 STAGES registry에 등록."""
    def wrap(fn):
        STAGES[name] = fn
        return fn
    return wrap
