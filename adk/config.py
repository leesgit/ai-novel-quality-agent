"""Vertex AI 백엔드 + 모델 설정.

ADK가 Gemini를 Vertex AI를 통해 호출하도록 환경변수를 세팅한다.
(신청서에 적은 'ADK with Vertex AI' 요건 충족)
"""
from __future__ import annotations

import os
from pathlib import Path

# Project root (one level above this file)
ROOT = Path(__file__).resolve().parent.parent

# 평가/추론 모델 — flash로 비용 절감, 정밀 평가 필요 시 pro로 교체
EVAL_MODEL = os.environ.get("ADK_EVAL_MODEL", "gemini-2.5-flash")
AGGREGATE_MODEL = os.environ.get("ADK_AGGREGATE_MODEL", "gemini-2.5-flash")


def configure_vertex() -> None:
    """ADK가 Vertex AI 백엔드로 Gemini를 호출하도록 환경변수 설정.

    GCP_PROJECT_ID가 없으면 Vertex 대신 GenAI API 키 모드로 폴백한다
    (스모크 테스트/모킹 시 프로젝트 없이도 import는 통과하도록).
    """
    project = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        os.environ["GOOGLE_CLOUD_PROJECT"] = project
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
