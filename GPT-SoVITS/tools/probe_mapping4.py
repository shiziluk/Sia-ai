"""探测4：dump 场景表原始明文段 + 包号↔台词号集合对照

新假设：z 包号 = 表中 4 位台词号
"""
import csv
import re
from collections import Counter
from pathlib import Path

G = Path(r"F:\初恋1-1\初恋1比1")
BASE = Path(__file__).resolve().parent.parent

b = (G / "scene.chs").read_bytes()
s = b.decode("utf-16-le", errors="ignore")

# 1. dump 表区域原始明文（首条 0x295f = 字符位 0x295f//2）
char_off = 0x295f // 2
seg = s[char_off - 400: char_off + 400]
seg = "".join(c if c.isprintable() else "·" for c in seg)
print("===== 表区域原始明文（±400 字符）=====")
print(seg)

# 2. 修正角色统计：group(3) 才是角色名（允许片假名/全角）
pat = re.compile(r"([a-z])(\d{2})([^\d_]{1,8})_(\d{4})")
tags = [(m.group(1), m.group(2), m.group(3), m.group(4)) for m in pat.finditer(s)]
print(f"\n===== 全量标签 {len(tags)} 条 =====")
print("角色分布:", dict(Counter(t[2] for t in tags).most_common()))
letter = Counter(t[0] + t[2] for t in tags)
print("字母+角色:", dict(letter.most_common(15)))
lines = {int(t[3]) for t in tags}
print(f"台词号范围: {min(lines)} ~ {max(lines)}, 唯一 {len(lines)} 个")

# 3. 全部包号
pkgs = sorted({p.name.split("_")[0] for p in (BASE / "_voices").glob("*.ogg")})
pnums = {int(p[1:]) for p in pkgs}
print(f"\novk 包号范围: {min(pnums)} ~ {max(pnums)}, 共 {len(pnums)} 个")

inter = lines & pnums
print(f"包号∩台词号: {len(inter)} 个")
print(f"台词号命中包的比例: {len(inter)}/{len(lines)} = {len(inter)/len(lines):.1%}")
print(f"包号命中台词号的比例: {len(inter)}/{len(pnums)} = {len(inter)/len(pnums):.1%}")

# 4. 各包声学主体 vs 台词号角色（用命中交集验）
with open(BASE / "_classified_v2.csv", encoding="utf-8-sig") as f:
    cnt = Counter()
    for r in csv.DictReader(f):
        pkg = r["file"].split("_")[0]
        cnt[(pkg, r["who"])] += 1
by_pkg = {}
for (pkg, who), n in cnt.items():
    by_pkg.setdefault(pkg, []).append((n, who))
for pkg in by_pkg:
    by_pkg[pkg].sort(reverse=True)

tag_by_line = {}
for t in tags:
    tag_by_line[int(t[3])] = t[2]  # 台词号 -> 角色名
print("\n===== 交集包：声学主体 vs 台词号角色 =====")
ok = bad = 0
for p in sorted(inter)[:40]:
    pkg = f"z{p:04d}"
    main = by_pkg.get(pkg, [(0, "?")])[0][1]
    role = tag_by_line.get(p, "?")
    m = "MATCH" if main == role else ""
    if m:
        ok += 1
    else:
        bad += 1
    print(f"  {pkg}: 声学={main} vs 表角色={role} {m}")
print(f"前 40 交集包一致率: {ok}/{ok+bad}")
