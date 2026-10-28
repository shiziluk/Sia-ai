"""探测3：全量提取场景索引表，与 ovk 包列表 / 声学分类三方对照

已确认标签格式（紧凑）：g00摩耶_0501 = <字母><2位序号><角色名>_<4位台词号>
"""
import re
from collections import Counter
from pathlib import Path

import csv

G = Path(r"F:\初恋1-1\初恋1比1")
BASE = Path(__file__).resolve().parent.parent

b = (G / "scene.chs").read_bytes()
s = b.decode("utf-16-le", errors="ignore")

# 1. 全量提取（紧凑格式）
pat = re.compile(r"([a-z])(\d{2})([\u4e00-\u9fff]{1,6})_(\d{4})")
tags = [(m.start(), m.group(1), m.group(2), m.group(3), m.group(4)) for m in pat.finditer(s)]
print(f"场景表条目: {len(tags)}")
print("角色分布:", dict(Counter(t[2] for t in tags).most_common()))

# 表的物理连续性：是否集中在一块
print(f"\n首条 @0x{tags[0][0]:x} 末条 @0x{tags[-1][0]:x}")
print("前 8 条:", [(t[1] + t[2], t[3], t[4]) for t in tags[:8]])

# 2. ovk 包列表
pkgs = sorted({p.name.split("_")[0] for p in (BASE / "_voices").glob("*.ogg")})
print(f"\novk 派生包数: {len(pkgs)}")
print("包名:", pkgs[:20], "..." if len(pkgs) > 20 else "")

# 3. 每个 z 包的声学判定主体
pkg_main = {}
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
print("\n各包判定主体（前 20 包）:")
for pkg in pkgs[:20]:
    top = by_pkg.get(pkg, [])
    print(f"  {pkg}: {top[:3]}")

# 4. 场景表按出现顺序展开成序列，试对齐：z000N = 表第 N 项？
seq = [(t[1] + t[2], t[2], int(t[4])) for t in tags]
print(f"\n对齐假设检验（z编号-1 = 表索引，取前 20 包）:")
for pkg in pkgs[:20]:
    idx = int(pkg[1:]) - 1
    if 0 <= idx < len(seq):
        sc, who, line = seq[idx]
        main = by_pkg.get(pkg, [(0, "?")])[0][1]
        print(f"  {pkg} -> 表[{idx}]={sc}_{line:04d} 角色={who} | 声学主体={main} {'<-- MATCH' if main==who else ''}")
