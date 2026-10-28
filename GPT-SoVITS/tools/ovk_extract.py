"""OVK 解包器（SiglusEngine 语音容器 → ogg）

TOC 结构（自研逆向，链式校验通过）：
  u32 count
  count × 16B 记录: [u32 size, u32 start, u32 id, u32 d]
  payload 为明文 Ogg；start_i + size_i == start_{i+1}
用法: python ovk_extract.py <ovk文件或koe目录> <输出目录>
"""
import struct
import sys
from pathlib import Path


def parse_ovk(path: Path):
    data = path.read_bytes()
    count, = struct.unpack_from("<I", data, 0)
    entries = []
    ok = 0
    for i in range(count):
        size, start, rid, d = struct.unpack_from("<IIII", data, 4 + i * 16)
        if size <= 0 or start < 0 or start + size > len(data):
            entries.append(None)
            continue
        payload = data[start:start + size]
        valid = payload[:4] == b"OggS"
        ok += valid
        entries.append({"id": rid, "start": start, "size": size, "d": d, "valid": valid, "data": payload})
    return entries, ok, count


def main():
    src, outdir = Path(sys.argv[1]), Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    files = [src] if src.is_file() else sorted(src.glob("*.ovk"))
    if src.is_file():
        entries, ok, count = parse_ovk(src)
        stem = src.stem
        good = 0
        for e in entries:
            if e and e["valid"]:
                (outdir / f"{stem}_{e['id']:04d}.ogg").write_bytes(e["data"])
                good += 1
        print(f"{stem}: entries={count} ogg_ok={ok} dumped={good}")
        return
    total = good = 0
    for f in files:
        entries, ok, count = parse_ovk(f)
        total += count
        g = 0
        for e in entries:
            if e and e["valid"]:
                (outdir / f"{f.stem}_{e['id']:04d}.ogg").write_bytes(e["data"])
                g += 1
        good += g
        print(f"{f.stem}: {count} entries, ogg {ok}, dumped {g}")
    print(f"TOTAL: {len(files)} files, {total} entries, {good} dumped")


if __name__ == "__main__":
    main()
