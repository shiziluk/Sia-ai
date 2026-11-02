from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "frontend" / "public" / "avatars" / "final_apron.png"
OUT = ROOT / "sia_out" / "sia_face_p0"
LAYERS = OUT / "layers"
MANIFEST = OUT / "layers.manifest.json"
PREVIEW = OUT / "debug_preview.png"

FACE = (220, 220, 710, 700)
EYE_GOLD = (285, 325, 190, 170)
EYE_RED = (605, 345, 190, 165)
MOUTH = (410, 545, 210, 145)
BROWS = {
    "brow_viewer_left": (290, 270, 220, 110),
    "brow_viewer_right": (590, 280, 230, 110),
}


def crop_box(image: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = box
    return image[y : y + h, x : x + w]


def ellipse_mask(size: tuple[int, int], inset: int = 2) -> np.ndarray:
    w, h = size
    mask = np.zeros((h, w), np.uint8)
    cv2.ellipse(mask, (w // 2, h // 2), (max(1, w // 2 - inset), max(1, h // 2 - inset)), 0, 0, 360, 255, -1)
    return mask


def iris_mask(eye: np.ndarray, kind: str) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    hsv = cv2.cvtColor(eye, cv2.COLOR_RGB2HSV)
    if kind == "gold":
        mask = (hsv[..., 0] >= 18) & (hsv[..., 0] <= 45) & (hsv[..., 1] > 105) & (hsv[..., 2] > 105)
    else:
        mask = (((hsv[..., 0] < 10) | (hsv[..., 0] > 170)) & (hsv[..., 1] > 105) & (hsv[..., 2] > 60))
    mask = mask.astype(np.uint8) * 255
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    if count <= 1:
        raise RuntimeError(f"no {kind} iris component found")
    best = max(range(1, count), key=lambda i: int(stats[i, cv2.CC_STAT_AREA]))
    core = np.where(labels == best, 255, 0).astype(np.uint8)
    x, y, w, h = bbox_from_mask(core, padding=2)
    disk = np.zeros_like(core)
    cv2.ellipse(disk, (x + w // 2, y + h // 2), (w // 2, h // 2), 0, 0, 360, 255, -1)
    disk = cv2.GaussianBlur(disk, (5, 5), 0)
    return disk, (x, y, w, h)


def bbox_from_mask(mask: np.ndarray, padding: int = 4) -> tuple[int, int, int, int]:
    ys, xs = np.where(mask > 0)
    h, w = mask.shape
    x0 = max(0, int(xs.min()) - padding)
    y0 = max(0, int(ys.min()) - padding)
    x1 = min(w, int(xs.max()) + padding + 1)
    y1 = min(h, int(ys.max()) + padding + 1)
    return x0, y0, x1 - x0, y1 - y0


def save_rgba(path: Path, rgb: np.ndarray, alpha: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rgba = np.dstack([rgb, alpha])
    Image.fromarray(rgba, "RGBA").save(path)


def make_eye_layers(image: np.ndarray, box: tuple[int, int, int, int], kind: str, side: str) -> dict:
    eye = crop_box(image, box)
    mask, iris_box = iris_mask(eye, kind)
    ix, iy, iw, ih = iris_box
    iris_rgb = eye[iy : iy + ih, ix : ix + iw]
    iris_alpha = mask[iy : iy + ih, ix : ix + iw]

    # Replace the complete iris disk with a soft sclera fill. Color-mask-only
    # removal leaves dark pupil/highlight fragments and causes double pupils.
    eye_base = eye.copy()
    hsv = cv2.cvtColor(eye, cv2.COLOR_RGB2HSV)
    sclera_pixels = eye[(hsv[..., 1] < 60) & (hsv[..., 2] > 145)]
    sclera = np.median(sclera_pixels, axis=0) if len(sclera_pixels) else np.array([220, 224, 228])
    yy, xx = np.mgrid[: eye.shape[0], : eye.shape[1]]
    cx, cy = ix + iw / 2, iy + ih / 2
    norm = np.sqrt(((xx - cx) / max(iw / 2, 1)) ** 2 + ((yy - cy) / max(ih / 2, 1)) ** 2)
    shade = np.clip(1.04 - 0.12 * norm, 0.82, 1.04)[..., None]
    sclera_fill = np.clip(sclera[None, None, :] * shade, 0, 255).astype(np.uint8)
    eye_base[mask > 0] = sclera_fill[mask > 0]
    eye_alpha = ellipse_mask((eye.shape[1], eye.shape[0]), inset=0)

    stem = f"eye_{side}"
    save_rgba(LAYERS / f"{stem}_base.png", eye_base, eye_alpha)
    save_rgba(LAYERS / f"{stem}_iris.png", iris_rgb, iris_alpha)
    x, y, w, h = box
    return {
        "source_box": [x, y, w, h],
        "iris_source_box": [x + ix, y + iy, iw, ih],
        "base": f"layers/{stem}_base.png",
        "iris": f"layers/{stem}_iris.png",
        "iris_anchor": [x + ix + iw / 2, y + iy + ih / 2],
        "iris_radius": [iw / 2, ih / 2],
        "heterochromia": kind,
        "mask_strategy": "ellipse_disk",
        "extraction": "draft_sclera_fill",
    }


def make_mouth_layer(image: np.ndarray) -> dict:
    x, y, w, h = MOUTH
    mouth = crop_box(image, MOUTH)
    hsv = cv2.cvtColor(mouth, cv2.COLOR_RGB2HSV)
    pink = (((hsv[..., 0] < 15) | (hsv[..., 0] > 170)) & (hsv[..., 1] > 35) & (hsv[..., 2] > 60))
    dark = hsv[..., 2] < 105
    mask = ((pink | dark) & (ellipse_mask((w, h), inset=3) > 0)).astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
    save_rgba(LAYERS / "mouth.png", mouth, mask)
    return {
        "source_box": [x, y, w, h],
        "image": "layers/mouth.png",
        "anchor": [x + w / 2, y + h / 2],
        "extraction": "draft_color_mask",
    }


def make_brow_layer(image: np.ndarray, name: str, box: tuple[int, int, int, int]) -> dict:
    brow = crop_box(image, box)
    hsv = cv2.cvtColor(brow, cv2.COLOR_RGB2HSV)
    mask = ((hsv[..., 2] < 115) & (hsv[..., 1] > 15)).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 3), np.uint8))
    save_rgba(LAYERS / f"{name}.png", brow, mask)
    x, y, w, h = box
    return {
        "source_box": [x, y, w, h],
        "image": f"layers/{name}.png",
        "z": 40,
        "under_bangs_alpha": 0.55,
        "extraction": "draft_dark_mask",
    }


def make_face_base(image: np.ndarray, eye_boxes: list[tuple[int, int, int, int]]) -> np.ndarray:
    mask = np.zeros(image.shape[:2], np.uint8)
    for box in eye_boxes:
        x, y, w, h = box
        local = ellipse_mask((w, h), inset=5)
        mask[y : y + h, x : x + w] = np.maximum(mask[y : y + h, x : x + w], local)
    mx, my, mw, mh = MOUTH
    mask[my : my + mh, mx : mx + mw] = np.maximum(
        mask[my : my + mh, mx : mx + mw],
        ellipse_mask((mw, mh), inset=10),
    )
    bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
    repaired = cv2.inpaint(bgr, mask, 5, cv2.INPAINT_TELEA)
    return cv2.cvtColor(repaired, cv2.COLOR_BGR2RGB)


def normalized(box: tuple[int, int, int, int], size: tuple[int, int]) -> list[float]:
    w, h = size
    x, y, bw, bh = box
    return [round(x / w, 6), round(y / h, 6), round(bw / w, 6), round(bh / h, 6)]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    LAYERS.mkdir(parents=True, exist_ok=True)
    image = np.asarray(Image.open(SOURCE).convert("RGB"))
    height, width = image.shape[:2]

    eye_boxes = [EYE_GOLD, EYE_RED]
    face_base = make_face_base(image, eye_boxes)
    Image.fromarray(face_base, "RGB").save(LAYERS / "face_base.png")

    manifest = {
        "source": str(SOURCE.relative_to(ROOT)),
        "source_size": [width, height],
        "face": {
            "source_box": list(FACE),
            "normalized_box": normalized(FACE, (width, height)),
            "base": "layers/face_base.png",
            "extraction": "draft_inpaint",
        },
        "eyes": {
            "viewer_left_gold": make_eye_layers(image, EYE_GOLD, "gold", "viewer_left"),
            "viewer_right_red": make_eye_layers(image, EYE_RED, "red", "viewer_right"),
        },
        "mouth": make_mouth_layer(image),
        "brows": {
            name: make_brow_layer(image, name, box)
            for name, box in BROWS.items()
        },
        "blush": {
            "source_box": [260, 430, 650, 290],
            "extraction": "procedural_overlay_required",
        },
        "layers_dir": "layers",
        "notes": [
            "Draft extraction; skin behind eyes and mouth is locally inpainted and needs visual seam review.",
            "Eye base uses a rectangular crop with an elliptical alpha mask; lash/ball separation still needs manual cleanup.",
            "Heterochromia is preserved: viewer-left gold, viewer-right red.",
        ],
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    preview = Image.fromarray(face_base, "RGB").convert("RGBA")
    for path in [
        LAYERS / "eye_viewer_left_base.png",
        LAYERS / "eye_viewer_left_iris.png",
        LAYERS / "eye_viewer_right_base.png",
        LAYERS / "eye_viewer_right_iris.png",
        LAYERS / "mouth.png",
    ]:
        layer = Image.open(path).convert("RGBA")
        key = path.stem
        box = EYE_GOLD if "viewer_left" in key else EYE_RED if "viewer_right" in key else MOUTH
        preview.alpha_composite(layer, (box[0], box[1]))

    draw = ImageDraw.Draw(preview)
    for label, box in [("face", FACE), ("eye-gold", EYE_GOLD), ("eye-red", EYE_RED), ("mouth", MOUTH)]:
        x, y, w, h = box
        draw.rectangle((x, y, x + w, y + h), outline=(0, 220, 255, 255), width=3)
        draw.text((x + 5, y + 5), label, fill=(255, 240, 80, 255))
    preview.convert("RGB").save(PREVIEW)

    print(f"wrote {MANIFEST.relative_to(ROOT)}")
    print(f"wrote {PREVIEW.relative_to(ROOT)}")
    print(f"layers: {len(list(LAYERS.glob('*.png')))}")


if __name__ == "__main__":
    main()
