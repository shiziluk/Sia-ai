"""探针4：.ovk 容器头部结构"""
import binascii

P = r"F:\初恋1-1\初恋1比1\koe\z0001.ovk"
data = open(P, "rb").read()
print("size", len(data))
print(binascii.hexlify(data[:128]).decode())
print("---- as text ----")
print(repr(data[:128]))
