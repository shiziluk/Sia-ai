# -*- coding: utf-8 -*-
"""Edge-TTS 生成 20 句中文念稿(SVC 路线的音源), 供 RVC 变摩耶音色。
输出: RVC/src_edge/<id>.mp3
用法: runtime\\python.exe tools\\gen_edge_src.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
SENT = ROOT / "_audition" / "gate" / "sentences.json"
OUT = Path(r"F:\self_project\Sia-ai\RVC\src_edge")
PY = ROOT / "GPT-SoVITS-v2pro-20261006" / "runtime" / "python.exe"

# style -> (voice, rate): 晓晓温柔 / 晓伊俏皮
VOICE = {
    "wenrou": ("zh-CN-XiaoxiaoNeural", "-4%"),
    "akuma": ("zh-CN-XiaoyiNeural", "+2%"),
}


def main():
    cfg = json.loads(SENT.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    ok = 0
    for s in cfg["sentences"]:
        dst = OUT / f"{s['id']}.mp3"
        if dst.exists() and dst.stat().st_size > 10000:
            ok += 1
            continue
        voice, rate = VOICE[s["style"]]
        cmd = [str(PY), "-m", "edge_tts", "--voice", voice,
               f"--rate={rate}", "--text", s["text"], "--write-media", str(dst)]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0 and dst.exists() and dst.stat().st_size > 10000:
            ok += 1
            print(f"OK {s['id']}")
        else:
            print(f"FAIL {s['id']}: {p.stderr[-120:]}")
    print(f"完成 {ok}/20 -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
