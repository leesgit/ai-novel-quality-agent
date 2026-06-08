"""Gemini backend + model configuration.

The QualityAnalyst agent is built on Google ADK (which ships under the
Vertex AI Agent Builder product family) and is powered by Gemini.

Two backends are supported, selected at runtime:
- **Vertex AI** (when GCP_PROJECT_ID is set) — Gemini runs as a billable
  Google Cloud product via Vertex.
- **Google AI Studio (GenAI API)** (default, no project set) — Gemini runs
  on the free GenAI tier. This is the default so the demo reproduces at zero
  cost; switch to Vertex by exporting GCP_PROJECT_ID.
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
    """Select the Gemini backend at runtime.

    If GCP_PROJECT_ID (or GOOGLE_CLOUD_PROJECT) is set, route Gemini through
    Vertex AI (a billable Google Cloud product). Otherwise the agent uses the
    free Google AI Studio GenAI API via GOOGLE_API_KEY — the default, so the
    demo runs at zero cost without a configured GCP project.
    """
    project = os.environ.get("GCP_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    if project:
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "TRUE"
        os.environ["GOOGLE_CLOUD_PROJECT"] = project
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")
