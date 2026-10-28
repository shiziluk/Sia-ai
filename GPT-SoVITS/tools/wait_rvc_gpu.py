# -*- coding: utf-8 -*-
"""等 RVC 训练的 GPU 空闲窗口: s1_train 退出 + api_v2 不在 + 显存 < 1500MB + 评测报告已出。
全部满足则退出 0, 否则每 5 分钟复查。
"""
import subprocess
import time
from pathlib import Path

GATE = Path(r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\gate")


def s1_alive():
    out = subprocess.run(["wmic", "process", "where", "name='python.exe'", "get", "commandline"],
                         capture_output=True, text=True).stdout
    return "s1_train" in out


def api_listening():
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    return ":9880" in out and "LISTENING" in out.upper()


def gpu_low():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip()
    try:
        return int(out) < 1500
    except ValueError:
        return False


def report_done():
    return any(GATE.glob("report_*.json"))


def main():
    while True:
        if not s1_alive() and not api_listening() and gpu_low() and report_done():
            print("GPU free + eval report done -> start RVC train", flush=True)
            return
        time.sleep(300)


if __name__ == "__main__":
    main()
