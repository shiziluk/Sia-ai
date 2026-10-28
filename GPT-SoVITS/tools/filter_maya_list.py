"""从 maya.list 精选训练子集：时长过滤(1.5~12s) + 按场景均匀采样 → maya_train.list

背景: 1050Ti 实测 11.5s/step, 全量 7453 条一个 epoch 要 11 小时。
     精选 ~1500 条(约55分钟素材)已等效社区典型微调量, 3 epoch 一夜跑完。
"""
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_training" / "maya.list"
DST = ROOT / "_training" / "maya_train.list"
WAVDIR = ROOT / "_training" / "wav"

MIN_DUR, MAX_DUR, TARGET = 1.5, 12.0, 1500


def main():
    lines = [l for l in SRC.read_text(encoding="utf-8").splitlines() if l.strip()]
    kept = []
    for line in lines:
        wav = Path(line.split("|")[0])
        try:
            with wave.open(str(wav), "rb") as w:
                dur = w.getnframes() / w.getframerate()
        except Exception:
            continue
        if MIN_DUR <= dur <= MAX_DUR:
            kept.append((dur, line))
    total = sum(d for d, _ in kept)
    print(f"时长过滤: {len(kept)}/{len(lines)} 条, 合计 {total/60:.0f} 分钟")

    # 按文件名排序(场景连续分布)后 stride 均匀采样, 保证覆盖所有场景/情绪
    kept.sort(key=lambda x: x[1])
    if len(kept) > TARGET:
        stride = len(kept) / TARGET
        kept = [kept[int(i * stride)] for i in range(TARGET)]
    DST.write_text("\n".join(l for _, l in kept) + "\n", encoding="utf-8")
    print(f"采样后: {len(kept)} 条, 合计 {sum(d for d, _ in kept)/60:.0f} 分钟 → {DST}")


if __name__ == "__main__":
    main()
