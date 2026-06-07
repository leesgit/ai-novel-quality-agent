"""RALF unit tests for adk/continuity_metrics — pure functions, synthetic images.

No network, no server, no real frames. Fixtures are PIL-generated solid/
gradient images created on the fly under a temp dir.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from adk import continuity_metrics as cm  # noqa: E402


def _make_image(path: Path, color, size=(160, 160), gradient=False):
    from PIL import Image
    im = Image.new("RGB", size, color)
    if gradient:
        px = im.load()
        for x in range(size[0]):
            for y in range(size[1]):
                px[x, y] = (x % 256, y % 256, (x + y) % 256)
    im.save(path)


def main() -> int:
    passed = 0
    failed = 0

    def check(name, cond):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  ✅ {name}")
        else:
            failed += 1
            print(f"  ❌ {name}")

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        red = d / "red.png"
        red2 = d / "red2.png"
        blue = d / "blue.png"
        grad = d / "grad.png"
        _make_image(red, (200, 30, 30))
        _make_image(red2, (200, 30, 30))
        _make_image(blue, (30, 30, 200))
        _make_image(grad, (0, 0, 0), gradient=True)

        # dHash similarity: identical content -> 1.0
        h = cm.dhash(red)
        check("dhash identical -> similarity 1.0", cm.hash_similarity(h, cm.dhash(red2)) == 1.0)

        # histogram similarity: identical -> 1.0, very different -> < 1.0
        hr = cm.rgb_histogram(red)
        check("histogram identical -> 1.0", cm.histogram_similarity(hr, cm.rgb_histogram(red2)) == 1.0)
        sim_rb = cm.histogram_similarity(hr, cm.rgb_histogram(blue))
        check("histogram red vs blue < 1.0", sim_rb is not None and sim_rb < 1.0)

        # subject_consistency / palette_stability range
        sc = cm.subject_consistency(grad, red)
        pal = cm.palette_stability(grad, red)
        check("subject_consistency in [0,1]", sc is not None and 0.0 <= sc <= 1.0)
        check("palette_stability in [0,1]", pal is not None and 0.0 <= pal <= 1.0)

        # metrics_summary: low palette pair raises an alert
        summ = cm.metrics_summary(red, blue)
        check("summary keys present",
              {"subject_consistency", "palette_stability", "alerts"} <= set(summ))
        check("red->blue raises a palette alert",
              any("palette_stability" in a for a in summ["alerts"]))

        # graceful degrade: missing file -> None, no crash
        missing = d / "nope.png"
        check("missing file -> dhash None", cm.dhash(missing) is None)
        check("missing file -> subject_consistency None",
              cm.subject_consistency(missing, red) is None)
        check("None inputs -> hash_similarity None", cm.hash_similarity(None, h) is None)

    print(f"\n{passed} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
