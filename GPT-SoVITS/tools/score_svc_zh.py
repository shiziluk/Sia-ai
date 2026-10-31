# -*- coding: utf-8 -*-
"""Score the controlled Chinese RVC audition outputs."""
import json
import os
import sys
from pathlib import Path

import librosa
import numpy as np


ROOT = Path(r"F:\self_project\Sia-ai")
TOOLS = ROOT / "GPT-SoVITS" / "tools"
OUT_DIR = ROOT / "GPT-SoVITS" / "_audition" / "tuning_20261029_svc_zh"

sys.path.insert(0, str(TOOLS))
import eval_gate  # noqa: E402


def load_audio_16k(path):
    audio, sample_rate = librosa.load(str(path), sr=None, mono=True)
    if sample_rate != 16000:
        audio = librosa.resample(audio, orig_sr=sample_rate, target_sr=16000)
    return audio


def main():
    os.chdir(ROOT / "GPT-SoVITS" / "GPT-SoVITS-v2pro-20261006")
    sys.path.append(str(ROOT / "GPT-SoVITS" / "GPT-SoVITS-v2pro-20261006" / "GPT_SoVITS" / "eres2net"))

    manifest = json.loads((OUT_DIR / "manifest.json").read_text(encoding="utf-8"))
    records = manifest["records"]
    if not records:
        raise SystemExit("No RVC audition records found")

    from GPT_SoVITS.sv import SV

    asr = eval_gate.load_asr()
    speaker_model = SV("cpu", False)
    maya_center = eval_gate.maya_center()
    rows = []
    for record in records:
        path = OUT_DIR / record["output"]
        audio, sample_rate = librosa.load(str(path), sr=None, mono=True)
        embedding = (
            speaker_model.compute_embedding3(
                eval_gate.torch_from(load_audio_16k(path))
            )
            .squeeze()
            .float()
            .cpu()
            .numpy()
        )
        hypothesis = asr.generate(input=str(path))[0].get("text", "") or ""
        row = {
            **record,
            "duration": round(len(audio) / sample_rate, 2),
            "cer": round(eval_gate.cer(record["text"], hypothesis), 3),
            "speaker_similarity": round(eval_gate.cos(embedding, maya_center), 3),
            "f0_median": round(eval_gate.f0_median(audio, sample_rate)),
            "transcript": hypothesis,
        }
        rows.append(row)
        print(
            f"{row['output']}: CER={row['cer']:.3f} "
            f"sim={row['speaker_similarity']:.3f} "
            f"F0={row['f0_median']} ASR={row['transcript']}",
            flush=True,
        )

    report = {
        "avg_cer": round(float(np.mean([row["cer"] for row in rows])), 3),
        "avg_speaker_similarity": round(
            float(np.mean([row["speaker_similarity"] for row in rows])), 3
        ),
        "rows": rows,
    }
    report_path = OUT_DIR / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"REPORT {report_path}")


if __name__ == "__main__":
    main()
