# -*- coding: utf-8 -*-
"""从 _training/wav 挑摩耶切片做 RVC 训练集(小样 ~15 分钟)。
规则: 3-10s 完整句(非空台词), 三个时期(早期z0-z2/g线z3-z5/后日谈z6+)均衡抽样。
输出: RVC/dataset_maya/*.wav + manifest.csv
用法: runtime\\python.exe tools\\pick_maya_rvc.py [--minutes 15]
"""
import csv
import random
import shutil
import wave
from pathlib import Path

ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
MAYA_LIST = ROOT / "_training" / "maya.list"
OUT = Path(r"F:\self_project\Sia-ai\RVC\dataset_maya")

random.seed(20261028)

# 台词清洗: 去省略号/标点后不足 4 字的视为无效
BAD = set("…。、！？，,.!?~～ーー ")


def valid_text(t):
    return len([c for c in t if c not in BAD]) >= 4


def wav_dur(p):
    try:
        with wave.open(str(p), "rb") as w:
            return w.getnframes() / w.getframerate()
    except Exception:
        return 0.0


def era_of(name):
    z = int(name[1:5])  # z0003 -> 3
    if z < 3000:
        return "early"
    if z < 6000:
        return "mid"
    return "late"


def main(minutes=15):
    rows = []
    for line in MAYA_LIST.read_text(encoding="utf-8").splitlines():
        parts = line.split("|")
        if len(parts) < 4:
            continue
        p, text = Path(parts[0]), parts[3]
        if not p.exists() or not valid_text(text):
            continue
        d = wav_dur(p)
        if 3.0 <= d <= 10.0:
            rows.append((p, d, text, era_of(p.name)))
    print(f"候选: {len(rows)} 条 (3-10s 完整句)")
    by_era = {}
    for r in rows:
        by_era.setdefault(r[3], []).append(r)
    for k, v in sorted(by_era.items()):
        print(f"  {k}: {len(v)} 条")

    total = minutes * 60
    per_era = total // 3
    OUT.mkdir(parents=True, exist_ok=True)
    picked = []
    for era, target in by_era.items():
        # 按时长升序的均匀分位抽样: 保证音高/语速多样性
        pool = sorted(by_era[era], key=lambda r: r[1])
        take, acc, i, step = [], 0.0, 0, max(1, len(pool) * 3 // (per_era * 10))
        random.shuffle(pool)
        for r in pool:
            if acc >= per_era:
                break
            take.append(r)
            acc += r[1]
        picked.extend(take)
        print(f"  取 {era}: {len(take)} 条 {acc:.0f}s")
    random.shuffle(picked)
    acc = 0.0
    with open(OUT / "manifest.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["file", "dur", "era", "text"])
        for p, d, text, era in picked:
            shutil.copy2(p, OUT / p.name)
            w.writerow([p.name, f"{d:.1f}", era, text])
            acc += d
    print(f"训练集: {len(picked)} 条 / {acc/60:.1f} 分钟 -> {OUT}")


if __name__ == "__main__":
    import sys
    main(int(sys.argv[sys.argv.index("--minutes") + 1]) if "--minutes" in sys.argv else 15)
