"""Arize Phoenix MCP 연결 — 파트너 통합 (해커톤 R1).

@arizeai/phoenix-mcp 서버를 npx로 띄워 ADK 에이전트에 toolset으로 붙인다.
Phoenix는 LLM observability/evaluation 플랫폼 — 우리 5인 전문가 평가 데이터를
trace/annotation/experiment로 적재·조회한다.

검증(2026-06-02, ADK 2.1.0):
- MCPToolset(대문자 MCP)은 deprecated → McpToolset 사용
- StdioConnectionParams(server_params=StdioServerParameters(...)) 구조
- 연결은 lazy — 에이전트가 처음 tool을 쓸 때 npx 프로세스가 뜬다
"""
from __future__ import annotations

import os

from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters


def build_phoenix_toolset() -> McpToolset:
    """Phoenix MCP 서버에 연결하는 toolset.

    환경변수:
        PHOENIX_BASE_URL — Phoenix 인스턴스 URL (예: https://app.phoenix.arize.com)
        PHOENIX_API_KEY  — Phoenix API key

    둘 다 없으면 로컬 기본값(localhost:6006)으로 시도한다 (self-host Phoenix).
    """
    base_url = os.environ.get("PHOENIX_BASE_URL", "http://localhost:6006")
    api_key = os.environ.get("PHOENIX_API_KEY", "")

    args = ["-y", "@arizeai/phoenix-mcp@latest", "--baseUrl", base_url]
    if api_key:
        args += ["--apiKey", api_key]

    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(command="npx", args=args),
            timeout=30,
        ),
    )
