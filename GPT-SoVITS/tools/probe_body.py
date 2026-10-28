"""探针8：scene.chs 正文结构——名称表之后的区域"""
P = r"F:\初恋1-1\初恋1比1\scene.chs"
data = open(P, "rb").read()

# 名称表约在 26154~26984。看 26984 之后 3KB 的原始 utf-16 内容
seg = data[26960:30200]
txt = seg.decode("utf-16-le", errors="replace")
pretty = "".join(c if c.isprintable() or c in "\r\n\t" else f"‧{ord(c):04x}‧" for c in txt)
print(pretty[:4000])
