"""分析 koe_master.csv：官方角色分布 + 会长/摩耶核验"""
import csv
from collections import Counter
from pathlib import Path

CSV = Path(r"F:\self_project\Sia-ai\GPT-SoVITS\_ssu_out\koe_master.csv")

chars = Counter()
durs = Counter()
mayaka = []
kaicho = []
with open(CSV, encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        c = r["character"] or "(无角色)"
        chars[c] += 1
        try:
            durs[c] += float(r["duration_sec"] or 0)
        except ValueError:
            pass
        if c == "摩耶":
            mayaka.append(r)
        if "会長" in c or "会长" in c:
            kaicho.append(r)

print("===== 官方角色分布 =====")
for c, n in chars.most_common():
    m, s = divmod(int(durs[c]), 60)
    h, m = divmod(m, 60)
    print(f"  {c}: {n} 条, {h}:{m:02d}:{s:02d}")

print(f"\n会長: {len(kaicho)} 条")
for r in kaicho[:8]:
    print(f"  koe={r['koe_no']} dur={r['duration_sec'][:5]} {r['text'][:40]}")

print(f"\n摩耶: {len(mayaka)} 条, 样例:")
for r in mayaka[:8]:
    print(f"  koe={r['koe_no']} dur={r['duration_sec'][:5]} callsite={r['callsite'][:60]}")
    print(f"      {r['text'][:50]}")

# koe_no 与 ogg 文件名的映射核验：ground truth z0003_1991~2330=摩耶
# koe_no 疑似 = 包号*100 + TOC id（100019=1000*100+19 不符），改用工具抽取核实
