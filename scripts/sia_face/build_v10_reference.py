from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "sia_out" / "sia_3v10_apron_00018_.png"
OUT = ROOT / "sia_out" / "sia_v10_reference"
FRONT = OUT / "front_gold.png"
PREVIEW = OUT / "front_gold_preview.png"
MANIFEST = OUT / "manifest.json"


def border_connected_background(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    corners = np.concatenate(
        [
            image[:24, :24].reshape(-1, 3),
            image[:24, -24:].reshape(-1, 3),
            image[-24:, :24].reshape(-1, 3),
            image[-24:, -24:].reshape(-1, 3),
        ]
    )
    bg = np.median(corners, axis=0)
    distance = np.linalg.norm(image.astype(np.int16) - bg[None, None, :], axis=-1)
    candidate = (distance < 52).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate, 8)
    border_labels = set(labels[0, :]) | set(labels[-1, :]) | set(labels[:, 0]) | set(labels[:, -1])
    border_labels.discard(0)
    background = np.isin(labels, list(border_labels)).astype(np.uint8)
    return background


def find_red_irises(image: np.ndarray) -> list[tuple[int, int, int, int, int]]:
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    red = (((hsv[..., 0] < 10) | (hsv[..., 0] > 170)) & (hsv[..., 1] > 90) & (hsv[..., 2] > 55))
    red[int(image.shape[0] * 0.38) :, :] = False
    count, _, stats, _ = cv2.connectedComponentsWithStats(red.astype(np.uint8), 8)
    eyes = []
    for index in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[index])
        if 25 <= area <= 2000 and w >= 5 and h >= 4:
            eyes.append((x, y, w, h, area))
    return sorted(eyes, key=lambda item: item[0])


def make_gold_eye(image: np.ndarray, eye_box: tuple[int, int, int, int]) -> tuple[np.ndarray, pathlib_box]:
    x, y, w, h = eye_box
    crop = image[y : y + h, x : x + w].copy()
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    red = (((hsv[..., 0] < 10) | (hsv[..., 0] > 170)) & (hsv[..., 1] > 95) & (hsv[..., 2] > 60))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(red.astype(np.uint8), 8)
    if count <= 1:
        raise RuntimeError("could not find red iris in v10 front view")
    component = max(range(1, count), key=lambda i: int(stats[i, cv2.CC_STAT_AREA]))
    mask = labels == component
    highlight = hsv[..., 2] > 242
    mask &= ~highlight
    hsv_float = hsv.astype(np.float32)
    hsv_float[..., 0] = np.where(mask, 23.3, hsv_float[..., 0])
    hsv_float[..., 1] = np.where(mask, np.clip(hsv_float[..., 1] * 1.12, 0, 255), hsv_float[..., 1])
    crop = cv2.cvtColor(hsv_float.astype(np.uint8), cv2.COLOR_HSV2RGB)
    image[y : y + h, x : x + w] = crop
    area = int(stats[component, cv2.CC_STAT_AREA])
    return image, (x, y, w, h, area)


pathlib_box = tuple[int, int, int, int, int]


def make_preview(rgba: Image.Image) -> Image.Image:
    preview = Image.new("RGBA", rgba.size, (10, 15, 20, 255))
    draw = ImageDraw.Draw(preview)
    for y in range(preview.height):
        k = y / max(1, preview.height - 1)
        draw.line(
            ((0, y), (preview.width, y)),
            fill=(11 + round(4 * k), 17 + round(7 * k), 25 + round(10 * k), 255),
        )
    preview.alpha_composite(rgba)
    return preview.convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source = np.asarray(Image.open(SOURCE).convert("RGB"))
    h, w = source.shape[:2]
    front = source[:, : w // 3].copy()
    background = border_connected_background(front)
    alpha = np.where(background > 0, 0, 255).astype(np.uint8)
    alpha = cv2.erode(alpha, np.ones((2, 2), np.uint8), iterations=2)
    alpha = cv2.GaussianBlur(alpha, (3, 3), 0.6)

    ys, xs = np.where(alpha > 8)
    pad = 8
    x0 = max(0, int(xs.min()) - pad)
    y0 = max(0, int(ys.min()) - pad)
    x1 = min(front.shape[1], int(xs.max()) + pad + 1)
    y1 = min(front.shape[0], int(ys.max()) + pad + 1)
    front = front[y0:y1, x0:x1]
    alpha = alpha[y0:y1, x0:x1]

    # The first third can contain a sliver of the next view's hair. Keep only
    # the largest connected foreground component.
    count, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 8).astype(np.uint8), 8)
    if count <= 1:
        raise RuntimeError("front view has no foreground")
    main_label = max(range(1, count), key=lambda i: int(stats[i, cv2.CC_STAT_AREA]))
    alpha = np.where(labels == main_label, alpha, 0).astype(np.uint8)

    # Suppress green spill only on the alpha boundary, not inside the sweater.
    core = (alpha > 235).astype(np.uint8)
    edge_zone = cv2.dilate(core, np.ones((7, 7), np.uint8), iterations=1) - cv2.erode(
        core, np.ones((7, 7), np.uint8), iterations=1
    )
    r = front[..., 0].astype(np.int16)
    g = front[..., 1].astype(np.int16)
    b = front[..., 2].astype(np.int16)
    spill = (edge_zone > 0) & (g > np.maximum(r, b) + 4)
    if spill.any():
        front[..., 1] = np.where(spill, np.maximum(r, b), front[..., 1]).astype(np.uint8)

    # Front-view viewer-left iris is Sia's anatomical right eye.
    eyes = find_red_irises(front)
    if len(eyes) < 2:
        raise RuntimeError(f"expected two red iris components, got {len(eyes)}")
    ex, ey, ew, eh, _ = eyes[0]
    eye_box = (max(0, ex - 24), max(0, ey - 18), ew + 48, eh + 36)
    front, left_eye_change = make_gold_eye(front, eye_box)

    rgba = Image.fromarray(np.dstack([front, alpha]), "RGBA")
    rgba.save(FRONT)
    make_preview(rgba).save(PREVIEW)
    MANIFEST.write_text(
        json.dumps(
            {
                "source": str(SOURCE.relative_to(ROOT)),
                "selection_reason": "v10 00018 has 3 views, visible hands, aligned legs/shoes and a back-strap reference; this is the apron/bare-leg variant",
                "crop_box_in_front_third": [x0, y0, x1 - x0, y1 - y0],
                "front": str(FRONT.relative_to(ROOT)),
                "preview": str(PREVIEW.relative_to(ROOT)),
                "size": list(rgba.size),
                "alpha_pixels": int((np.asarray(rgba.getchannel("A")) > 8).sum()),
                "gold_eye_crop": list(left_eye_change),
                "remaining_issues": [
                    "side view has a garment slit and weak anatomy",
                    "apron side pocket and waist tassel shape are still inconsistent",
                    "face identity remains simpler than stage-realistic-night",
                    "this apron variant does not include black stockings",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {FRONT.relative_to(ROOT)}")
    print(f"wrote {PREVIEW.relative_to(ROOT)}")
    print(f"size {rgba.size}, alpha pixels {int((np.asarray(rgba.getchannel('A')) > 8).sum())}")


if __name__ == "__main__":
    main()
