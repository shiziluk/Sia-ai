"""用 scene.chs 名称表的语音号指纹，在 327 个 ovk 中找对应容器"""
import re
import struct
from pathlib import Path

SCENE = Path(r"F:\初恋1-1\初恋1比1\scene.chs")
KOE = Path(r"F:\初恋1-1\初恋1比1\koe")

# 1) 全文件扫名称表（字母+2位序号+角色_4位号）
data = SCENE.read_bytes()
head = data[:60000].decode("utf-16-le", errors="ignore")
pat = re.compile(r"([a-z]{1,2})(\d{2})([\u4e00-\u9fffA-Za-z]+)_(\d{4})")
want = {}   # num -> (letter, seq, name)
for m in pat.finditer(head):
    letter, seq, name, num = m.groups()
    want.setdefault(int(num), (letter, seq, name))
print("names:", len(want), "unique nums")
by_char = {}
for num, (l, s, n) in want.items():
    by_char.setdefault(n, []).append(num)
print({k: len(v) for k, v in by_char.items()})

# 2) 扫 327 个 ovk，找 id 超集
nums = set(want)
matches = []
for p in sorted(KOE.glob("*.ovk")):
    raw = p.read_bytes()
    count, = struct.unpack_from("<I", raw, 0)
    ids = {struct.unpack_from("<IIII", raw, 4 + i * 16)[2] for i in range(count)}
    cover = len(nums & ids)
    if cover >= len(nums) * 0.9:
        matches.append((p.name, count, cover))
        print(f"MATCH? {p.name}: entries={count} covers {cover}/{len(nums)}")
if not matches:
    print("no superset match — id 与语音号非同一编号体系")
