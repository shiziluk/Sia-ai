"""抽查：挑高置信「会长」样本给用户试听，验证分类是否正确

选样：dist 升序（最像锚点）+ dur 2~8s + voi>=0.7，每个 z 包最多 2 条（防单包偏置），
另强制附上用户锚点 z0001_0306 作基准。
"""
import csv
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
VOICES = BASE / "_voices"
OUT = BASE / "_audition" / "check_huizhang"

rows = []
with open(BASE / "_classified_v2.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        if r["who"] != "会长":
            continue
        try:
            dur, voi = float(r["dur"] or 0), float(r["voicing"] or 0)
            dist = float(r["dist"] or 9)
        except ValueError:
            continue
        if 2.0 <= dur <= 8.0 and voi >= 0.7:
            rows.append((dist, r["file"]))

rows.sort()
seen, picked = {}, []
for d, name in rows:
    pkg = name.split("_")[0]
    if seen.get(pkg, 0) >= 2:
        continue
    seen[pkg] = seen.get(pkg, 0) + 1
    picked.append((d, name))
    if len(picked) >= 10:
        break

# 用户锚点基准强制入选
anchor = "z0001_0306.ogg"
if anchor not in [n for _, n in picked]:
    picked.insert(0, (float("nan"), anchor))

OUT.mkdir(parents=True, exist_ok=True)
for d, name in picked:
    tag = " [用户锚点基准]" if name == anchor else ""
    print(f"{name} dist={d}{tag}")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(VOICES / name),
         "-codec:a", "libmp3lame", "-q:a", "2",
         str(OUT / name.replace(".ogg", ".mp3"))],
        check=True)
print(f"\n共 {len(picked)} 条 -> {OUT}")
