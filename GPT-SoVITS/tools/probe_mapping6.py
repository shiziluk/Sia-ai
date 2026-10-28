"""探测6：找 scene.chs 中的语音指令与 ovk 引用形式

思路：
  1. dump 全部 $ 分隔标识符（指令名/变量名表），找语音相关（vo/koe/snd/wav）
  2. 试搜 ovk 包号的各种引用形式：z0003 / 0003 / #0003（UTF-16LE）
"""
import re
from pathlib import Path

G = Path(r"F:\初恋1-1\初恋1比1")
b = (G / "scene.chs").read_bytes()
s = b.decode("utf-16-le", errors="ignore")

# 1. 全部标识符（$ 分隔或长 ASCII 串）
idents = set(re.findall(r"[A-Za-z][A-Za-z0-9_]{3,}", s))
print(f"唯一标识符: {len(idents)}")
kw = [i for i in idents if re.search(r"vo|koe|snd|wav|bgm|se|voice|sound", i, re.I)]
print("音声相关标识符:")
for i in sorted(kw):
    print("  ", i)

# 2. 包号引用形式搜索
for form, label in [
    ("z0003", "z0003"),
    ("0003", "0003裸"),
    ("#0003", "#0003"),
    ("\"0003\"", "引号0003"),
]:
    enc = form.encode("utf-16-le")
    n, first, start = 0, -1, 0
    while True:
        i = b.find(enc, start)
        if i < 0:
            break
        n += 1
        if first < 0:
            first = i
        start = i + 1
    if n:
        ctx = s[max(0, first // 2 - 40): first // 2 + 60]
        ctx = "".join(c if c.isprintable() else "·" for c in ctx)
        print(f"\n[{label}] {n} 处, first=0x{first:x}")
        print("   ", ctx)
    else:
        print(f"\n[{label}] 0 处")

# 3. z+4位数字 的 UTF-16 模式（任意包号）
m = re.findall(r"z\d{4}", s)
print(f"\nz+4位数字 模式: {len(m)} 处, 样例 {Counter(m).most_common(10) if m else '-'}")

# 4. 找台词文本区：先定位「 引号字符的分布（193 个），看第一条上下文
pos = s.find("「")
if pos >= 0:
    ctx = s[max(0, pos - 80): pos + 120]
    ctx = "".join(c if c.isprintable() else "·" for c in ctx)
    print(f"\n首个「@字符{pos}: {ctx}")
