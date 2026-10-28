"""生成官方映射表 _official_map.csv + 声学分类吻合率混淆矩阵

KOE 9位编号 = z包号(4位) + TOC id(5位前导零) -> ogg 名 zXXXX_YYYY(4位id)
"""
import csv
from collections import Counter, defaultdict
from pathlib import Path

V = Path(r"F:\self_project\Sia-ai\GPT-SoVITS\_ssu_out\voices")
BASE = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")

# 1. 遍历角色目录 -> koe_no -> ogg 名
koe2char = {}
for d in V.iterdir():
    if not d.is_dir():
        continue
    for f in d.glob("KOE(*).ogg"):
        koe9 = f.stem[4:-1]  # KOE(XXXXXXXXX)
        pkg, id5 = koe9[:4], int(koe9[4:])
        koe2char[f"z{pkg}_{id5:04d}.ogg"] = d.name

print(f"官方映射条目: {len(koe2char)}")

# 2. join 台词文本
text = {}
with open(V / "koe_master.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        k = r["koe_no"].zfill(9)
        pkg, id5 = k[:4], int(k[4:])
        text[f"z{pkg}_{id5:04d}.ogg"] = r["text"]

# 3. 写官方映射表
rows = []
for fn, ch in sorted(koe2char.items()):
    rows.append({"file": fn, "character": ch, "text": text.get(fn, "")})
with open(BASE / "_official_map.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["file", "character", "text"])
    w.writeheader()
    w.writerows(rows)
print(f"_official_map.csv 写入 {len(rows)} 行")

# 4. 与声学分类对照的混淆矩阵
name_map = {"碧": "会长", "愛里": "老师", "叶": "月岛叶"}  # 官方名->声学类名
off = {r["file"]: name_map.get(r["character"], r["character"]) for r in rows}
acoustic = {}
with open(BASE / "_classified_v2.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        acoustic[r["file"]] = r["who"]

common = set(off) & set(acoustic)
conf = defaultdict(Counter)
for fn in common:
    conf[off[fn]][acoustic[fn]] += 1

major = ["摩耶", "会长", "老师", "雪乃", "月岛叶", "瑠奈"]  # 已映射后的类名（碧→会长、愛里→老师、叶→月岛叶）
print(f"\n===== 混淆矩阵（官方 -> 声学，共 {len(common)} 条）=====")
hdr = "官方\\声学  " + " ".join(f"{m:>7}" for m in major)
print(hdr)
for m in major:
    row = conf.get(m, Counter())
    tot = sum(row.values())
    line = " ".join(f"{row.get(x, 0):>7}" for x in major)
    print(f"{m:<8} {line}  | 共{tot}")
