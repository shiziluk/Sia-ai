# -*- coding: utf-8 -*-
"""等 RVC 训练出可用的 maya_svc_e200 权重(或最高 epoch), 然后:
1) svc_convert.py 变声 20 句 Edge-TTS 念稿
2) eval_gate.py score 评分 svc_edge (CPU)
"""
import subprocess
import sys
import time
from pathlib import Path

PKG = Path(r"F:\self_project\Sia-ai\RVC\pkg\RVC20260718Nvidia")
ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
PY = PKG / "runtime" / "python.exe"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def weight_ready():
    ws = list((PKG / "assets" / "weights").glob("*maya_svc_e*.pth"))
    return ws


def train_done():
    txt = (Path(r"F:\self_project\Sia-ai\RVC") / "train_log.txt")
    return txt.exists() and "ALL DONE" in txt.read_text(encoding="utf-8", errors="ignore")


def main():
    log("等待 RVC 训练完成 ...")
    while not weight_ready() or not train_done():
        time.sleep(300)
    log(f"训练完成, 权重: {weight_ready()}")
    time.sleep(30)
    r = subprocess.run([str(PY), str(ROOT / "tools" / "svc_convert.py")],
                       capture_output=True, text=True, cwd=str(PKG))
    log(f"convert rc={r.returncode}")
    print(r.stdout[-800:], flush=True)
    if r.returncode != 0:
        return
    r = subprocess.run([str(PY), str(ROOT / "tools" / "eval_gate.py"), "score",
                        "--tags", "svc_edge"],
                       capture_output=True, text=True, cwd=str(ROOT / "GPT-SoVITS-v2pro-20261006"))
    log(f"score rc={r.returncode}")
    print(r.stdout[-2000:], flush=True)
    log("转换+评分结束")


if __name__ == "__main__":
    main()
