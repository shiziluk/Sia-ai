"""生成摩耶微调训练清单 + ogg→wav(32k) 转换
.list 格式: wav路径|说话人|语言|文本
用法: python gen_train_list.py
"""
import csv
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "_official_map.csv"
VOICES = ROOT / "_voices"
OUT = ROOT / "_training"
WAVDIR = OUT / "wav"


def clean(text: str) -> str:
    return text.replace("|", "，").replace("\n", " ").strip()


def main():
    WAVDIR.mkdir(parents=True, exist_ok=True)
    with MAP.open(encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.reader(fh) if len(r) >= 3 and r[1] == "摩耶"]

    lines, ok = [], 0
    for i, r in enumerate(rows):
        src = VOICES / r[0]
        dst = WAVDIR / (Path(r[0]).stem + ".wav")
        if not dst.exists():
            p = subprocess.run(
                ["ffmpeg", "-v", "error", "-y", "-i", str(src),
                 "-ar", "32000", "-ac", "1", "-c:a", "pcm_s16le", str(dst)],
                capture_output=True)
            if p.returncode != 0 or not dst.exists():
                continue
        ok += 1
        lines.append(f"{dst.as_posix()}|摩耶|ja|{clean(r[2])}")
        if (i + 1) % 500 == 0:
            print(f"... {i + 1}/{len(rows)}")

    (OUT / "maya.list").write_text("\n".join(lines), encoding="utf-8")
    print(f"完成: {ok}/{len(rows)} 条 → {OUT / 'maya.list'}")


if __name__ == "__main__":
    main()
