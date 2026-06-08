"""평가 결과 → Phoenix trace/annotation 적재기 (해커톤 A안).

5인 전문가 영상 평가를 Phoenix에 OpenInference span으로 기록한다:
    씬 평가 1회 = CHAIN span (scene+iteration)
      └ 5× LLM span (감독/DP/컬러/컨티/편집) — 각자 점수
    + 집계 점수를 span annotation으로 부착

이 스크립트는 phoenix 패키지가 필요하므로 .venv-phoenix 에서 실행한다
(ADK와 opentelemetry 버전 충돌 회피 — venv 분리). 적재(write)는 OTLP로,
조회(read)는 ADK 에이전트가 phoenix-mcp로 한다.

사용:
    PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006 \
      .venv-phoenix/bin/python -m adk.phoenix_ingest --mock
    # 또는 실제 평가 리포트 디렉토리 적재:
    .venv-phoenix/bin/python -m adk.phoenix_ingest --reports path/to/reports
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from opentelemetry import trace as otel_trace
from opentelemetry.trace import Status, StatusCode
from phoenix.client import Client
from phoenix.otel import SpanAttributes, register

PROJECT_NAME = "ai-novel-quality"

# Repo root (one level above adk/).
ROOT = Path(__file__).resolve().parent.parent

# 5인 전문가가 담당하는 평가 항목 (rubric.md 와 동일)
EXPERTS = {
    "Director": ["prompt_adherence", "composition_camera", "emotional_impact"],
    "DP": ["style_unity", "lighting"],
    "Colorist": ["palette_stability", "timing_pacing"],
    "ContinuitySupervisor": [
        "character_consistency", "location_consistency", "inter_scene_continuity"
    ],
    "Editor": ["motion_naturalness", "defect_free"],
}


# Sample real frames shipped in the repo (resized stills from an actual
# generated trailer). The deterministic continuity metric is MEASURED on these
# adjacent frames, not hard-coded — so "subjective score vs measured drift" is
# a real cross-check, not mock-vs-mock.
FRAMES_DIR = ROOT / "assets" / "frames"
SCENE_FRAMES = {
    "01_grab": "01_ambush.png",
    "02_reveal": "02_creature.png",
    "03_cliffhanger": "03_bait.png",
}


def _measured_continuity(scene: str) -> dict:
    """Measure continuity for a scene vs its predecessor on real frames.

    Uses adk.continuity_metrics on the shipped sample frames. Falls back to an
    empty dict (graceful) if PIL or the frames are unavailable — the metric is
    a signal, never a required field. The first scene has no predecessor.
    """
    from adk import continuity_metrics

    order = list(SCENE_FRAMES)
    idx = order.index(scene) if scene in order else -1
    if idx <= 0:
        return {}  # first scene (or unknown) has no adjacent predecessor
    prev_img = FRAMES_DIR / SCENE_FRAMES[order[idx - 1]]
    curr_img = FRAMES_DIR / SCENE_FRAMES[scene]
    summary = continuity_metrics.metrics_summary(prev_img, curr_img)
    return {
        k: summary[k]
        for k in ("subject_consistency", "palette_stability")
        if summary.get(k) is not None
    }


def _mock_evaluations() -> list[dict]:
    """씬별·iteration별 평가. 전문가 점수는 합성(개선 추이)이나,
    **continuity 지표는 실제 프레임에서 측정**한다 (mock 아님).

    한 씬(03_cliffhanger)이 character_consistency에서 반복 정체하는 패턴을
    심어 QualityAnalyst가 진단할 거리를 만든다. 측정된 continuity는 그 주관
    점수와 교차검증 대상이 된다.
    """
    scenes = ["01_grab", "02_reveal", "03_cliffhanger"]
    evals: list[dict] = []
    for scene in scenes:
        # iteration 간 프레임은 동일하므로 측정값도 동일 (한 번만 계산)
        measured = _measured_continuity(scene)
        for it in range(1, 4):
            base = 62 + it * 8  # 70 → 78 → 86
            scores = {
                "prompt_adherence": min(10, 6 + it),
                "composition_camera": min(10, 7 + it),
                "emotional_impact": min(10, 6 + it),
                "style_unity": min(10, 7 + it),
                "lighting": min(10, 7 + it),
                "palette_stability": min(10, 8 + it),
                "timing_pacing": min(10, 6 + it),
                # 03_cliffhanger는 일관성 정체 (의도적 약점)
                "character_consistency": 6 if scene == "03_cliffhanger" else min(10, 7 + it),
                "location_consistency": min(10, 8 + it),
                "inter_scene_continuity": 6 if scene == "03_cliffhanger" else min(10, 7 + it),
                "motion_naturalness": min(10, 6 + it),
                "defect_free": min(10, 8 + it),
            }
            total = base if scene != "03_cliffhanger" else base - 8
            evals.append({
                "scene_id": scene,
                "iteration": it,
                "scores": scores,
                "continuity": measured,  # MEASURED on real frames (may be {} for scene 1)
                "total_normalized": float(min(95, total)),
                "verdict": "PASS" if total >= 85 else "REVISE",
            })
    return evals


def _expert_score(scores: dict, items: list[str]) -> float:
    vals = [scores[i] for i in items if i in scores]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


# Continuity metric keys we expect in an evaluation's optional `continuity` block.
CONTINUITY_KEYS = ("subject_consistency", "palette_stability")
CONTINUITY_ALERT_THRESHOLD = 0.85


def _continuity_attributes(cont: dict) -> dict:
    """Span attributes for the deterministic continuity metrics.

    Empty dict when no continuity data is present (graceful — the metric is a
    signal, not a required field)."""
    attrs: dict = {}
    alert = False
    for key in CONTINUITY_KEYS:
        val = cont.get(key)
        if val is None:
            continue
        attrs[f"continuity.{key}"] = float(val)
        if val < CONTINUITY_ALERT_THRESHOLD:
            alert = True
    if attrs:
        attrs["continuity.alert"] = alert
    return attrs


def ingest(evaluations: list[dict], *, endpoint: str, project_name: str = PROJECT_NAME) -> dict:
    """평가 리스트를 Phoenix에 span으로 적재.

    반환: {"expert": [...], "continuity": [...]} — 두 종류의 annotation 행.
    expert는 LLM 전문가 점수, continuity는 결정론적 정량 지표(annotator_kind='CODE').

    멱등성: Phoenix는 OTLP append 모델이라 재실행 시 trace가 누적된다.
    깨끗한 재실행이 필요하면 호출 측에서 project_name에 고유 suffix를 준다.
    """
    tracer_provider = register(project_name=project_name, endpoint=f"{endpoint}/v1/traces")
    tracer = otel_trace.get_tracer(__name__)

    annotation_rows: list[dict] = []
    metric_rows: list[dict] = []

    for ev in evaluations:
        scene, it = ev["scene_id"], ev["iteration"]
        cont = ev.get("continuity") or {}
        cont_attrs = _continuity_attributes(cont)
        with tracer.start_as_current_span(
            f"evaluate:{scene}#iter{it}",
            attributes={
                SpanAttributes.OPENINFERENCE_SPAN_KIND: "CHAIN",
                SpanAttributes.INPUT_VALUE: f"{scene} iteration {it}",
                "scene.id": scene,
                "scene.iteration": it,
                "scene.total_score": ev["total_normalized"],
                "scene.verdict": ev["verdict"],
                **cont_attrs,
            },
        ) as parent:
            parent.set_status(Status(StatusCode.OK))
            # 항목별 점수가 없으면(실데이터 일부) 전문가 child span은 생략 — 총점 span만 적재
            if not ev["scores"]:
                continue
            # 5인 전문가 child span
            for expert, items in EXPERTS.items():
                # The ContinuitySupervisor span also carries the deterministic
                # continuity metrics so 'subjective score vs measured drift'
                # sits on one span for the agent to cross-check.
                extra_attrs = cont_attrs if expert == "ContinuitySupervisor" else {}
                with tracer.start_as_current_span(
                    f"{expert}:{scene}#iter{it}",
                    attributes={
                        SpanAttributes.OPENINFERENCE_SPAN_KIND: "LLM",
                        SpanAttributes.LLM_MODEL_NAME: "gemini-2.5-flash",
                        SpanAttributes.INPUT_VALUE: f"{expert} reviews {scene}",
                        SpanAttributes.OUTPUT_VALUE: json.dumps(
                            {i: ev["scores"][i] for i in items if i in ev["scores"]},
                            ensure_ascii=False),
                        "expert.role": expert,
                        "expert.score": _expert_score(ev["scores"], items),
                        **extra_attrs,
                    },
                ) as child:
                    child.set_status(Status(StatusCode.OK))
                    ctx = child.get_span_context()
                    span_id = format(ctx.span_id, "016x")
                    annotation_rows.append({
                        "span_id": span_id,
                        "label": expert,
                        "score": _expert_score(ev["scores"], items),
                    })
                    # Deterministic continuity metric as a separate annotation
                    # (annotator_kind='CODE') so it reads apart from LLM scores.
                    if expert == "ContinuitySupervisor":
                        for name, value in cont.items():
                            if value is not None:
                                metric_rows.append({
                                    "span_id": span_id,
                                    "label": name,
                                    "score": float(value),
                                })

    tracer_provider.force_flush()
    return {"expert": annotation_rows, "continuity": metric_rows}


def annotate(rows: dict | list[dict], *, endpoint: str) -> int:
    """span annotation 부착. 부착 건수 반환.

    rows가 dict이면 {"expert": [...], "continuity": [...]} 두 종류를 각각 부착한다:
      - expert_score      (annotator_kind='LLM')  : 5인 전문가 주관 점수
      - continuity_metric (annotator_kind='CODE') : 결정론적 정량 연속성 지표
    Phoenix/MCP에서 '판정(LLM) vs 측정(CODE)'을 분리 조회할 수 있다.
    (이전 호환: rows가 list이면 expert 점수만 부착)

    annotation은 span_id(전역 유일)로 부착되므로 project_name이 필요 없다.
    """
    if isinstance(rows, list):
        rows = {"expert": rows, "continuity": []}
    client = Client(base_url=endpoint)
    total = 0
    expert_rows = rows.get("expert") or []
    if expert_rows:
        client.spans.log_span_annotations_dataframe(
            dataframe=pd.DataFrame(expert_rows),
            annotation_name="expert_score",
            annotator_kind="LLM",
        )
        total += len(expert_rows)
    continuity_rows = rows.get("continuity") or []
    if continuity_rows:
        client.spans.log_span_annotations_dataframe(
            dataframe=pd.DataFrame(continuity_rows),
            annotation_name="continuity_metric",
            annotator_kind="CODE",
        )
        total += len(continuity_rows)
    return total


DEFECTS_DATASET = "confirmed-defects"


def ensure_defects_dataset(*, endpoint: str) -> bool:
    """Create the 'confirmed-defects' dataset (idempotent) so the QualityAnalyst
    can *write* its diagnosis back via the phoenix-mcp add-dataset-examples tool.

    add-dataset-examples only appends to an *existing* dataset, so the write-back
    loop needs this target to exist. Seeded with one baseline example. Returns
    True if created, False if it already existed / on failure (non-fatal)."""
    client = Client(base_url=endpoint)
    try:
        existing = {d.get("name") for d in client.datasets.list()}
    except Exception:
        existing = set()
    if DEFECTS_DATASET in existing:
        return False
    try:
        client.datasets.create_dataset(
            name=DEFECTS_DATASET,
            dataset_description=(
                "Confirmed quality defects recorded by the QualityAnalyst agent "
                "(read→diagnose→write loop). Baseline row below; the agent appends "
                "real findings via add-dataset-examples."
            ),
            examples=[{
                "input": {"scene_id": "_baseline", "dimension": "_init"},
                "output": {"verdict": "baseline", "note": "dataset initialized"},
                "metadata": {"source": "seeder"},
            }],
        )
        return True
    except Exception as exc:  # non-fatal — diagnosis still works without write-back
        print(f"  (dataset 생성 skip: {exc})")
        return False


def _load_reports(reports_dir: Path) -> list[dict]:
    """실제 평가 리포트 디렉토리에서 평가를 읽는다 (__history.json 활용).

    실제 history.json은 항목별 `scores` dict가 없고 총점 `score`만 있는 경우가 많다.
    그 경우에도 총점 span은 적재한다 (scores 없으면 전문가 child span은 생략).
    """
    out: list[dict] = []
    for hist in sorted(reports_dir.glob("*__history.json")):
        scene = hist.name.replace("__history.json", "")
        data = json.loads(hist.read_text(encoding="utf-8"))
        for entry in (data if isinstance(data, list) else []):
            score = entry.get("score")
            if score is None:
                continue  # 점수 없는 기록은 적재 가치 없음 → skip
            out.append({
                "scene_id": scene,
                "iteration": int(entry.get("iteration", len(out) + 1)),
                "scores": entry.get("scores") or {},  # 항목별 없으면 빈 dict
                "total_normalized": float(score),
                "verdict": entry.get("verdict", "REVISE"),
            })
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--mock", action="store_true", help="mock 데이터 적재")
    p.add_argument("--reports", help="실제 리포트 디렉토리 경로")
    p.add_argument("--endpoint", default="http://localhost:6006")
    p.add_argument("--project", default=PROJECT_NAME,
                   help="Phoenix 프로젝트명 (재실행 시 고유값 주면 깨끗한 분리)")
    args = p.parse_args()

    if args.reports:
        evals = _load_reports(Path(args.reports))
    else:
        evals = _mock_evaluations()

    if not evals:
        print("적재할 평가 없음")
        return 1

    rows = ingest(evals, endpoint=args.endpoint, project_name=args.project)
    time.sleep(2)  # span flush 후 annotation (span이 먼저 존재해야 함)
    n = annotate(rows, endpoint=args.endpoint)
    ensure_defects_dataset(endpoint=args.endpoint)
    print(f"✅ 적재 완료: {len(evals)}개 평가 → span, {n}개 annotation "
          f"(expert_score + continuity_metric) "
          f"(project={args.project}, endpoint={args.endpoint})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
