"""探针10：定位正文台词区 + 语音标记格式"""
import re
from collections import Counter

P = r"F:\初恋1-1\初恋1比1\scene.chs"
data = open(P, "rb").read()
N = len(data)

# 「 in utf-16le = b'\x53\x30'
q = b"\x53\x30"
idx = data.find(q)
first_text = idx
cnt = data.count(q)
print(f"「count={cnt} first@{first_text}")

# 每 500KB 统计「密度，找出正文分布
marks = []
pos = 0
while True:
    i = data.find(q, pos)
    if i < 0:
        break
    marks.append(i)
    pos = i + 2
import bisect
buckets = Counter((m // 500_000) * 500 for m in marks)
print("density (MB bucket: count):")
for k in sorted(buckets):
    if buckets[k] > 20:
        print(f"  {k}MB: {buckets[k]}")
