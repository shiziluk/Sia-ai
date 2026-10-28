"""探测5：精确验证 z包号 ↔ 场景表台词号(多角色集合)

要点：
  - 同一台词号被多条角色线共享 -> 台词号映射到角色集合，声学主体∈集合 即命中
  - 顺带打印包号分布，判断编号体系
"""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

G = Path(r"F:\初恋1-1\初恋1比1")
BASE = Path(__file__).resolve().parent.parent

b = (G / "scene.chs").read_bytes()
s = b.decode("utf-16-le", errors="ignore")

pat = re.compile(r"([a-z])(\d{2})([^\d_]{1,8})_(\d{4})")
tags = [(m.group(1), m.group(2), m.group(3), int(m.group(4))) for m in pat.finditer(s)]

# 台词号 -> [(字母,序号,角色)]
line2roles = defaultdict(list)
for letter, seq, who, line in tags:
    line2roles[line].append(f"{letter}{seq}{who}")

# 包号 -> 声学主体
pkgs = sorted({p.name.split("_")[0] for p in (BASE / "_voices").glob("*.ogg")})
pnums = sorted({int(p[1:]) for p in pkgs})
with open(BASE / "_classified_v2.csv", encoding="utf-8-sig") as f:
    cnt = Counter()
    for r in csv.DictReader(f):
        cnt[(r["file"].split("_")[0], r["who"])] += 1
by_pkg = {}
for (pkg, who), n in cnt.items():
    by_pkg.setdefault(pkg, []).append((n, who))
for pkg in by_pkg:
    by_pkg[pkg].sort(reverse=True)

print(f"===== 包号分布（百位段）=====")
hist = Counter(p // 100 * 100 for p in pnums)
for k in sorted(hist):
    print(f"  {k:04d}~{k+99:04d}: {hist[k]}")

print(f"\n===== 包号∈台词号集 的命中检验 =====")
in_tab = [p for p in pnums if p in line2roles]
print(f"包号命中台词号: {len(in_tab)}/{len(pnums)}")
ok = bad = 0
for p in in_tab[:30]:
    pkg = f"z{p:04d}"
    main = by_pkg.get(pkg, [(0, "?")])[0][1]
    roles = line2roles[p]
    hit = main in roles
    ok += hit
    bad += not hit
    print(f"  {pkg}: 声学={main} | 表[{p}]={roles} {'' if hit else '<-- MISS'}")
print(f"一致 {ok} / 不一致 {bad}")

# 台词号全部样例（前 25 个，含角色集合）
print(f"\n===== 台词号样例（前 25）=====")
for line in sorted(line2roles)[:25]:
    print(f"  {line:04d}: {line2roles[line]}")
