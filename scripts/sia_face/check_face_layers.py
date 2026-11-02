from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend" / "public" / "avatars" / "final_apron.png"
PACK = ROOT / "sia_out" / "sia_face_p0"
MANIFEST = PACK / "layers.manifest.json"


def compose() -> tuple[np.ndarray, dict]:
    source = np.asarray(Image.open(SOURCE).convert("RGB")).astype(np.int16)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    base = Image.open(PACK / manifest["face"]["base"]).convert("RGBA")

    for key in ("viewer_left_gold", "viewer_right_red"):
        eye = manifest["eyes"][key]
        if eye.get("mask_strategy") != "ellipse_disk":
            raise AssertionError(f"{key}: iris must use a complete ellipse disk")
        x, y, _, _ = eye["source_box"]
        base.alpha_composite(Image.open(PACK / eye["base"]).convert("RGBA"), (x, y))
        ix, iy, _, _ = eye["iris_source_box"]
        base.alpha_composite(Image.open(PACK / eye["iris"]).convert("RGBA"), (ix, iy))

    mouth = manifest["mouth"]
    mx, my, _, _ = mouth["source_box"]
    base.alpha_composite(Image.open(PACK / mouth["image"]).convert("RGBA"), (mx, my))
    return source, np.asarray(base.convert("RGB")).astype(np.int16), manifest


def region_mae(actual: np.ndarray, expected: np.ndarray, box: list[int]) -> tuple[float, float]:
    x, y, w, h = box
    delta = np.abs(actual[y : y + h, x : x + w] - expected[y : y + h, x : x + w])
    return float(delta.mean()), float(np.percentile(delta, 95))


def main() -> None:
    source, composed, manifest = compose()
    checks = {}
    for key in ("viewer_left_gold", "viewer_right_red"):
        box = manifest["eyes"][key]["source_box"]
        checks[key] = region_mae(composed, source, box)
    checks["mouth"] = region_mae(composed, source, manifest["mouth"]["source_box"])

    passed = (
        checks["viewer_left_gold"][0] <= 5
        and checks["viewer_right_red"][0] <= 5
        and checks["mouth"][0] <= 8
        and checks["mouth"][1] <= 45
    )
    print(json.dumps({"passed": passed, "mae": checks}, indent=2))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
