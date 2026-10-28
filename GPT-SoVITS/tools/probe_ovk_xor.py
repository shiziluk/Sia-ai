"""探针5：.ovk 内 OggS XOR 混淆检测"""
from collections import Counter

P = r"F:\初恋1-1\初恋1比1\koe\z0001.ovk"
data = open(P, "rb").read()

c = Counter()
for i in range(0, len(data) - 4):
    c[data[i:i + 4]] += 1

print("top 8 4-byte sequences:")
for seq, n in c.most_common(8):
    k = bytes(a ^ b for a, b in zip(seq, b"OggS"))
    print(f"  {seq.hex()}  count={n}  xor_key_if_OggS={k.hex()}  {k!r}")
