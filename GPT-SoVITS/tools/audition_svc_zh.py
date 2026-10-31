# -*- coding: utf-8 -*-
"""Render a controlled Chinese A/B test for the Maya RVC voice model.

The source clips are Mandarin edge-tts voices, so any remaining foreign accent
comes from the RVC conversion rather than from the Maya GPT language model.
"""
import argparse
import asyncio
import csv
import json
import os
import re
import sys
from pathlib import Path

import numpy as np


ROOT = Path(r"F:\self_project\Sia-ai")
PKG = ROOT / "RVC" / "pkg" / "RVC20260718Nvidia"
SOURCE_DIR = ROOT / "RVC" / "src_svc_zh"
OUT_DIR = ROOT / "GPT-SoVITS" / "_audition" / "tuning_20261029_svc_zh"
TEXT = "你回来了。今天过得怎么样？"
TEXT_WITH_PAUSE = "你回来了。<0.28s>今天过得怎么样？"
PAUSE_SECONDS = 0.28
SOURCES = (
    ("wenrou", "zh-CN-XiaoxiaoNeural", "-4%"),
    ("akuma", "zh-CN-XiaoyiNeural", "+2%"),
)


def log(message):
    print(message, flush=True)


def latest_weight():
    weights = list((PKG / "assets" / "weights").glob("*maya_svc*_e*.pth"))
    if not weights:
        raise SystemExit("No Maya RVC weight found in assets/weights")

    def epoch(path):
        match = re.search(r"_e(\d+)(?:_s\d+)?$", path.stem)
        return int(match.group(1)) if match else -1

    return max(weights, key=lambda path: (epoch(path), path.stat().st_mtime))


def latest_index():
    indices = list((PKG / "logs" / "maya_svc").glob("added_*.index"))
    return max(indices, key=lambda path: path.stat().st_mtime) if indices else None


async def render_sources():
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    pending = [
        (source_id, voice, rate)
        for source_id, voice, rate in SOURCES
        if not (
            (SOURCE_DIR / f"{source_id}.mp3").exists()
            and (SOURCE_DIR / f"{source_id}.mp3").stat().st_size > 10000
        )
    ]
    if pending:
        import edge_tts

    for source_id, voice, rate in SOURCES:
        dst = SOURCE_DIR / f"{source_id}.mp3"
        if dst.exists() and dst.stat().st_size > 10000:
            log(f"SOURCE EXISTS {dst.name}")
            continue
        communicate = edge_tts.Communicate(TEXT, voice, rate=rate)
        await communicate.save(str(dst))
        if not dst.exists() or dst.stat().st_size <= 10000:
            raise RuntimeError(f"edge-tts failed to write {dst}")
        log(f"SOURCE OK {dst.name}")


def convert(key_values, index_rates):
    os.chdir(PKG)
    sys.path.insert(0, str(PKG))
    os.environ["weight_root"] = "assets/weights"
    os.environ.setdefault("rmvpe_root", "assets/rmvpe")
    os.environ.setdefault("index_root", "logs")
    # Config.arg_parse() owns process argv; keep our audition flags out of it.
    sys.argv = [sys.argv[0]]

    from configs.config import Config
    from infer.vc.modules import VC
    import soundfile as sf

    weight = latest_weight()
    index = latest_index()
    if index is None:
        index_rates = (0.0,)
        log("No faiss index yet; rendering without retrieval.")
    cfg = Config()
    vc = VC(cfg)
    vc.get_vc(weight.name)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = []
    for source_id, _, _ in SOURCES:
        source = SOURCE_DIR / f"{source_id}.mp3"
        if not source.exists():
            raise SystemExit(f"Missing source: {source}")
        for key in key_values:
            for index_rate in index_rates:
                rate_tag = str(index_rate).replace(".", "p")
                out = OUT_DIR / f"{source_id}_key{key:+d}_idx{rate_tag}.wav"
                info, audio = vc.vc_single(
                    0,
                    str(source),
                    key,
                    "rmvpe",
                    str(index) if index else "",
                    index_rate,
                    0,
                    0.25,
                    0.33,
                )
                if not audio or audio[0] is None or audio[1] is None:
                    raise RuntimeError(f"RVC failed for {out.name}: {info}")
                sample_rate, samples = audio
                sf.write(str(out), samples, sample_rate)
                rows.append(
                    {
                        "source": source.name,
                        "output": out.name,
                        "key": key,
                        "index_rate": index_rate,
                        "weight": weight.name,
                        "index": index.name if index else "",
                        "text": TEXT,
                    }
                )
                log(f"RENDER OK {out.name}")

    for source_id, _, _ in SOURCES:
        parts = (
            SOURCE_DIR / f"{source_id}_first.mp3",
            SOURCE_DIR / f"{source_id}_second.mp3",
        )
        if not all(part.exists() for part in parts):
            log(f"PAUSE SKIP {source_id}: split sources missing")
            continue
        for key in key_values:
            rendered = []
            sample_rate = None
            for part in parts:
                info, audio = vc.vc_single(
                    0,
                    str(part),
                    key,
                    "rmvpe",
                    str(index) if index else "",
                    index_rates[0],
                    0,
                    0.25,
                    0.33,
                )
                if not audio or audio[0] is None or audio[1] is None:
                    raise RuntimeError(f"RVC failed for {part.name}: {info}")
                sample_rate, samples = audio
                samples = np.asarray(samples)
                if np.issubdtype(samples.dtype, np.integer):
                    samples = samples.astype(np.float32) / 32768.0
                else:
                    samples = samples.astype(np.float32)
                rendered.append(samples)
            silence = np.zeros(int(sample_rate * PAUSE_SECONDS), dtype=np.float32)
            out = OUT_DIR / f"{source_id}_key{key:+d}_pause0p28.wav"
            sf.write(
                str(out),
                np.concatenate((rendered[0], silence, rendered[1])),
                sample_rate,
                subtype="PCM_16",
            )
            rows.append(
                {
                    "source": f"{source_id}_first+second.mp3",
                    "output": out.name,
                    "key": key,
                    "index_rate": index_rates[0],
                    "weight": weight.name,
                    "index": index.name if index else "",
                    "text": TEXT,
                }
            )
            log(f"RENDER OK {out.name}")

    manifest = OUT_DIR / "manifest.json"
    manifest.write_text(
        json.dumps({"records": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (OUT_DIR / "manifest.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    log(f"MANIFEST {manifest}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources-only", action="store_true")
    parser.add_argument("--keys", nargs="+", type=int, default=(0, -1, 1))
    parser.add_argument(
        "--index-rates", nargs="+", type=float, default=(0.0, 0.75)
    )
    args = parser.parse_args()

    asyncio.run(render_sources())
    if args.sources_only:
        return
    convert(args.keys, args.index_rates)


if __name__ == "__main__":
    main()
