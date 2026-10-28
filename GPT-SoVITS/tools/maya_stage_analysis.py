"""摩耶按剧情阶段的声学演化分析（CPU 任务, 不占 GPU）

阶段: a=序章 b=共通线(不熟期) c/d/e/f=他线客串 g=摩耶线(情侣初期) h/i/j=附录后日谈/if
用法: runtime\\python.exe maya_stage_analysis.py
"""
import csv
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from voice_profile_fast import analyze, load_pcm

ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "_ssu_out" / "koe_master.csv"
MAP = ROOT / "_official_map.csv"
VOICES = ROOT / "_voices"

STAGE_OF = {"a": "0序章", "b": "1共通(不熟)", "c": "2他线客串", "d": "2他线客串",
            "e": "2他线客串", "f": "2他线客串", "g": "3摩耶线(情侣)", "h": "4后日谈/if",
            "i": "4后日谈/if", "j": "4后日谈/if"}


def main():
    # koe_no -> callsite
    koe2site = {}
    with MASTER.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            if r["callsite"]:
                koe2site[int(r["koe_no"])] = r["callsite"]

    groups = defaultdict(list)
    with MAP.open(encoding="utf-8-sig", newline="") as fh:
        for r in csv.reader(fh):
            if len(r) < 3 or r[1] != "摩耶":
                continue
            f = r[0]                       # z0003_0819.ogg
            pkg, idx = f[1:5], f[6:10]
            koe = int(pkg + idx.zfill(5))
            site = koe2site.get(koe, "")
            tag = site.split("!")[-1][:1] if site else "?"
            stage = STAGE_OF.get(tag, "9未知")
            wav = VOICES / f
            if wav.exists():
                groups[stage].append(wav)

    rng = random.Random(42)
    print(f"{'阶段':<12}{'样本':>5}  {'F0中位':>6} {'p10':>5} {'p90':>5} {'质心':>6} {'浊音比':>6} {'时长中位':>7}")
    for stage in sorted(groups):
        pool = [w for w in groups[stage]]
        rng.shuffle(pool)
        sample = []
        for w in pool[:250]:
            try:
                d = analyze(w)
                if 1.2 <= d["dur"] <= 15 and d["voicing"] >= 0.3:
                    sample.append(d)
            except Exception:
                pass
        if not sample:
            print(f"{stage:<12}{len(pool):>5}  (有效样本不足)")
            continue
        f0s = sorted(d["f0_med"] for d in sample)
        cen = sorted(d["centroid_med"] for d in sample)
        dur = sorted(d["dur"] for d in sample)
        vr = sum(d["voicing"] for d in sample) / len(sample)
        n = len(sample)
        print(f"{stage:<12}{len(pool):>5}  {f0s[n//2]:>6.0f} {f0s[n//10]:>5.0f} {f0s[9*n//10]:>5.0f} "
              f"{cen[n//2]:>6.0f} {vr:>6.2f} {dur[n//2]:>6.1f}s")
        # 组内 F0 的 p90-p10 跨度 = 音域, 额外输出
    print("\n注: F0 单位 Hz, 质心单位 Hz; 每组最多抽 250 条, 1.2~15s 且浊音占比>=0.3")


if __name__ == "__main__":
    main()
