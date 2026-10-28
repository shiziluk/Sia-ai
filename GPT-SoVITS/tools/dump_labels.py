"""探针9：完整场景标签表（含 ASCII 标签），输出 表位号↔标签"""
import re

P = r"F:\初恋1-1\初恋1比1\scene.chs"
data = open(P, "rb").read()
head = data[:60000].decode("utf-16-le", errors="ignore")

# 标签格式：<字母><2位数字>_<名称>（名称可含 CJK/ASCII/カタカナ，直到下一个标签或非打印区）
pat = re.compile(r"([a-z])(\d{2})_?([^\x00-\x1f‧]{1,40}?)(?=[a-z]\d{2}_|‧|\s*$)")
labels = []
for m in pat.finditer(head):
    labels.append((m.start(), m.group(1), int(m.group(2)), m.group(3)))

print("total labels:", len(labels))
for i, (off, letter, seq, name) in enumerate(labels, 1):
    mark = " ←摩耶" if "摩耶" in name else ""
    if i <= 12 or mark or i > len(labels) - 8:
        print(f"#{i:03d} z{i:04d}  {letter}{seq:02d} {name!r}{mark}  @{off}")
