"""探测：游戏文件中是否存在 语音包(z编号) ↔ 角色 的官方映射

线索：
  1. gameexe.chs（10KB 明文汉化版？）——SiglusEngine 配置，可能有 #VOICE_/#NAME_ 映射
  2. scene.chs（13.9MB 场景脚本）——搜 z 编号引用 + 角色名 + 头部标签表
"""
import re
from pathlib import Path

G = Path(r"F:\初恋1-1\初恋1比1")


def hexdump(b, n=128):
    for i in range(0, min(n, len(b)), 16):
        chunk = b[i:i + 16]
        hexs = " ".join(f"{c:02x}" for c in chunk)
        txt = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        print(f"{i:06x}  {hexs:<48}  {txt}")


# 1. 配置三件套头部
for name in ["gameexe.chs", "Gameexe.dat", "Gameexe.ini"]:
    p = G / name
    b = p.read_bytes()
    print(f"\n===== {name} ({len(b)} B) =====")
    hexdump(b, 96)

# 2. scene.chs 搜 z0003（ASCII 与 UTF-16LE）
b = (G / "scene.chs").read_bytes()
for enc, label in [(b"z0003", "ascii"), ("z0003".encode("utf-16-le"), "utf16le")]:
    positions, start = [], 0
    while True:
        i = b.find(enc, start)
        if i < 0 or len(positions) >= 8:
            break
        positions.append(i)
        start = i + 1
    print(f"\nscene.chs 中 'z0003' [{label}]: {len(positions)} 处 {positions[:8]}")

# 3. scene.chs 搜角色名（UTF-16LE 与 GBK）
for enc, label in [("摩耶".encode("utf-16-le"), "utf16le"), ("摩耶".encode("gbk"), "gbk")]:
    cnt, first, start = 0, -1, 0
    while True:
        i = b.find(enc, start)
        if i < 0:
            break
        cnt += 1
        if first < 0:
            first = i
        start = i + 1
    print(f"scene.chs 中 '摩耶' [{label}]: {cnt} 处, first={hex(first) if first >= 0 else '-'}")

# 4. scene.chs 头部 UTF-16LE 可读串（标签表样例）
s = b[:0x8000].decode("utf-16-le", errors="ignore")
runs = re.findall(r"[\u4e00-\u9fffA-Za-z0-9_=\-]{6,}", s)
print(f"\nscene.chs 头部 UTF-16LE 可读串（共 {len(runs)}，前 40 条）:")
for r in runs[:40]:
    print("  ", r)
