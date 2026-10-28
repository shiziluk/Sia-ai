"""探测2：挖 scene.chs 的角色名上下文 + 场景标签表全貌

目标：建立 z包号 ↔ 场景标签(含角色名) ↔ 语音 的官方映射链
"""
import re
from collections import Counter
from pathlib import Path

G = Path(r"F:\初恋1-1\初恋1比1")
b = (G / "scene.chs").read_bytes()

# 1. 49 处「摩耶」上下文（UTF-16LE 解码窗口）
enc = "摩耶".encode("utf-16-le")
pos, start = [], 0
while True:
    i = b.find(enc, start)
    if i < 0:
        break
    pos.append(i)
    start = i + 1
print(f"===== 「摩耶」{len(pos)} 处，上下文样例 =====")
for i, p in enumerate(pos[:12]):
    lo, hi = max(0, p - 60), min(len(b), p + 120)
    ctx = b[lo:hi].decode("utf-16-le", errors="ignore")
    ctx = "".join(c if c.isprintable() else "·" for c in ctx)
    print(f"[{i}] @0x{p:x}: {ctx}")

# 2. 全量标签提取：模式 <字母><2位序号>_<角色名>_<4位数字>
s_all = b.decode("utf-16-le", errors="ignore")
pat = re.compile(r"[a-z]\d{2}_[\u4e00-\u9fff]{1,6}_\d{4}")
tags = pat.findall(s_all)
print(f"\n===== 标签表：共 {len(tags)} 条 =====")
letters = Counter(t[0] for t in tags)
print("字母分布:", dict(sorted(letters.items())))
uniq_prefix = Counter("_".join(t.split("_")[:2]) for t in tags)
print(f"唯一前缀数: {len(uniq_prefix)}")
for k, v in sorted(uniq_prefix.items())[:40]:
    print(f"  {k}: {v}")

# 3. voice/koe/ovk 关键词
for kw in ["voice", "koe", "ovk", "wav"]:
    n = s_all.lower().count(kw)
    if n:
        first = s_all.lower().find(kw)
        print(f"\n'{kw}' UTF16: {n} 处, first={hex(first*2)}")
        print("  ctx:", "".join(c if c.isprintable() else "·" for c in s_all[max(0,first-30):first+50]))
