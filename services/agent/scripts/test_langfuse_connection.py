"""
LangFuse 실제 연결 테스트 스크립트.

사용법:
    1. .env 파일에 LangFuse 키 설정
    2. python scripts/test_langfuse_connection.py

필수 환경변수:
    - LANGFUSE_PUBLIC_KEY
    - LANGFUSE_SECRET_KEY
    - LANGFUSE_HOST (선택, 기본값: https://cloud.langfuse.com)
    - LLM 설정 (OPENAI_API_KEY 또는 다른 provider)
"""

import asyncio
import os
import sys

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()


def check_langfuse_config() -> bool:
    """LangFuse 설정 확인."""
    from app.core.config import settings

    print("=" * 60)
    print("LangFuse 설정 확인")
    print("=" * 60)

    public_key = settings.LANGFUSE_PUBLIC_KEY
    secret_key = settings.LANGFUSE_SECRET_KEY
    host = settings.LANGFUSE_HOST

    print(f"LANGFUSE_PUBLIC_KEY: {'✅ 설정됨' if public_key else '❌ 미설정'}")
    print(f"LANGFUSE_SECRET_KEY: {'✅ 설정됨' if secret_key else '❌ 미설정'}")
    print(f"LANGFUSE_HOST: {host}")
    print(f"langfuse_enabled: {settings.langfuse_enabled}")
    print()

    if not settings.langfuse_enabled:
        print("❌ LangFuse가 비활성화 상태입니다.")
        print("   .env 파일에 다음 환경변수를 설정하세요:")
        print("   LANGFUSE_PUBLIC_KEY=pk-lf-...")
        print("   LANGFUSE_SECRET_KEY=sk-lf-...")
        return False

    return True


def test_tracing_manager() -> bool:
    """TracingManager 초기화 테스트."""
    from app.core.tracing import TracingManager

    print("=" * 60)
    print("TracingManager 테스트")
    print("=" * 60)

    manager = TracingManager()
    manager.initialize()

    print(f"TracingManager initialized: {manager._initialized}")
    print(f"TracingManager enabled: {manager.enabled}")

    if not manager.enabled:
        print("❌ TracingManager가 비활성화 상태입니다.")
        return False

    # 콜백 핸들러 생성 테스트
    handler = manager.get_callback_handler()

    if handler:
        print(f"✅ CallbackHandler 생성 성공: {type(handler).__name__}")
    else:
        print("❌ CallbackHandler 생성 실패")
        return False

    print()
    return True


async def test_llm_with_tracing() -> bool:
    """LLM 호출과 함께 LangFuse 추적 테스트."""
    from langchain_core.messages import HumanMessage

    from app.core.llm_factory import LLMFactory
    from app.core.tracing import tracing

    print("=" * 60)
    print("LLM + LangFuse 추적 테스트")
    print("=" * 60)

    factory = LLMFactory()

    # 사용 가능한 역할 확인
    print(f"등록된 역할: {list(factory._models.keys())}")

    if not factory._models:
        print("❌ 등록된 LLM 모델이 없습니다.")
        print("   .env 파일에 LLM 설정을 확인하세요.")
        return False

    # 첫 번째 역할로 테스트
    role = next(iter(factory._models.keys()))
    print(f"테스트 역할: {role}")

    # 콜백 생성
    callbacks = tracing.get_callbacks(
        session_id="integration-test-session",
        user_id="test-user",
        trace_name=f"test_llm_{role}",
        request_type="test",
        metadata={"test": True, "script": "test_langfuse_connection.py"},
    )

    print(f"콜백 핸들러 수: {len(callbacks)}")

    if not callbacks:
        print("⚠️ 콜백 핸들러가 없습니다 (추적이 비활성화됨)")

    # LLM 호출
    messages = [HumanMessage(content="Say 'Hello LangFuse!' in exactly 3 words.")]

    try:
        print("\n--- invoke 테스트 ---")
        response = await factory.invoke_with_failover(
            role=role,
            messages=messages,
            session_id="invoke-test-session",
            user_id="test-user",
            request_type="invoke-test",
            trace_metadata={"method": "invoke"},
        )
        print(f"✅ invoke 응답: {response.content[:100]}...")

        print("\n--- stream 테스트 ---")
        chunks = []
        async for chunk in factory.stream_with_failover(
            role=role,
            messages=messages,
            session_id="stream-test-session",
            user_id="test-user",
            request_type="stream-test",
            trace_metadata={"method": "stream"},
        ):
            chunks.append(chunk.content)
            print(f"  청크: {chunk.content}", end="", flush=True)

        print()
        print(f"✅ stream 완료 (총 {len(chunks)}개 청크)")

    except Exception as e:
        print(f"❌ LLM 호출 실패: {e}")
        return False

    print()
    print("=" * 60)
    print("✅ 모든 테스트 통과!")
    print()
    print("LangFuse 대시보드에서 trace를 확인하세요:")
    print("  https://cloud.langfuse.com")
    print()
    print("확인할 세션:")
    print("  - integration-test-session")
    print("  - invoke-test-session")
    print("  - stream-test-session")
    print("=" * 60)

    return True


async def main() -> None:
    """메인 실행."""
    print("\n🔍 LangFuse 연결 테스트 시작\n")

    # 1. 설정 확인
    if not check_langfuse_config():
        sys.exit(1)

    # 2. TracingManager 테스트
    if not test_tracing_manager():
        sys.exit(1)

    # 3. LLM + 추적 테스트
    if not await test_llm_with_tracing():
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
