# AI Video Quality Agent

> An autonomous agent that monitors and diagnoses AI-generated video quality,
> powered by **Gemini** and **Arize Phoenix (MCP)**.
>
> Submission for the **Google Cloud Rapid Agent Hackathon** — Arize track.

**🔴 Live demo:** [agent.chmonst.com](https://agent.chmonst.com) — pick `quality_analyst`,
then ask *"Which scene is stuck at a low score, and what should I fix first?"*
The agent calls the Phoenix MCP server live and diagnoses it.

---

## The Problem

AI video pipelines produce hundreds of scene evaluations. When quality drops,
it's nearly impossible to manually trace *which* scene regressed and *why*.
A five-expert review panel (Director / DP / Colorist / Continuity / Editor)
scores every scene — but those scores scatter across files with no observability,
and continuity is judged subjectively with nothing to check it against.

## What It Does

This agent turns scattered evaluations into an **observable, diagnosable** system:

1. **Ingest** — each scene evaluation is logged to Phoenix as an OpenInference
   trace: a `CHAIN` span per scene, five `LLM` child spans (one per expert),
   plus per-expert score annotations. **Continuity is also *measured*** —
   deterministic metrics (`subject_consistency` via dHash, `palette_stability`
   via RGB histogram) are **computed on real adjacent frames** shipped in
   [`assets/frames/`](assets/frames) (not hard-coded) and logged beside the
   expert scores as a separate `CODE` annotation. See
   [docs/08_CONTINUITY_METRICS.md](docs/08_CONTINUITY_METRICS.md).
2. **Diagnose** — `QualityAnalyst` (Gemini) connects to Phoenix via the
   **`@arizeai/phoenix-mcp`** server and autonomously queries traces/spans to
   find quality-regression patterns (e.g. *"scene 03 stalls at 6/10 on
   character_consistency across 3 iterations"*). It **cross-checks** the
   subjective scores against the deterministic continuity metrics on the same
   span — measured drift confirms a real defect; a gap suggests judging variance.
3. **Prioritize** — the agent proposes which scene to fix first and how.

The agent doesn't just chat — it **calls MCP tools** (`list-projects`,
`list-traces`, `get-spans`, `get-span-annotations`) and reasons over real data.

## Architecture

```
Scene evaluations
  └─[phoenix_ingest.py / OTLP]→ Phoenix (observability)
                                   ▲
                                   │ @arizeai/phoenix-mcp (Model Context Protocol)
                                   │
        QualityAnalyst (Gemini, Google ADK) ── autonomous query + diagnosis
```

- **Google ADK** (`google-adk`) — agent framework. ADK ships as part of
  [**Vertex AI Agent Builder**](https://cloud.google.com/agent-builder/agent-development-kit/overview);
  `McpToolset` connects the partner MCP server.
- **Gemini** (`gemini-2.5-flash`) — the agent's reasoning backbone. Runs on the
  free Google AI Studio tier by default; set `GCP_PROJECT_ID` to route it
  through **Vertex AI** instead (see [`adk/config.py`](adk/config.py)).
- **Arize Phoenix** — LLM observability; **partner MCP integration (required)**
- **OpenInference** — semantic conventions for spans

## Quick Start (free, local)

```bash
# 1) Two isolated venvs (opentelemetry versions differ between ADK and Phoenix)
python3.11 -m venv .venv-adk     && .venv-adk/bin/pip install -r requirements-adk.txt
python3.11 -m venv .venv-phoenix && .venv-phoenix/bin/pip install -r requirements-phoenix.txt

# 2) Gemini API key (free): https://aistudio.google.com/apikey
cp .env.example .env   # then put your GOOGLE_API_KEY in .env

# 3) One command: Phoenix + mock data + agent Web UI
./scripts/serve_demo.sh
#   → http://localhost:8000  → pick "quality_analyst" → ask it to diagnose
```

Or run the headless diagnosis demo:

```bash
.venv-adk/bin/python -m adk.demo_analyst
```

See [docs/HOSTING.md](docs/HOSTING.md) for hosting details (local + Cloud Run).

## Verify

```bash
.venv-phoenix/bin/python verify/test_phoenix_ingest.py   # ingest logic
```

## Project Layout

```
adk/
├── config.py             # Vertex/GenAI model config (free GenAI mode by default)
├── phoenix_ingest.py     # evaluations → Phoenix OTLP spans + annotations
├── continuity_metrics.py # deterministic continuity metrics (dHash + RGB hist)
├── demo_analyst.py       # headless diagnosis demo
├── agents/analyst.py     # QualityAnalyst (Gemini + Phoenix MCP toolset)
└── tools/phoenix_mcp.py  # @arizeai/phoenix-mcp connection (McpToolset)
agents_dir/quality_analyst/agent.py   # `adk web` entry point
```

## License

[Apache-2.0](LICENSE) © 2026 Byeongchang Lee
