"""探针6：TOC 记录 vs 实际 OggS 页位置对齐"""
import struct

P = r"F:\初恋1-1\初恋1比1\koe\z0001.ovk"
data = open(P, "rb").read()

pages = []
i = data.find(b"OggS")
while i >= 0:
    pages.append(i)
    i = data.find(b"OggS", i + 1)
print("ogg pages:", len(pages), "first 12:", pages[:12])
print("file size:", len(data))

count, = struct.unpack_from("<I", data, 0)
print("toc count:", count, "toc bytes:", 4 + count * 16, hex(4 + count * 16))
recs = [struct.unpack_from("<IIII", data, 4 + i * 16) for i in range(min(count, 15))]
for r in recs:
    print(f"a={r[0]:#x} b={r[1]:#x} id={r[2]:#x} d={r[3]:#x}")
