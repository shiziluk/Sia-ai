"""v3 分类复验 + 电话段定位 + 参考音频候选圈定

用户 ground truth：z0003_1991 ~ z0003_2330 全部为摩耶，
其中开头若干条是"模拟打电话"音效（带限失真，音色≠真实摩耶）。

步骤：
  1. 区间内逐条重提取特征，加算 hp3k（>3.4kHz 能量占比）定位电话段边界
  2. 复验 _classified_v2.csv 在区间内的判定准确率（全区间 / 排除电话段）
  3. 干净段圈定参考音频候选（dur 3~10s、voicing>=0.7、非电话），转 mp3 供试听
"""
import csv
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from voice_profile_fast import FRAME, HOP, SR, analyze, load_pcm

BASE = Path(__file__).resolve().parent.parent
VOICES = BASE / "_voices"
GT_LO, GT_HI = 1991, 2330  # 含两端


def hp3k(path: Path) -> float:
    """>3.4kHz 频带能量占比（电话音效带限 → 接近 0）"""
    x = load_pcm(path)
    n = max((len(x) - FRAME) // HOP, 0)
    if n == 0:
        return 0.0
    idx = np.arange(n)[:, None] * HOP + np.arange(FRAME)[None, :]
    frames = x[idx] * np.hanning(FRAME).astype(np.float32)
    spec = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(FRAME, 1 / SR)
    tot = spec.sum(axis=1)
    hi = spec[:, freqs > 3400].sum(axis=1)
    return float(np.mean(hi / np.maximum(tot, 1e-9)))


def main():
    # ---- 读 v3 结果 ----
    v3 = {}
    with open(BASE / "_classified_v2.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            v3[r["file"]] = r

    # ---- 1. 区间逐条提取特征 + hp3k ----
    print("id | dur | f0_med | cent | voi | hp3k | v3判定")
    feats = {}
    for gid in range(GT_LO, GT_HI + 1):
        name = f"z0003_{gid:04d}.ogg"
        p = VOICES / name
        if not p.exists():
            continue
        a = analyze(p)
        a["hp3k"] = round(hp3k(p), 3)
        a["v3"] = v3.get(name, {}).get("who", "?")
        feats[gid] = a
        print(f"{gid} | {a['dur']} | {a['f0_med']} | {a['centroid_med']} | "
              f"{a['voicing']} | {a['hp3k']} | {a['v3']}")

    # ---- 2. 定位电话段：hp3k 连续异常（<0.02 视为带限）----
    ids = sorted(feats)
    phone_ids = [g for g in ids if feats[g]["hp3k"] < 0.02 and feats[g]["dur"] > 0]
    print(f"\nhp3k<0.02 的条目数: {len(phone_ids)} / {len(ids)}")
    if phone_ids:
        # 找前缀连续段
        cut = phone_ids[0]
        prev = cut
        for g in phone_ids[1:]:
            if g == prev + 1:
                prev = g
                cut = g
            else:
                break
        print(f"开头连续电话段: {ids[0]} ~ {cut}")
        clean_lo = cut + 1
    else:
        clean_lo = ids[0]

    # ---- 3. 复验 v3 准确率 ----
    all_ok = sum(1 for g in ids if feats[g]["v3"] == "摩耶")
    clean_ids = [g for g in ids if g >= clean_lo and feats[g]["hp3k"] >= 0.02]
    clean_ok = sum(1 for g in clean_ids if feats[g]["v3"] == "摩耶")
    print(f"\nv3 复验: 全区间 {all_ok}/{len(ids)} = {all_ok/len(ids):.1%}")
    print(f"v3 复验: 排除电话后 {clean_ok}/{len(clean_ids)} = "
          f"{clean_ok/len(clean_ids):.1%}" if clean_ids else "无干净样本")

    # ---- 4. 参考音频候选：干净段 dur 3~10s voi>=0.7，dist 最小优先 ----
    cand = []
    for g in clean_ids:
        a = feats[g]
        if 3.0 <= a["dur"] <= 10.0 and a["voicing"] >= 0.7:
            d = v3.get(f"z0003_{g:04d}.ogg", {}).get("dist", "9")
            cand.append((float(d or 9), g, a))
    cand.sort()
    print(f"\n参考音频候选（干净+3~10s+voi>=0.7）: {len(cand)} 条，前 12:")
    outdir = BASE / "_audition" / "ref"
    outdir.mkdir(parents=True, exist_ok=True)
    for d, g, a in cand[:12]:
        name = f"z0003_{g:04d}.ogg"
        print(f"  {name} dist={d} dur={a['dur']} f0={a['f0_med']} "
              f"cent={a['centroid_med']} voi={a['voicing']}")
        dst = outdir / (name.replace(".ogg", ".mp3"))
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(VOICES / name),
             "-codec:a", "libmp3lame", "-q:a", "2", str(dst)],
            check=True)
    print(f"\nmp3 已输出到 {outdir}")


if __name__ == "__main__":
    main()
