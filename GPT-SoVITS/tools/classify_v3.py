"""分类器 v3：锚点增强重分类（纯 CSV 查表，秒级）

1) 摩耶锚点 = 用户 ground truth z0003_1991~2330 区间的干净样本（voicing>=0.6, dur>=1.0）
2) 其他角色锚点 = v1 结果中 dist<=0.6 的高置信样本（半监督扩充，每类上限 80）
3) 全量重分类 → _classified_v2.csv
"""
import csv
from collections import Counter
from pathlib import Path

import numpy as np

V1 = Path(r"F:\self_project\Sia-ai\GPT-SoVITS\_classified.csv")
OUT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS\_classified_v2.csv")
FEATS = ["f0_med", "f0_p10", "f0_p90", "centroid_med"]
WEIGHTS = np.array([1.0, 1.0, 0.7, 0.7])
SCALE = np.array([60.0, 60.0, 60.0, 400.0])
THRESH = 1.6          # 锚点增强后收紧阈值


def fvec(r):
    v = [float(r[k]) for k in FEATS]
    return np.array(v) if all(x > 0 for x in v) else None


def main():
    rows = list(csv.DictReader(open(V1, encoding="utf-8-sig")))
    dedup = {}
    for r in rows:                      # 并发续跑产生的重复行，保留最后一条
        dedup[r["file"]] = r
    rows = list(dedup.values())
    print("v1 rows:", len(rows), "(deduped)")

    def gid(r):
        try:
            return int(r["file"].split("_")[1].split(".")[0])
        except Exception:
            return -1

    anchors = {}   # who -> [vec]
    for r in rows:
        who, v = r["who"], fvec(r)
        if v is None:
            continue
        dur, voi = float(r["dur"] or 0), float(r["voicing"] or 0)
        if who == "摩耶":
            # ground truth 区间 + 干净度过滤
            if r["file"].startswith("z0003_") and 1991 <= gid(r) <= 2330 and voi >= 0.6 and dur >= 1.0:
                anchors.setdefault("摩耶", []).append(v)
        elif voi >= 0.6 and dur >= 1.0 and float(r["dist"] or 9) <= 0.6:
            anchors.setdefault(who, []).append(v)

    # 每类上限 80（优先低 dist/接近锚心的），摩耶不限
    for who in list(anchors):
        vs = anchors[who]
        if who != "摩耶" and len(vs) > 80:
            mu = np.mean(vs, axis=0)
            vs.sort(key=lambda v: float(((v - mu) ** 2).sum()))
            anchors[who] = vs[:80]

    names = sorted(anchors)
    A = {n: np.array(anchors[n]) for n in names}
    print({n: len(anchors[n]) for n in names})

    # 分类：取样本到各类锚点集的最小距离
    out = open(OUT, "w", newline="", encoding="utf-8-sig")
    w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
    w.writeheader()
    counts = Counter()
    for r in rows:
        v = fvec(r)
        if v is None:
            r["who"], r["dist"] = "无效(静音/电话)", ""
        else:
            best, bd = "未识别", 9e9
            for n in names:
                d = float(np.sqrt((((A[n] - v) / SCALE) ** 2 * WEIGHTS).sum(axis=1)).min())
                if d < bd:
                    best, bd = n, d
            r["who"], r["dist"] = (best if bd < THRESH else "未识别"), round(bd, 2)
        counts[r["who"]] += 1
        w.writerow(r)
    out.close()
    print("v2 verdicts:", dict(counts))
    print("csv ->", OUT)


if __name__ == "__main__":
    main()
