# -*- coding: utf-8 -*-
"""그래프 빌드 호스트 네트워크 점검 — 이 서버가 사내 DB/Qdrant/임베딩API에 도달하나.
KT Cloud GPU 서버 등 새 빌드 호스트 후보에서 실행. stdlib만 사용(의존성 0).

  python3 check_connectivity.py
"""
import socket

# 그래프 빌드가 읽고/호출하는 사내 엔드포인트
TARGETS = [
    ("localhost", 5432, "PostgreSQL (청크 읽기)"),
    ("localhost", 6333, "Qdrant (엔티티벡터)"),
    ("localhost", 4000, "BGE-M3 (임베딩 API)"),
]


def main():
    print("=== 빌드 호스트 → 사내 데이터스토어 도달성 점검 ===")
    ok = 0
    for host, port, name in TARGETS:
        try:
            ip = socket.gethostbyname(host)            # ① DNS
        except Exception as e:
            print(f"[DNS 실패]   {name:22} {host} -> {e}")
            continue
        try:
            socket.create_connection((host, port), timeout=5).close()  # ② TCP
            print(f"[OK]         {name:22} {host}:{port} (->{ip}) 도달됨")
            ok += 1
        except Exception as e:
            print(f"[연결 실패]  {name:22} {host}:{port} (->{ip}) {type(e).__name__}: {e}")
    print(f"\n결과: {ok}/{len(TARGETS)} 도달. "
          + ("모두 OK → 이 서버에서 빌드 가능(네트워크 측면)."
             if ok == len(TARGETS) else
             "일부/전부 실패 → 이 서버에선 빌드 불가(라우팅 필요) 또는 다른 호스트."))


if __name__ == "__main__":
    main()
