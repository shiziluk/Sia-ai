"""探针11：Scene.pck 头部与 TOC"""
import binascii

P = r"F:\初恋1-1\初恋1比1\Scene.pck"
data = open(P, "rb").read()
print("size", len(data))
print("head:", binascii.hexlify(data[:96]).decode())
print("ascii:", repr(data[:96]))

# 找可见文件名串（ascii 字母数字下划线）
import re
for m in list(re.finditer(rb"[0-9A-Za-z_]{4,24}", data[:20000]))[:30]:
    print(m.start(), m.group())
