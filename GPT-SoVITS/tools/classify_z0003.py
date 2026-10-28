"""锚点最近邻分类器 v2：全量 ogg → 角色归属

升级：断点续跑（已有 CSV 跳过）+ 多进程 + 增量写盘
用法: python classify_z0003.py <clip目录> <输出csv>
锚点 = 13 条用户标注（剔除电话样本）；加权欧氏距离，超阈值标"未识别"
"""
import csv
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from voice_profile_fast import analyze

LABELED = [
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\z0001\z0001_0306.ogg", "会长"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\z0001\z0001_0343.ogg", "老师"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\z4001\z4001_0022.ogg", "月岛叶"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_0073.ogg", "瑠奈"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_0220.ogg", "雪乃"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_0381.ogg", "瑠奈"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_0655.ogg", "月岛叶"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_2090.ogg", "摩耶"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_2094.ogg", "摩耶"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_2096.ogg", "摩耶"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_2262.ogg", "摩耶"),
]

FEATS = ["f0_med", "f0_p10", "f0_p90", "centroid_med"]
WEIGHTS = np.array([1.0, 1.0, 0.7, 0.7])
THRESH = 2.2
SCALE = np.array([60.0, 60.0, 60.0, 400.0])
FIELDS = ["file", "who", "dist", "dur", "f0_med", "f0_p10", "f0_p90", "centroid_med", "voicing"]


def load_anchors():
    anchors = {}
    for path, who in LABELED:
        f = analyze(Path(path))
        anchors.setdefault(who, []).append([f[k] for k in FEATS])
    names = sorted(anchors)
    A = np.array([np.mean(anchors[n], axis=0) for n in names])
    return names, A


def classify_one(args):
    p, names, A = args
    try:
        f = analyze(p)
    except Exception:
        return {"file": p.name, "who": "FAIL", "dist": "", "dur": "", "f0_med": "",
                "f0_p10": "", "f0_p90": "", "centroid_med": "", "voicing": ""}
    v = np.array([f[k] for k in FEATS])
    d = np.sqrt((((A - v) / SCALE) ** 2 * WEIGHTS).sum(axis=1))
    j = int(d.argmin())
    who = names[j] if d[j] < THRESH else "未识别"
    return {"file": p.name, "who": who, "dist": round(float(d[j]), 2), **f}


def main():
    clip_dir = Path(sys.argv[1])
    out = Path(sys.argv[2])

    names, A = load_anchors()
    print("anchors:", dict(zip(names, [len(n) for n in names])))

    done = set()
    write_header = not out.exists()
    if out.exists():
        with open(out, encoding="utf-8-sig") as fh:
            done = {r["file"] for r in csv.DictReader(fh)}
        print(f"resume: {len(done)} already classified")

    clips = [p for p in sorted(clip_dir.glob("*.ogg")) if p.name not in done]
    print(f"to classify: {len(clips)}")

    fh = open(out, "a", newline="", encoding="utf-8-sig")
    w = csv.DictWriter(fh, fieldnames=FIELDS)
    if write_header:
        w.writeheader()
    counts = {}
    with ProcessPoolExecutor(max_workers=6) as ex:
        for i, row in enumerate(ex.map(classify_one, [(p, names, A) for p in clips], chunksize=16), 1):
            w.writerow(row)
            counts[row["who"]] = counts.get(row["who"], 0) + 1
            if i % 200 == 0:
                fh.flush()
                print(f"... {i}/{len(clips)}  {counts}", flush=True)
    fh.flush()
    fh.close()
    print("DONE", counts)

    # 摩耶候选速报
    with open(out, encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    maya = [r for r in rows if r["who"] == "摩耶"]
    good = [r for r in maya if 3.0 <= float(r["dur"] or 0) <= 10.0 and float(r["voicing"] or 0) >= 0.7]
    print(f"\n摩耶 total={len(maya)}  参考_audio候选(3~10s,voicing>=0.7)={len(good)}")
    for r in sorted(good, key=lambda r: -float(r["voicing"]))[:25]:
        print(f"{r['file']}  dur={r['dur']}s f0={r['f0_med']} centroid={r['centroid_med']} voicing={r['voicing']}")


if __name__ == "__main__":
    main()
