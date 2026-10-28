"""终版声学画像：基于官方映射（_official_map.csv）全量重算各角色声学特征
并广泛精选摩耶参考音频 → _audition/ref2/
用法: python final_profile.py
"""
import csv
import random
import subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "_official_map.csv"
VOICES = ROOT / "_voices"
OUT_DIR = ROOT / "_audition" / "ref2"
SR = 16000
WIN, HOP = 1024, 512


def load_pcm(path: Path) -> np.ndarray:
    try:
        import soundfile as sf
        data, sr = sf.read(str(path), dtype="float32", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        if sr != SR:
            n = int(len(data) * SR / sr)
            data = np.interp(
                np.linspace(0, len(data) - 1, n), np.arange(len(data)), data
            ).astype(np.float32)
        return data
    except Exception:
        p = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le",
             "-ac", "1", "-ar", str(SR), "-"],
            capture_output=True)
        if not p.stdout:
            return np.zeros(0, dtype=np.float32)
        return np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0


def feats(pcm: np.ndarray):
    if len(pcm) < WIN * 2:
        return None
    frames = [pcm[i:i + WIN] for i in range(0, len(pcm) - WIN, HOP)]
    frames = [f for f in frames if np.sqrt((f ** 2).mean()) >= 1e-4]
    if len(frames) < 8:
        return None
    F = np.stack(frames)
    spec = np.abs(np.fft.rfft(F * np.hanning(WIN), axis=1)) ** 2
    freqs = np.fft.rfftfreq(WIN, 1 / SR)
    centroid = (spec * freqs).sum(1) / spec.sum(1)
    ac = np.fft.irfft(np.abs(np.fft.rfft(F, axis=1, n=WIN * 2)) ** 2, axis=1)
    ac /= (ac[:, :1] + 1e-9)
    lo, hi = SR // 400, SR // 60  # 60~400 Hz
    seg = ac[:, lo:hi]
    pk = seg.argmax(1) + lo
    v = ac[np.arange(len(ac)), pk]
    voiced = v > 0.35
    f0 = SR / pk[voiced]
    if len(f0) < 5:
        return None
    return {
        "dur": len(pcm) / SR,
        "f0_med": float(np.median(f0)),
        "f0_p10": float(np.percentile(f0, 10)),
        "f0_p90": float(np.percentile(f0, 90)),
        "centroid": float(np.median(centroid)),
        "voicing": float(voiced.mean()),
    }


def work(args):
    fp, = args
    try:
        return fp, feats(load_pcm(Path(fp)))
    except Exception:
        return fp, None


def main():
    with MAP.open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.reader(fh) if len(r) >= 2]
    text_of = {r[0]: (r[2] if len(r) > 2 else "") for r in rows}
    by_c = {}
    for r in rows:
        by_c.setdefault(r[1], []).append(r[0])

    random.seed(42)
    jobs, sampled = [], {}
    for c, files in by_c.items():
        files = sorted(set(files))
        pick = random.sample(files, min(400, len(files)))
        sampled[c] = pick
        jobs += [(str(VOICES / f),) for f in pick]

    print(f"官方角色 {len(by_c)} 个，抽样 {len(jobs)} 条计算中…")
    with ProcessPoolExecutor(6) as ex:
        res = dict(ex.map(work, jobs, chunksize=16))

    print("\n=== 终版声学画像（官方映射，每角色 ≤400 条）===")
    print(f"{'角色':<6} {'样本':>4} {'F0中位':>6} {'P10':>5} {'P90':>5} "
          f"{'音域':>5} {'质心':>6} {'浊音':>5} {'时长':>5}")
    stat = {}
    for c in sorted(by_c, key=lambda x: -len(by_c[x])):
        fs = [res[str(VOICES / f)] for f in sampled[c]]
        fs = [f for f in fs if f]
        if not fs:
            continue
        f0m = np.median([f["f0_med"] for f in fs])
        p10 = np.median([f["f0_p10"] for f in fs])
        p90 = np.median([f["f0_p90"] for f in fs])
        ce = np.median([f["centroid"] for f in fs])
        vo = np.median([f["voicing"] for f in fs])
        du = np.median([f["dur"] for f in fs])
        stat[c] = {"f0": f0m, "p10": p10, "p90": p90, "ce": ce,
                   "vo": vo, "du": du, "n": len(fs), "total": len(by_c[c])}
        print(f"{c:<6} {len(fs):>4} {f0m:>6.0f} {p10:>5.0f} {p90:>5.0f} "
              f"{p90 - p10:>5.0f} {ce:>6.0f} {vo:>5.2f} {du:>5.1f}")

    # --- 希亚匹配评分（人设：中性偏低偏稳、清亮不甜腻、克制） ---
    T_F0, T_CE = 240.0, 1550.0  # 目标：偏低音高 + 清亮质心
    print("\n=== 希亚人设匹配分（0~1，越高越配）===")
    scored = []
    for c, s in stat.items():
        if s["total"] < 300:  # 排除配角/男角
            continue
        f0s = max(0, 1 - abs(s["f0"] - T_F0) / 120)          # 音高中性
        ces = max(0, 1 - abs(s["ce"] - T_CE) / 900)          # 音色清亮
        ras = max(0, 1 - (s["p90"] - s["p10"]) / 200)        # 音域稳定
        score = 0.45 * f0s + 0.35 * ces + 0.20 * ras
        scored.append((score, c, f0s, ces, ras))
    scored.sort(reverse=True)
    for score, c, f0s, ces, ras in scored:
        print(f"{c:<6} 综合 {score:.3f}  (音高 {f0s:.2f} / 音色 {ces:.2f} / 稳定 {ras:.2f})")

    # --- 广泛精选摩耶参考音频 ---
    maya_files = sorted(set(by_c.get("摩耶", [])))
    pick = random.sample(maya_files, min(1500, len(maya_files)))
    print(f"\n从官方摩耶 {len(maya_files)} 条中抽 {len(pick)} 条精算特征…")
    with ProcessPoolExecutor(6) as ex:
        res2 = dict(ex.map(work, [(str(VOICES / f),) for f in pick], chunksize=16))

    cands = []
    for f, ft in res2.items():
        if not ft:
            continue
        name = Path(f).name
        pref = name.split("_")[0]
        try:
            gid = int(name.split("_")[1].split(".")[0])
        except ValueError:
            continue
        # 排除电话音效段；只留长句、高浊音、音高/质心在摩耶日常区间
        if pref == "z0003" and gid <= 2030:
            continue
        if not (3.0 <= ft["dur"] <= 10.0 and ft["voicing"] >= 0.72):
            continue
        if not (215 <= ft["f0_med"] <= 295 and 1250 <= ft["centroid"] <= 1800):
            continue
        # 贴近摩耶日常中心 = 越平常说话越好
        dist = abs(ft["f0_med"] - 250) / 60 + abs(ft["centroid"] - 1550) / 250
        cands.append((dist, name, ft, pref))
    cands.sort()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    chosen, per_pref = [], {}
    for dist, name, ft, pref in cands:
        if per_pref.get(pref, 0) >= 3:  # 每个场景包 ≤3 条，保证覆盖面
            continue
        per_pref[pref] = per_pref.get(pref, 0) + 1
        chosen.append((dist, name, ft))
        if len(chosen) >= 18:
            break

    list_lines = []
    for dist, name, ft in chosen:
        src = VOICES / name
        dst = OUT_DIR / (Path(name).stem + ".mp3")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src),
                        "-q:a", "4", str(dst)], check=True)
        line = (f"{Path(name).stem}  dur={ft['dur']:.1f}s f0={ft['f0_med']:.0f} "
                f"ce={ft['centroid']:.0f} | {text_of.get(name, '')[:60]}")
        list_lines.append(line)
        print("  " + line)
    (OUT_DIR / "_list.txt").write_text("\n".join(list_lines), encoding="utf-8")
    print(f"\n已输出 {len(chosen)} 条 → {OUT_DIR}")


if __name__ == "__main__":
    main()
