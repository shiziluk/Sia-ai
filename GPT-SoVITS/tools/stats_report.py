"""终版报告：基于 _classified_v2.csv（v3 分类，ground truth 复验 85.3%）
统计各角色声学画像分布，量化匹配希亚人设。

希亚人设 → 声学目标映射：
  人造意识/偏男孩子气 → F0 偏低（中性少年感，目标 ~200Hz）
  情感克制不言情化   → 音域波动小（p90-p10 span 小，目标 ~90Hz）
  清亮不甜腻         → 频谱质心中亮（太暗=御姐太亮=甜萝莉，目标 ~1600Hz）
"""
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parent.parent

# 人设目标参数
T_F0, W_F0 = 200.0, 80.0      # 音高：偏低中性
T_SPAN, W_SPAN = 90.0, 60.0   # 音域：克制平稳
T_CENT, W_CENT = 1600.0, 500.0  # 音色：清亮不甜腻
W_PITCH, W_STABLE, W_BRIGHT = 0.4, 0.3, 0.3


def gauss(x, t, w):
    return math.exp(-((x - t) / w) ** 2)


def main():
    groups = defaultdict(list)
    with open(BASE / "_classified_v2.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            who = r["who"]
            if who in ("未识别", "无效(静音/电话)"):
                continue
            try:
                f0m = float(r["f0_med"] or 0)
            except ValueError:
                continue
            if f0m <= 0:  # 无浊音段
                continue
            groups[who].append({
                "f0": f0m,
                "span": float(r["f0_p90"] or 0) - float(r["f0_p10"] or 0),
                "cent": float(r["centroid_med"] or 0),
            })

    print(f"{'角色':<6} {'样本':>6} {'f0中位':>7} {'f0四分位':>13} "
          f"{'span中位':>8} {'质心中位':>8} | {'音高':>5} {'平稳':>5} {'明亮':>5} {'综合':>5}")
    rows = []
    for who, items in groups.items():
        f0 = np.array([i["f0"] for i in items])
        span = np.array([i["span"] for i in items])
        cent = np.array([i["cent"] for i in items])
        # 用中位数算分（稳健，抗激动段拖累）
        f0m, spanm, centm = np.median(f0), np.median(span), np.median(cent)
        s_pitch = gauss(f0m, T_F0, W_F0)
        s_stable = gauss(spanm, T_SPAN, W_SPAN)
        s_bright = gauss(centm, T_CENT, W_CENT)
        s_total = W_PITCH * s_pitch + W_STABLE * s_stable + W_BRIGHT * s_bright
        rows.append((s_total, who, len(items), f0m, f0m, spanm, centm,
                     s_pitch, s_stable, s_bright))
    rows.sort(reverse=True)
    for s_total, who, n, f0m, _, spanm, centm, sp, ss, sb in rows:
        q1 = np.percentile([i["f0"] for i in groups[who]], 25)
        q3 = np.percentile([i["f0"] for i in groups[who]], 75)
        print(f"{who:<6} {n:>6} {f0m:>7.0f} {f'{q1:.0f}~{q3:.0f}':>13} "
              f"{spanm:>8.0f} {centm:>8.0f} | {sp:>5.2f} {ss:>5.2f} {sb:>5.2f} "
              f"{s_total:>5.2f}")


if __name__ == "__main__":
    main()
