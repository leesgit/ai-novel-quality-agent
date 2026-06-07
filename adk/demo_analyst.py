"""QualityAnalyst 데모 — Phoenix에 적재된 평가를 에이전트가 실제로 진단 (해커톤 핵심 장면).

흐름:
  1. (사전) Phoenix 서버 가동 + mock 평가 적재되어 있어야 함
  2. QualityAnalyst(Gemini + phoenix-mcp)를 실행
  3. 에이전트가 phoenix-mcp 도구로 trace/span을 조회 → 품질 저하 패턴 진단
  4. 기대: "03_cliffhanger가 character_consistency에서 반복 정체" 를 스스로 발견

무료 GenAI 모드 (GOOGLE_API_KEY, Vertex 아님 → GCP 과금 없음).

사용:
    .venv-adk/bin/python -m adk.demo_analyst
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path


def _load_env() -> None:
    env = Path(__file__).resolve().parent.parent / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


async def _run() -> None:
    _load_env()
    os.environ.setdefault("PHOENIX_BASE_URL", "http://localhost:6006")

    from google.adk.runners import InMemoryRunner
    from google.genai import types

    from adk.agents.analyst import build_quality_analyst

    analyst = build_quality_analyst()
    runner = InMemoryRunner(agent=analyst, app_name="ai-novel-analyst")
    session = await runner.session_service.create_session(
        app_name="ai-novel-analyst", user_id="local",
    )

    prompt = (
        "Phoenix 프로젝트 'ai-novel-quality'의 평가 trace를 조회해라. "
        "list-projects로 프로젝트를 찾고, list-traces/get-spans로 씬별 점수를 분석해서 "
        "어느 씬이 어떤 평가 항목에서 반복적으로 품질이 낮은지 진단하고, "
        "개선 우선순위를 제안하라. 실제 조회한 데이터에만 근거하라."
    )
    msg = types.Content(role="user", parts=[types.Part(text=prompt)])

    print("=" * 60)
    print("QualityAnalyst 진단 시작 (Gemini + phoenix-mcp)")
    print("=" * 60)
    async for event in runner.run_async(
        user_id="local", session_id=session.id, new_message=msg
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "text", None):
                    print(f"\n[{event.author}]\n{part.text}")
                if getattr(part, "function_call", None):
                    print(f"  🔧 tool 호출: {part.function_call.name}")


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
