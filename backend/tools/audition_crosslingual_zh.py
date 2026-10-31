"""Compare Chinese pronunciation against Chinese and Maya-original prompts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import PROJECT_ROOT, settings
from app.services.tts import (
    GptSovitsBackend,
    RefSample,
    VoiceLang,
    VoiceTier,
    load_ref_manifest,
)


TEXT = "你回来了。今天过得怎么样？"


def resolve(raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = load_ref_manifest()
    zh_ref = manifest.refs[(VoiceLang.ZH, VoiceTier.LOW)][0]
    maya_ref = manifest.refs[(VoiceLang.JA, VoiceTier.LOW)][0]
    tune = manifest.tunes[VoiceTier.LOW]
    sovits = resolve(settings.sovits_weight)
    base_gpt = resolve(settings.gpt_zh_weight)
    selected_gpt = resolve(
        "GPT-SoVITS/GPT-SoVITS-v2pro-20261006/"
        "GPT_weights_v2ProPlus/maya-e20.ckpt"
    )
    full16_gpt = resolve(
        "GPT-SoVITS/GPT-SoVITS-v2pro-20261006/"
        "GPT_weights_v2ProPlus/maya_full-e16.ckpt"
    )

    cases = [
        ("zh_base_current_ref", base_gpt, zh_ref),
        ("zh_base_maya_ref", base_gpt, maya_ref),
        ("zh_sel_maya_ref", selected_gpt, maya_ref),
        ("zh_full16_maya_ref", full16_gpt, maya_ref),
    ]
    backend = GptSovitsBackend()
    records = []
    for name, gpt_weight, ref in cases:
        destination = output / f"{name}.mp3"
        if destination.exists() and not args.overwrite:
            records.append({"id": name, "path": str(destination), "skipped": True})
            continue
        audio = backend.synthesize(
            text=TEXT,
            lang=VoiceLang.ZH,
            ref=ref,
            gpt_weight=gpt_weight,
            sovits_weight=sovits,
            tune=tune,
        )
        destination.write_bytes(audio)
        records.append(
            {
                "id": name,
                "text": TEXT,
                "gpt_weight": str(gpt_weight),
                "sovits_weight": str(sovits),
                "ref_audio": str(ref.audio),
                "ref_text": ref.text,
                "prompt_lang": ref.prompt_lang or "zh",
                "text_lang": "zh",
                "speed": tune.speed,
                "top_p": tune.top_p,
                "temperature": tune.temperature,
                "bytes": len(audio),
                "path": str(destination),
            }
        )
        print(f"{name}: {len(audio)} bytes")

    (output / "index.json").write_text(
        json.dumps({"version": 1, "records": records}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"cross-lingual audition: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
