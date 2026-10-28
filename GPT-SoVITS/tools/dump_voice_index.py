"""导出 scene.chs 头部的语音名索引表：`<字母><2位序号><角色>_<4位台词号>`

验证字母↔ovk 对应关系（字母 g = 摩耶？→ z0007.ovk？）
"""
import re

P = r"F:\初恋1-1\初恋1比1\scene.chs"
data = open(P, "rb").read()

# UTF-16LE 下匹配 字母(可能多字符)+两位数字+角色名_四位数字
# 名称区在文件头部约 26000~40000 字节处，全扫也很快
def u16(s):
    return s.encode("utf-16-le")

# 逐位置扫描太慢，改为解码头部区域再正则
head = data[:60000].decode("utf-16-le", errors="ignore")
pat = re.compile(r"([a-z]{1,2})(\d{2})([\u4e00-\u9fffA-Za-z]+)_(\d{4}|エンディング)")
groups = {}
for m in pat.finditer(head):
    letter, seq, name, num = m.groups()
    groups.setdefault(letter, []).append((int(seq), name, num))

for letter, items in sorted(groups.items()):
    names = {}
    for _, name, num in items:
        names.setdefault(name, []).append(num)
    desc = ", ".join(f"{k}×{len(v)}" for k, v in names.items())
    print(f"{letter}: total={len(items)}  [{desc}]")
