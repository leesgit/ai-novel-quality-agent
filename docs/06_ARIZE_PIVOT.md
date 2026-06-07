# 06 · 해커톤 A안 — Arize Phoenix MCP 통합 피벗 설계

> **결정**: 04 문서의 A안 채택. 우리 5인 전문가 영상 평가 시스템을
> **Arize Phoenix MCP**에 연결해 **"AI 영상 품질 자동 모니터링·개선 에이전트"** 로 제출.
> **트랙**: Arize ($5,000 / $3,000 / $2,000)
> **검증 출처**: `@arizeai/phoenix-mcp` README (Phoenix monorepo, Apache-2.0), 2026-06-02 curl 확인.

---

## 1. 왜 이게 자연스러운 매핑인가 (억지 아님)

Phoenix는 LLM **observability/evaluation** 플랫폼이다. 우리 시스템은 이미 "5인 LLM 평가자가
영상을 채점하고 개선 루프를 돈다" — **본질이 LLM 평가 파이프라인**이다. Phoenix가 다루는 개념과 1:1 대응:

| 우리 시스템 | Phoenix MCP 개념 | phoenix-mcp 도구 |
|---|---|---|
| 한 씬의 평가 1회 | **trace** | Traces, Spans |
| 5인 전문가 각각의 채점 | **span + annotation** | Annotations |
| 전문가 점수/issues | **annotation (label+score)** | annotation configs |
| 개선 루프 iteration | **experiment** | Experiments (결과 pull) |
| 스토리보드 프롬프트 | **prompt** | Prompts Management (create/update/iterate) |
| 영상 평가 프로젝트 | **project/dataset** | Projects, Datasets |

→ 즉 **"우리 평가 데이터를 Phoenix에 적재하고, 에이전트가 phoenix-mcp로 그걸 조회·분석·개선 제안"** 하는 구조.
파트너 슈퍼파워(R1) = Phoenix의 observability를 영상 품질 관리에 부여.

## 2. 제출 컨셉 (실생활 문제 프레이밍 — R3/Idea 축)

> **"AI 영상 제작자는 컷이 수백 개 쌓이면 어느 씬이 왜 품질이 떨어지는지 추적 불가능하다.
> 이 에이전트는 모든 씬 평가를 Phoenix에 기록하고, 품질 저하 패턴을 자동 진단해
> 개선 액션을 제안·실행한다 — AI 영상 파이프라인의 '품질 관제탑'."**

- Beyond Chat(R3): 단순 답변이 아니라 평가 적재 → 진단 → 개선 실행 (tool 사용) ✅
- Multi-step(R4): 진단 → 우선순위 → fix 적용 → 재평가 계획·실행 ✅
- Partner MCP(R1): phoenix-mcp로 trace/annotation/experiment 조회·기록 ✅

## 3. 아키텍처 — 기존 ADK 레이어에 MCP 추가

```
ContinuityDirector (기존 ADK orchestrator)
│
├─ ExpertReviewPanel (5인) ──┐
├─ ScoreAggregator           │ 평가 결과
│                            ▼
├─ [신규] PhoenixLogger      ── phoenix-mcp: 평가를 trace+annotation으로 적재
│                            
└─ [신규] QualityAnalystAgent ── phoenix-mcp: 과거 trace/experiment 조회
                                 → "ep02 03씬이 3회째 character_consistency 정체" 같은
                                   교차 분석 → 개선 우선순위 제안 → Reviser에 전달
```

- **ADK ↔ MCP 연결**: ADK는 `MCPToolset`으로 외부 MCP 서버를 tool로 흡수한다.
  `@arizeai/phoenix-mcp`를 `npx`로 띄우고 ADK 에이전트에 toolset으로 붙인다.

```python
# adk/tools/phoenix_mcp.py — ✅ 구현 완료·검증됨 (ADK 2.1.0)
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

McpToolset(  # ⚠️ MCPToolset(대문자)은 deprecated → McpToolset
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command="npx",
            args=["-y", "@arizeai/phoenix-mcp@latest",
                  "--baseUrl", base_url, "--apiKey", api_key]),
        timeout=30,
    ),
)
# adk/agents/analyst.py: QualityAnalyst.tools = [build_phoenix_toolset()]
```

> ✅ **검증 완료 (2026-06-02)**:
> - `@arizeai/phoenix-mcp@4.0.13` npm 존재, bin=`build/index.js`, npx 실행 가능
> - ADK 2.1.0 실제 API 확인: `McpToolset` + `StdioConnectionParams(server_params=...)` (Context7 문서의 `MCPToolset`/`StdioServerParameters`는 구버전)
> - `mcp` 파이썬 패키지 추가 설치 필요 (ADK가 MCP에 별도 의존) → `.venv-adk`에 설치 완료
> - QualityAnalyst 에이전트 조립 + RALF 검증 6/6 통과
> - 🎉 **END-TO-END 실연결 성공**: 로컬 Phoenix 서버(localhost:6006) 기동 → phoenix-mcp(npx) 연결 →
>   **27개 도구 실제 로드 확인** (list-prompts/upsert-prompt/list-experiments/list-datasets/get-traces 등).
>   lazy 객체가 아니라 진짜 MCP 핸드셰이크 성공 — R1(파트너 MCP 통합) 충족 입증.

## 4.5 무료 로컬 셋업 (요금 0원)

사용자 요청: 결제 안 되는 무료 한도 내 작업. Phoenix는 **로컬 self-host로 완전 무료** (가입/API key 불필요).

```bash
# Phoenix 서버 (별도 venv — ADK와 opentelemetry 버전 충돌 격리)
python3.11 -m venv .venv-phoenix && .venv-phoenix/bin/pip install arize-phoenix
PHOENIX_WORKING_DIR="$PWD/.phoenix_data" .venv-phoenix/bin/python -m phoenix.server.main serve  # localhost:6006

# ADK 에이전트는 PHOENIX_BASE_URL만 주면 됨 (API key 불필요, 로컬)
PHOENIX_BASE_URL=http://localhost:6006 .venv-adk/bin/python -m adk.main ...
```

> ⚠️ **venv 분리 필수**: arize-phoenix가 opentelemetry를 1.42.1로 올려 google-adk(≤1.41.1)와 충돌.
> → Phoenix는 `.venv-phoenix`, ADK는 `.venv-adk`로 격리. 연결은 MCP(stdio)로만 하므로 같은 프로세스일 필요 없음.
> 제출 시 호스팅(R5)은 Phoenix Cloud 무료 티어 or Cloud Run으로 승격 가능.

## 4. 제출 요건 충족 경로

| 요건 | 충족 방법 |
|---|---|
| R1 파트너 MCP | phoenix-mcp 통합 ✅ |
| R2 Gemini/Agent Builder | ADK 에이전트 LLM = Gemini(Vertex). Agent Builder는 "ideal"이지 필수 아님 — ADK로 충족 가능하나 README 문구상 Agent Builder 권장. **구현 시 확인** |
| R5 호스팅 URL | Phoenix 인스턴스(Phoenix Cloud 무료 or Cloud Run 배포) + 에이전트 대시보드 |
| R6 오픈소스+라이선스 | repo에 LICENSE 추가 (Apache-2.0 권장, Phoenix와 동일) |
| R7 3분 영상 | "품질 관제탑" 데모: 평가 적재 → Phoenix UI에서 추적 → 에이전트 진단 → 개선 |
| R8 트랙 | Arize 선택 |
| R9 Devpost 폼 | 03 제출문 기반 작성 → **제출 전 사용자 컨펌** |

## 5. 구현 작업 분해 (D-9, 추정 공수)

| # | 작업 | 공수 | 비고 |
|---|---|---|---|
| 1 | Phoenix 인스턴스 확보 (Cloud 무료 가입 or self-host) | 0.5h | API key 발급 |
| 2 | `adk/tools/phoenix_mcp.py` — MCPToolset 연결 + 스모크 | 1.5h | Context7로 import 확인 |
| 3 | 평가 결과 → trace/annotation 적재 로직 | 2h | aggregator 출력을 Phoenix span으로 |
| 4 | `QualityAnalystAgent` — 과거 trace 교차분석 | 2h | phoenix-mcp 조회 도구 활용 |
| 5 | 호스팅 (Phoenix Cloud + 에이전트 데모 페이지) | 1.5h | R5 |
| 6 | LICENSE + README(아키텍처 다이어그램) | 1h | R6 |
| 7 | RALF 검증 (MCP 연결 모킹) | 1h | |
| 8 | 3분 데모 영상 + Devpost 폼 | 2h | R7/R9 |
|  | **합계** | **~11.5h** | 기존 ADK 자산 재활용 전제 |

## 6. 리스크

- 🟡 **Agent Builder vs ADK**: README는 Agent Builder를 "How to Build"로 권장. ADK만으로 자격이 되는지 명확치 않음 → 구현 전 해커톤 FAQ/Discord 확인 권장. (ADK도 Google Cloud 에이전트 스택이라 통과 가능성 높지만 확인 필요)
- 🟡 **Phoenix 학습 곡선**: trace/span 스키마를 우리 데이터에 맞추는 작업이 핵심 공수.
- 🟢 컨셉 정합성은 강함 — 평가 시스템 ↔ observability는 천연 매칭.

## 7. 진행 현황 (2026-06-02 업데이트)

### ✅ 완료 — 핵심 데모 end-to-end 작동
- Phoenix MCP 연결 (27 도구) — 실연결 검증
- `adk/phoenix_ingest.py` 적재기 — 94.5/100 (07 문서) — 실데이터까지 검증
- **`adk/demo_analyst.py` — QualityAnalyst가 Gemini로 phoenix-mcp 도구를 실제 호출해
  스스로 진단** 🎉:
  - `list-projects` → `list-traces` 도구 호출 (시키지 않은 자율 호출)
  - 적재된 9개 평가를 읽고 03_cliffhanger의 character_consistency·inter_scene_continuity
    6점 정체를 **정확히 진단** + 개선 우선순위 제안
  - Gemini = 무료 GenAI 모드 (GOOGLE_API_KEY, Vertex 아님 → GCP 과금 0)
  - 전체 흐름: 평가 → Phoenix 적재 → QualityAnalyst 조회·추론·진단 = 닫힘

### 다음 액션
- [ ] Agent Builder 필수 여부 확인 (Discord/FAQ) — ADK로 통과 가능성 높으나 미확인
- [ ] 호스팅(R5): Phoenix Cloud 무료 티어 or Cloud Run
- [ ] LICENSE 파일(R6) repo에 추가
- [ ] 3분 데모 영상(R7) — 위 demo_analyst 실행 화면이 핵심
- [ ] Devpost 폼(R9) — **제출 전 사용자 컨펌** (자동제출 금지)
- [ ] ⚠️ 노출된 API key 폐기·재발급 (데모 후)
