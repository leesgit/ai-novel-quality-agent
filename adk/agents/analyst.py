"""품질 관제탑 — Phoenix MCP로 평가 이력을 교차분석하는 에이전트 (해커톤 A안 핵심).

우리 5인 전문가 평가 결과를 Phoenix에 적재한 뒤, 이 에이전트가 phoenix-mcp 도구로
과거 trace/experiment를 조회해 "어느 씬이 왜 반복적으로 품질이 떨어지는지" 진단하고
개선 우선순위를 제안한다. 이게 파트너(Arize) 슈퍼파워를 영상 파이프라인에 부여하는 부분.
"""
from __future__ import annotations

from google.adk.agents import LlmAgent

from adk.config import AGGREGATE_MODEL
from adk.tools.phoenix_mcp import build_phoenix_toolset


def build_quality_analyst() -> LlmAgent:
    """Phoenix observability를 활용하는 영상 품질 관제 에이전트."""
    return LlmAgent(
        name="QualityAnalyst",
        model=AGGREGATE_MODEL,
        description=(
            "Arize Phoenix MCP로 영상 평가 이력(trace/annotation/experiment)을 조회·교차분석해 "
            "품질 저하 패턴을 진단하고, 확정 결함을 Phoenix 데이터셋에 다시 기록하며 "
            "개선 우선순위를 제안하는 품질 관제 에이전트 (read→diagnose→write 닫힌 루프)."
        ),
        instruction=(
            "당신은 AI 영상 파이프라인의 품질 관제관이다. "
            "Phoenix MCP 도구로 다음을 수행하라:\n"
            "1. list_projects / 프로젝트의 trace·span을 조회해 씬별 평가 점수 추이를 파악한다.\n"
            "2. annotation을 두 종류로 함께 조회한다 — expert_score(전문가 주관 점수, "
            "annotator_kind='LLM')와 continuity_metric(결정론적 정량 지표, annotator_kind='CODE'). "
            "어느 차원(character_consistency 등)이 반복적으로 낮은지 찾는다.\n"
            "3. 주관 점수와 정량 지표를 교차검증한다:\n"
            "   - continuity_metric(subject_consistency/palette_stability)이 0.85 미만이고 "
            "expert의 character_consistency·inter_scene_continuity 점수도 정체 → '확정 연속성 결함'으로 "
            "분류하고 fix 우선순위 상단에 둔다.\n"
            "   - 정량 지표는 양호(≥0.85)한데 expert 점수만 낮음 → '심사 편차 의심'으로 분류해 재검토를 권고한다.\n"
            "   - 정량 지표가 낮은데 의도된 장소/시간 전환이면 alert를 면제한다.\n"
            "4. experiment 결과로 개선 루프가 정체된 씬을 식별한다.\n"
            "5. 진단을 근거로 '어느 씬을 어떤 fix로 먼저 개선할지' 우선순위를 제안한다.\n"
            "6. **진단을 Phoenix에 다시 기록한다 (read-only로 끝내지 마라):**\n"
            "   - list_datasets로 'confirmed-defects' 데이터셋이 있는지 확인한다.\n"
            "   - add_dataset_examples로 '확정 연속성 결함'으로 분류한 씬을 한 행 추가한다 — "
            "input={scene_id, dimension, iterations_stalled}, "
            "output={verdict:'confirmed_continuity_defect', recommended_fix, "
            "measured_metric, expert_score}. 데이터셋이 없으면 add_dataset_examples가 "
            "생성하도록 dataset_name='confirmed-defects'를 넘긴다.\n"
            "   - 이로써 다음 파이프라인 실행 때 회귀를 추적할 기준선이 Phoenix에 남는다.\n"
            "정량 지표는 판정이 아니라 신호다 — 최종 진단은 주관 점수와 함께 종합하라. "
            "추측 금지 — Phoenix에서 실제로 조회한 데이터에만 근거하라. "
            "데이터가 없으면 '적재된 평가 없음'이라고 보고하라. "
            "write 도구(add_dataset_examples) 호출이 실패하면 그 사실을 보고하되 진단은 계속한다."
        ),
        tools=[build_phoenix_toolset()],
        output_key="quality_diagnosis",
    )
