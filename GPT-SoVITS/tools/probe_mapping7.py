"""探测7：SiglusEngine 惯例——正文每字节 +N 偏移加密。做 -4~+4 全偏移搜索。

命中目标：z0001/z0003（语音包引用）、摩耶（台词角色名）、g00（场景名）
"""
from pathlib import Path

G = Path(r"F:\初恋1-1\初恋1比1")
raw = (G / "scene.chs").read_bytes()
print(f"文件大小 {len(raw)}")

targets = {}
for name in ["z0003", "z0001", "z4001", "g00", "摩耶", "雪乃"]:
    targets[name] = name.encode("utf-16-le")

for shift in range(-4, 5):
    shifted = bytes((x + shift) & 0xFF for x in raw)
    hits = {n: shifted.count(e) for n, e in targets.items()}
    tot = sum(hits.values())
    if tot:
        print(f"shift={shift:+d}: {hits}")
