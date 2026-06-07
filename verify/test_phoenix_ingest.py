"""RALF 검증 — Phoenix 적재기 로직 (서버/네트워크 없이 순수 함수 검증).

.venv-phoenix/bin/python docs/improvements/verify/test_phoenix_ingest.py

실제 OTLP 적재(ingest/annotate)는 Phoenix 서버가 필요하므로 여기서는
순수 데이터 변환 함수(_mock_evaluations, _expert_score, _load_reports)만 검증한다.
end-to-end 적재/round-trip은 별도 수동 스모크로 확인 (07 문서에 기록).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        FAILS.append(msg)


def test_mock_has_stagnant_pattern() -> None:
    from adk.phoenix_ingest import _mock_evaluations
    evals = _mock_evaluations()
    check(len(evals) == 9, f"mock 9개 평가 (3씬×3iter), 실제 {len(evals)}")
    # 03_cliffhanger는 character_consistency 정체(=6 고정)
    cliff = [e for e in evals if e["scene_id"] == "03_cliffhanger"]
    cc = {e["scores"]["character_consistency"] for e in cliff}
    check(cc == {6}, f"cliffhanger character_consistency 정체(6)여야 함, 실제 {cc}")
    # 다른 씬은 점수가 오른다
    grab = sorted([e for e in evals if e["scene_id"] == "01_grab"], key=lambda e: e["iteration"])
    check(grab[0]["total_normalized"] < grab[-1]["total_normalized"], "01_grab 점수 상승 추이")


def test_expert_score_safe_on_missing() -> None:
    from adk.phoenix_ingest import _expert_score
    # 항목 일부 누락에도 KeyError 없이 평균
    check(_expert_score({"lighting": 8}, ["style_unity", "lighting"]) == 8.0, "누락항목 안전 평균")
    check(_expert_score({}, ["lighting"]) == 0.0, "빈 scores → 0.0")


def test_load_reports_handles_no_item_scores() -> None:
    from adk.phoenix_ingest import _load_reports
    # 실데이터 형태: score만 있고 항목별 scores 없음
    with tempfile.TemporaryDirectory() as d:
        hist = Path(d) / "01_test__history.json"
        hist.write_text(json.dumps([
            {"iteration": 1, "score": 91.8, "verdict": "PASS"},
            {"iteration": 2, "score": None},  # 점수 없는 건 skip
        ]), encoding="utf-8")
        out = _load_reports(Path(d))
    check(len(out) == 1, f"score 있는 1건만 적재, 실제 {len(out)}")
    check(out[0]["scores"] == {}, "항목별 점수 없으면 빈 dict")
    check(out[0]["total_normalized"] == 91.8, "총점 보존")


def main() -> int:
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"  ✓ {name}")
            except Exception as e:  # noqa: BLE001
                FAILS.append(f"{name} raised {type(e).__name__}: {e}")
                print(f"  ✗ {name}: {e}")
    if FAILS:
        print(f"\n❌ {len(FAILS)} 실패:")
        for f in FAILS:
            print(f"   - {f}")
        return 1
    print("\n✅ Phoenix 적재기 로직 검증 전부 통과")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
