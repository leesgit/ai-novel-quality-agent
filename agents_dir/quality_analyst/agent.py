"""ADK Web UI 진입점 — `adk web agents_dir` 가 발견하는 root_agent.

QualityAnalyst(Gemini + Phoenix MCP)를 노출한다. 심사자/사용자가
http://localhost:8000 에서 이 에이전트와 대화하며 영상 평가 품질을 진단받는다.

전제: 프로젝트 루트가 PYTHONPATH 에 있어야 adk 패키지가 import 된다
(serve_demo.sh가 루트에서 실행).
"""
from __future__ import annotations

import os
from pathlib import Path

# .env 로드 (GOOGLE_API_KEY 등)
_env = Path(__file__).resolve().parents[2] / ".env"
if _env.exists():
    for _line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())
os.environ.setdefault("PHOENIX_BASE_URL", "http://localhost:6006")

from adk.agents.analyst import build_quality_analyst

# adk web 이 찾는 진입점 변수명: root_agent
root_agent = build_quality_analyst()
