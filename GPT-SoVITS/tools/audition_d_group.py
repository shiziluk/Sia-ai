"""D组: 中文ref + SoVITS_e3 + GPT_e10 复试 (日语腔假设验证)
假设: e3 音色绑定够强, 中文 ref 不再污染音色, 且消除日语腔
api 现状: SoVITS=maya_e3, GPT=maya-e10 (audition_on_gpt.py 切完遗留)
"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
OUT = ROOT / "_audition" / "finetuned_gpt"
API = "http://127.0.0.1:9880/tts"

# 中文 ref (edge-tts 合成) + 中文 prompt
CASES = [
    ("D_wenrou", ROOT / "_audition/ref_zh/xiaoxiao_a.wav",
     "哎呀，被你发现了。其实这些话，我一直都想找机会告诉你。",
     "今天也辛苦了，回来得正好，我刚把汤热好。"),
    ("D_akuma", ROOT / "_audition/ref_zh/xiaoyi_c1.mp3",
     "喂，别装傻了，昨天的事我可都记着呢。你老实交代。",
     "才不是担心你呢，只是你不在的话，会有人偷偷哭鼻子的。"),
]


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def main():
    for tag, ref, prompt, text in CASES:
        body = {
            "text": text, "text_lang": "zh",
            "ref_audio_path": str(ref).replace("\\", "/"),
            "prompt_text": prompt, "prompt_lang": "zh",
            "text_split_method": "cut5",
        }
        dst = OUT / f"{tag}.mp3"
        req = urllib.request.Request(API, json.dumps(body).encode(), {"Content-Type": "application/json"})
        for attempt in range(3):
            try:
                wav = urllib.request.urlopen(req, timeout=300).read()
                p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "pipe:0", "-b:a", "128k", str(dst)],
                                   input=wav, capture_output=True)
                if p.returncode == 0 and dst.stat().st_size > 10000:
                    log(f"OK {dst.name} {dst.stat().st_size // 1024}KB")
                    break
            except Exception as e:
                log(f"attempt{attempt} {tag}: {e}")
                time.sleep(5)
    log("D组完成")


if __name__ == "__main__":
    main()
