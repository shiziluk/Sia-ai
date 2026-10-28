"""探针：scene.chs 的编码与'摩耶'分布（临时工具，不入 Git）"""
import binascii

P = r"F:\初恋1-1\初恋1比1\scene.chs"
data = open(P, "rb").read()
print("size", len(data))
print("head hex:", binascii.hexlify(data[:64]).decode())

for enc in ("utf-16-le", "utf-8", "gbk", "shift_jis"):
    try:
        needle = "摩耶".encode(enc)
    except Exception as e:
        print(enc, "encode fail", e)
        continue
    cnt = data.count(needle)
    idx = data.find(needle)
    print(enc, "first@", idx, "count", cnt)
    if 0 < cnt <= 30 and idx > 0:
        s = max(0, idx - 120)
        print("  ctx:", data[s:idx + 120])
