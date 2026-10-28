"""探针3：全部 摩耶_XXXX 引用点分类（索引表 vs 脚本引用）"""
import re

P = r"F:\初恋1-1\初恋1比1\scene.chs"
data = open(P, "rb").read()

# UTF-16LE 文本下匹配 摩耶_\d{4}：构造字节级正则（字符间插 \x00）
def u16re(s: str) -> bytes:
    return b"".join(c.encode("utf-16-le") for c in s)

pat = re.compile(u16re("摩耶_") + b"([0-9]\x00.{3})", re.S)
names = {}
for m in pat.finditer(data):
    off = m.start()
    num = m.group(1).decode("utf-16-le", errors="replace")
    names.setdefault(num, []).append(off)

print("distinct voice ids:", len(names))
for num, offs in sorted(names.items()):
    print(num, "refs@", offs)
