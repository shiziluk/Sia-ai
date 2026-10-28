# -*- coding: utf-8 -*-
"""RVC 训练收尾链（无需人工）

背景：train.py 只往 logs/maya_svc/ 写 G_<global_step>.pth / D_<global_step>.pth，
而 svc_convert.py 与 chain_svc_convert.py 找的是 assets/weights/*maya_svc_e*.pth，
且依赖 train_log.txt 出现 "ALL DONE"。这两处原本没有任何环节负责，属链上断点。

本脚本补齐：
  1) 等训练结束（GPU 释放 + G_*.pth 已落盘）
  2) 导出最终 G 权重 -> assets/weights/maya_svc_e<step>.pth
  3) 建 faiss 索引     -> logs/maya_svc/added_*.index
  4) 变声 20 句念稿    -> _audition/gate/svc_edge/*.wav
  5) 评分              -> _audition/gate/report_svc_edge_*.json
  6) 写 "ALL DONE" 到 RVC/train_log.txt

用法：runtime\\python.exe F:\\self_project\\Sia-ai\\GPT-SoVITS\\tools\\svc_finish_chain.py
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

PKG = Path(r"F:\self_project\Sia-ai\RVC\pkg\RVC20260718Nvidia")
ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
RVC_DIR = Path(r"F:\self_project\Sia-ai\RVC")
TRAIN_LOG = RVC_DIR / "train_log.txt"
EXP_DIR = PKG / "logs" / "maya_svc"
PY = PKG / "runtime" / "python.exe"
SOVITS_PKG = ROOT / "GPT-SoVITS-v2pro-20261006"


def log(m):
    line = f"[{time.strftime('%Y/%m/%d %H:%M:%S')}] {m}"
    print(line, flush=True)
    try:
        with open(RVC_DIR / "finish_chain_log.txt", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def gpu_used_mb():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=30).stdout.strip()
        return int(out.split("\n")[0])
    except Exception:
        return -1


def g_weights():
    return sorted(EXP_DIR.glob("G_*.pth"))


def wait_train_done(timeout_h=8):
    log("等待 RVC 训练结束 ...")
    t0 = time.time()
    idle_hits = 0
    while time.time() - t0 < timeout_h * 3600:
        gws = g_weights()
        used = gpu_used_mb()
        if gws and 0 <= used < 300:
            idle_hits += 1
            # 连续 3 次（约 3 分钟）确认 GPU 已释放，避免 epoch 间隙误判
            if idle_hits >= 3:
                log(f"训练结束，G 权重: {[p.name for p in gws]}")
                return gws[-1]
        else:
            idle_hits = 0
        time.sleep(60)
    log("[TIMEOUT] 等待训练超时")
    return None


def latest_step(gw):
    m = re.search(r"G_(\d+)\.pth", gw.name)
    return int(m.group(1)) if m else 0


def main():
    gw = wait_train_done()
    if gw is None:
        sys.exit(1)

    # 2) 导出权重到 assets/weights/maya_svc_e<step>.pth
    step = latest_step(gw)
    dst_dir = PKG / "assets" / "weights"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"maya_svc_e{step}.pth"
    shutil.copyfile(gw, dst)
    log(f"[WRITE] {gw.name} -> {dst.name}")

    # 3) 建索引
    log("建 faiss 索引 ...")
    r = subprocess.run([str(PY), "train/train_index.py", "maya_svc", "v2", "logs", "4"],
                       capture_output=True, text=True, cwd=str(PKG))
    log(f"index rc={r.returncode}")
    if r.returncode != 0:
        print(r.stdout[-1500:], r.stderr[-1500:], flush=True)

    # 4) 变声
    log("变声 20 句念稿 ...")
    r = subprocess.run([str(PY), str(ROOT / "tools" / "svc_convert.py")],
                       capture_output=True, text=True, cwd=str(PKG))
    log(f"convert rc={r.returncode}")
    print(r.stdout[-1500:], r.stderr[-800:], flush=True)

    # 5) 评分
    log("评分 svc_edge ...")
    r = subprocess.run([str(PY), str(ROOT / "tools" / "eval_gate.py"), "score",
                        "--tags", "svc_edge"],
                       capture_output=True, text=True, cwd=str(SOVITS_PKG))
    log(f"score rc={r.returncode}")
    print(r.stdout[-2000:], r.stderr[-800:], flush=True)

    # 6) 标记完成
    with open(TRAIN_LOG, "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y/%m/%d %H:%M:%S')}] ALL DONE (by svc_finish_chain)\n")
    log("收尾链完成")


if __name__ == "__main__":
    main()
