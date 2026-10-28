"""探针2：摩耶出现的上下文结构（UTF-16LE 解码）"""
P = r"F:\初恋1-1\初恋1比1\scene.chs"
data = open(P, "rb").read()
needle = "摩耶".encode("utf-16-le")
pos, hits = 0, []
while True:
    i = data.find(needle, pos)
    if i < 0:
        break
    hits.append(i)
    pos = i + 2

for i, off in enumerate(hits[:6]):
    s = max(0, off - 300)
    raw = data[s:off + 300]
    # UTF-16LE 宽松解码，控制字符替换为·
    txt = raw.decode("utf-16-le", errors="replace")
    pretty = "".join(c if c.isprintable() else f"‧{ord(c):04x}‧" for c in txt)
    print(f"--- hit {i} @ {off} ---")
    print(pretty)
    print()
