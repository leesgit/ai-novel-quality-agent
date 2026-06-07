"""Deterministic continuity metrics for adjacent scenes.

These metrics give a *quantitative, reproducible* continuity signal that runs
independently of the LLM expert panel. They are cheap (PIL only, no face
embeddings / dlib) and are meant to be logged alongside the subjective expert
scores so the agent can cross-check "did the judges' continuity score actually
match the measured pixel drift?".

Two signals:

1. **dHash (difference hash)** — an image is reduced to 9x8 grayscale; comparing
   each pixel with its right neighbour yields an 8x8 (64-bit) fingerprint.
   Perceptual hashes are robust to small rotation / lighting changes, so two
   visually similar frames have a small Hamming distance. A center-ROI variant
   crops the middle 50% to focus the signal on the foreground subject region.
2. **RGB histogram** — 8 bins per channel (24 bins). The 1 - normalized-L1
   distance of two distributions captures palette / lighting drift.

This is not as precise as facial embeddings, but it reliably flags *macro*
changes — e.g. a subject that suddenly looks like a different identity between
adjacent scenes, or an abrupt color/lighting shift. Scores are 0.0-1.0;
0.85+ is the recommended pass threshold.

A continuity metric is a *signal, not a verdict*: the final judgement combines
it with the qualitative expert dimensions. PIL is an optional dependency —
when it (or an image) is missing, the metric returns ``None`` so evaluation
degrades gracefully instead of crashing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


# 8x8 dHash -> 64-bit fingerprint
DHASH_SIZE = 8

# Below this, a metric raises a continuity alert.
ALERT_THRESHOLD = 0.85


def _try_pil():
    try:
        from PIL import Image
        return Image
    except ImportError:
        return None


def dhash(image_path: Path, *, roi_center: bool = False) -> int | None:
    """Difference-hash of an image. ``roi_center=True`` crops the middle 50%
    to focus on the foreground subject region."""
    Image = _try_pil()
    if Image is None or not image_path.exists():
        return None
    try:
        with Image.open(image_path) as im:
            im = im.convert("L")  # grayscale
            if roi_center:
                w, h = im.size
                cx, cy = w // 2, h // 2
                half_w, half_h = w // 4, h // 4
                im = im.crop((cx - half_w, cy - half_h, cx + half_w, cy + half_h))
            im = im.resize((DHASH_SIZE + 1, DHASH_SIZE), Image.Resampling.LANCZOS)
            pixels = list(im.getdata())
        bits = 0
        for row in range(DHASH_SIZE):
            for col in range(DHASH_SIZE):
                left = pixels[row * (DHASH_SIZE + 1) + col]
                right = pixels[row * (DHASH_SIZE + 1) + col + 1]
                bits = (bits << 1) | (1 if left > right else 0)
        return bits
    except Exception:
        return None


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def hash_similarity(a: int | None, b: int | None) -> float | None:
    """Similarity of two dHashes, 0.0-1.0 (1.0 = identical)."""
    if a is None or b is None:
        return None
    dist = hamming(a, b)
    return round(1.0 - dist / 64.0, 4)


def rgb_histogram(image_path: Path, bins: int = 8) -> list[int] | None:
    """R/G/B histogram (``bins`` each). Counts are not normalized here."""
    Image = _try_pil()
    if Image is None or not image_path.exists():
        return None
    try:
        with Image.open(image_path) as im:
            im = im.convert("RGB").resize((128, 128), Image.Resampling.NEAREST)
            pixels = list(im.getdata())
        bin_size = 256 // bins
        hist = [0] * (bins * 3)
        for r, g, b in pixels:
            hist[r // bin_size] += 1
            hist[bins + g // bin_size] += 1
            hist[bins * 2 + b // bin_size] += 1
        return hist
    except Exception:
        return None


def histogram_similarity(h1: list[int] | None, h2: list[int] | None) -> float | None:
    """1 - normalized L1 distance of two histograms. 0.0-1.0 (1.0 = identical)."""
    if h1 is None or h2 is None or len(h1) != len(h2):
        return None
    s1 = sum(h1) or 1
    s2 = sum(h2) or 1
    diff = sum(abs(a / s1 - b / s2) for a, b in zip(h1, h2))
    # Max L1 distance between two normalized distributions is 2.0.
    return round(max(0.0, 1.0 - diff / 2.0), 4)


def subject_consistency(prev_image: Path, curr_image: Path) -> float | None:
    """Center-ROI dHash similarity between two adjacent frames. 0.0-1.0.

    Flags when the foreground subject's identity drifts between scenes."""
    h1 = dhash(prev_image, roi_center=True)
    h2 = dhash(curr_image, roi_center=True)
    return hash_similarity(h1, h2)


def palette_stability(prev_image: Path, curr_image: Path) -> float | None:
    """RGB-histogram similarity between two adjacent frames. 0.0-1.0.

    Flags color / lighting drift between scenes."""
    h1 = rgb_histogram(prev_image)
    h2 = rgb_histogram(curr_image)
    return histogram_similarity(h1, h2)


def metrics_summary(prev_image: Path, curr_image: Path) -> dict[str, Any]:
    """Quantitative continuity summary for one adjacent-scene pair.

    Returns the two scores plus any threshold alerts. The alerts are advisory
    nudges for the expert panel, never a standalone verdict."""
    subj = subject_consistency(prev_image, curr_image)
    pal = palette_stability(prev_image, curr_image)
    alerts: list[str] = []
    if subj is not None and subj < ALERT_THRESHOLD:
        alerts.append(
            f"subject_consistency={subj} < {ALERT_THRESHOLD} — "
            "large identity drift vs the previous scene; "
            "consider -1~-2 on character_consistency"
        )
    if pal is not None and pal < ALERT_THRESHOLD:
        alerts.append(
            f"palette_stability={pal} < {ALERT_THRESHOLD} — "
            "large color/lighting drift vs the previous scene; "
            "consider -1~-2 on inter_scene_continuity "
            "(ignore if an intentional location/time change)"
        )
    return {
        "subject_consistency": subj,
        "palette_stability": pal,
        "alerts": alerts,
    }
