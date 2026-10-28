"""摩耶参考音频广泛精选 v2（用官方全量重算的新标尺）
用法: python pick_refs.py
"""
import csv
import random
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, str(Path(__file__).parent))
from final_profile import VOICES, MAP, ROOT, work  # noqa: E402

OUT_DIR = ROOT / "_audition" / "ref2"


def main():
    with MAP.open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.reader(fh) if len(r) >= 2]
    text_of = {r[0]: (r[2] if len(r) > 2 else "") for r in rows}
    maya = sorted({r[0] for r in rows if r[1] == "摩耶"})

    random.seed(7)
    pick = random.sample(maya, min(2200, len(maya)))
    print(f"官方摩耶 {len(maya)} 条，抽 {len(pick)} 条精算…")
    with ProcessPoolExecutor(6) as ex:
        res = dict(ex.map(work, [(str(VOICES / f),) for f in pick], chunksize=16))

    cands = []
    for fp, ft in res.items():
        if not ft:
            continue
        name = Path(fp).name
        pref = name.split("_")[0]
        try:
            gid = int(name.split("_")[1].split(".")[0])
        except ValueError:
            continue
        if pref == "z0003" and gid <= 2030:  # 电话音效段
            continue
        if not (3.0 <= ft["dur"] <= 10.0 and ft["voicing"] >= 0.72):
            continue
        # 新标尺：摩耶日常中心 f0≈255 / 质心≈700
        if not (210 <= ft["f0_med"] <= 295 and 420 <= ft["centroid"] <= 1100):
            continue
        dist = abs(ft["f0_med"] - 255) / 50 + abs(ft["centroid"] - 700) / 300
        cands.append((dist, name, ft, pref))
    cands.sort()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    chosen, per_pref = [], {}
    for dist, name, ft, pref in cands:
        if per_pref.get(pref, 0) >= 3:
            continue
        per_pref[pref] = per_pref.get(pref, 0) + 1
        chosen.append((dist, name, ft))
        if len(chosen) >= 18:
            break

    lines = []
    for dist, name, ft in chosen:
        dst = OUT_DIR / (Path(name).stem + ".mp3")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(VOICES / name),
                        "-q:a", "4", str(dst)], check=True)
        lines.append(f"{Path(name).stem}  dur={ft['dur']:.1f}s f0={ft['f0_med']:.0f} "
                     f"ce={ft['centroid']:.0f} | {text_of.get(name, '')[:60]}")
    for l in lines:
        print("  " + l)
    (OUT_DIR / "_list.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n共 {len(lines)} 条 → {OUT_DIR}")


if __name__ == "__main__":
    main()
