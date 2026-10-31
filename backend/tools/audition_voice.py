"""Generate a small, reproducible voice-tuning audition pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.tts import (
    VoiceLang,
    VoiceTier,
    intimacy_to_tier,
    load_ref_manifest,
    pick_ref,
    synthesize_speech,
)


CASES = [
    {
        "id": "zh_low",
        "lang": VoiceLang.ZH,
        "intimacy": 1,
        "text": "你回来了。今天过得怎么样？",
    },
    {
        "id": "zh_mid",
        "lang": VoiceLang.ZH,
        "intimacy": 2,
        "text": "今天也辛苦了，回来得正好，我刚把汤热好。",
    },
    {
        "id": "zh_high",
        "lang": VoiceLang.ZH,
        "intimacy": 4,
        "text": "别担心，我会一直在你身边的。",
    },
    {
        "id": "ja_low",
        "lang": VoiceLang.JA,
        "intimacy": 1,
        "text": "おかえり。今日はどうだった？",
    },
    {
        "id": "ja_mid",
        "lang": VoiceLang.JA,
        "intimacy": 2,
        "text": "今日もお疲れさま。ちょうどスープを温めたところ。",
    },
    {
        "id": "ja_high",
        "lang": VoiceLang.JA,
        "intimacy": 4,
        "text": "心配しないで。ずっとそばにいるから。",
    },
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = load_ref_manifest()
    records = []

    for case in CASES:
        destination = output / f"{case['id']}.mp3"
        if destination.exists() and not args.overwrite:
            records.append(
                {
                    "id": case["id"],
                    "text": case["text"],
                    "lang": case["lang"].value,
                    "intimacy": case["intimacy"],
                    "path": str(destination),
                    "skipped": True,
                }
            )
            continue

        tier = intimacy_to_tier(case["intimacy"])
        ref = pick_ref(tier, case["lang"], case["text"])
        result = synthesize_speech(
            case["text"],
            intimacy_level=case["intimacy"],
            lang=case["lang"].value,
        )
        destination.write_bytes(result.audio)
        tune = manifest.tunes[tier]
        records.append(
            {
                "id": case["id"],
                "text": case["text"],
                "lang": case["lang"].value,
                "intimacy": case["intimacy"],
                "tier": tier.value,
                "backend": result.backend,
                "bytes": len(result.audio),
                "path": str(destination),
                "ref_audio": str(ref.audio) if ref else "",
                "ref_text": ref.text if ref else "",
                "speed": tune.speed,
                "top_p": tune.top_p,
                "temperature": tune.temperature,
            }
        )
        print(f"{case['id']}: {result.backend}, {len(result.audio)} bytes")

    index = output / "index.json"
    index.write_text(
        json.dumps({"version": 1, "records": records}, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    print(f"audition pack: {output}")
    if any(record.get("backend") == "edge" for record in records):
        print("WARNING: at least one sample fell back to edge-tts", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
