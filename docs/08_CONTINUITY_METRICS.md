# Continuity Metrics & Rubric

Continuity is the dimension most likely to break in AI-generated video: a
subject that subtly looks like a *different identity* between adjacent scenes,
or an abrupt color/lighting shift. Subjective expert scores catch some of it,
but they scatter and drift. This document defines how we make continuity
**measurable and observable** -- a deterministic signal logged next to the
expert panel so the agent can cross-check judgement against measurement.

> Scope: this is an **evaluation/observability** rubric. It describes how to
> *score and diagnose* continuity, not how to produce video.

---

## 1. Quantitative metrics (deterministic, code-computed)

Computed by [`adk/continuity_metrics.py`](../adk/continuity_metrics.py) on
adjacent-scene frame pairs. PIL-only, no face embeddings; returns `None` and
degrades gracefully when an image or PIL is missing.

| Metric | Definition | Range | Pass threshold |
|---|---|---|---|
| `subject_consistency` | Center-ROI (middle 50% crop) difference-hash (dHash) similarity between adjacent frames = `1 - HammingDistance/64`. A perceptual hash robust to small rotation/lighting changes; measures macro identity drift of the foreground subject. | 0.0-1.0 | >= 0.85 |
| `palette_stability` | `1 - normalized-L1` distance of the two frames' RGB 24-bin (8 bins/channel) histograms. Measures color/lighting drift. | 0.0-1.0 | >= 0.85 |

**How dHash works:** the image is reduced to a 9x8 grayscale grid; comparing
each pixel with its right neighbour yields an 8x8 (64-bit) fingerprint. Two
visually similar frames produce a small Hamming distance. The ROI variant crops
the center 50% to focus the signal on the foreground subject region.

Below threshold = a signal that the subject's identity, or the scene's
color/lighting, changed sharply between adjacent scenes -- unless the change
is an intentional location/time transition, in which case the alert is ignored.

---

## 2. Qualitative dimensions (expert panel, 0-10)

| Dimension | What it judges |
|---|---|
| `character_consistency` | Does the same subject keep its appearance/identity across cuts? |
| `location_consistency` | Is the background/space consistent? |
| `inter_scene_continuity` | Are tone/color/connection smooth across cuts? |

---

## 3. Cross-validation (quantitative vs qualitative)

The deterministic metric and the subjective scores are logged on the **same
span**, so `QualityAnalyst` can reconcile them:

- `subject_consistency < 0.85` AND `character_consistency` stalled low
  -> **confirmed continuity defect**; raise to the top of the fix priority list.
- `subject_consistency >= 0.85` BUT `character_consistency` low only
  -> **suspected judging variance**; flag for re-review.
- `palette_stability < 0.85` -> apply -1~-2 to `inter_scene_continuity`
  (waived if it's an intentional transition).

A metric is a **guide, never a standalone verdict**. The final continuity
judgement combines it with the qualitative dimensions.

---

## 4. Phoenix / OpenInference integration

Wired through [`adk/phoenix_ingest.py`](../adk/phoenix_ingest.py):

- **Span attributes** on the scene `CHAIN` span and the `ContinuitySupervisor`
  `LLM` span: `continuity.subject_consistency`, `continuity.palette_stability`,
  `continuity.alert` (true when any metric is below threshold).
- **Span annotation** `continuity_metric` with `annotator_kind='CODE'` --
  deliberately separate from the `expert_score` annotation
  (`annotator_kind='LLM'`). In Phoenix / via `phoenix-mcp` this lets the agent
  query **measurement vs judgement** apart and reconcile them.

This gives a **self-auditing** loop: most LLM-judge pipelines only trace
subjective scores; here a deterministic continuity signal sits beside them on
the same span, so the agent can ask *"did the judges' continuity score actually
match the measured pixel drift?"* -- directly serving the hackathon's
observability and agent-introspection goals.
