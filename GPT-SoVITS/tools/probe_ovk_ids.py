"""探针7：id 分区假设验证——z0001~z0010 的 id 范围"""
import struct
from pathlib import Path

koe = Path(r"F:\初恋1-1\初恋1比1\koe")
for n in range(1, 11):
    p = koe / f"z{n:04d}.ovk"
    data = p.read_bytes()
    count, = struct.unpack_from("<I", data, 0)
    ids = [struct.unpack_from("<IIII", data, 4 + i * 16)[2] for i in range(count)]
    ok = sum(1 for i in range(count)
             if data[struct.unpack_from("<IIII", data, 4 + i * 16)[1]:
                    struct.unpack_from("<IIII", data, 4 + i * 16)[1] + 4] == b"OggS")
    print(f"z{n:04d}: count={count} ids={min(ids)}..{max(ids)} ogg_ok={ok}/{count}")
