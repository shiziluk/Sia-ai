"""用 3 条不同语气的摩耶参考音频合成同句中文，供对比选型
用法: python try_refs.py
"""
import json
import subprocess
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_audition"
V = "F:/self_project/Sia-ai/GPT-SoVITS/_voices"

REFS = [
    # (文件, 官方台词, 标签) —— 古灵精怪/小恶魔段
    (f"{V}/z3016_0187.ogg", "やることやっておいて、あとはしらばっくれるんだ？", "G_z3016_0187"),
]
TEXT = "嗯，我在哦。今天想吃什么？你说，我来做。"

for ref, prompt, tag in REFS:
    body = json.dumps({
        "text": TEXT, "text_lang": "zh",
        "ref_audio_path": ref, "prompt_text": prompt, "prompt_lang": "ja",
        "streaming_mode": False,
    }).encode()
    req = urllib.request.Request("http://127.0.0.1:9880/tts", data=body,
                                 headers={"Content-Type": "application/json"})
    import time
    t0 = time.time()
    try:
        wav = urllib.request.urlopen(req, timeout=180).read()
    except Exception as e:
        print(f"{tag}: FAIL {e}")
        continue
    wpath = OUT / f"tz_{tag}.wav"
    wpath.write_bytes(wav)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wpath),
                    "-q:a", "4", str(OUT / f"tz_{tag}.mp3")], check=True)
    wpath.unlink()
    print(f"{tag}: {time.time()-t0:.0f}s -> tz_{tag}.mp3")
