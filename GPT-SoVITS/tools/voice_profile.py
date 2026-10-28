"""声学画像器：ogg/mp3 → 数值特征（F0/明暗度/语速代理），零第三方重依赖

用法: python voice_profile.py <音频文件或目录> [--csv out.csv]
特征:
  f0_med / f0_p10 / f0_p90   基频中位/低分位/高分位 (Hz) —— 音高与音域
  centroid_med               频谱质心中位 (Hz)          —— 音色明暗
  voicing                    有效浊音帧占比
  dur                        时长 (s)
"""
import csv
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 16000
FRAME = int(0.040 * SR)   # 40ms
HOP = int(0.010 * SR)     # 10ms
F0_LO, F0_HI = 70, 400    # 人类语音基频合理范围


def load_pcm(path: Path) -> np.ndarray:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le",
         "-ac", "1", "-ar", str(SR), "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def f0_autocorr(frame: np.ndarray):
    frame = frame - frame.mean()
    e = (frame * frame).sum()
    if e < 1e-6:
        return 0.0
    ac = np.correlate(frame, frame, "full")[FRAME - 1:]
    ac /= e
    lo, hi = SR // F0_HI, SR // F0_LO
    if hi >= len(ac):
        return 0.0
    seg = ac[lo:hi]
    k = int(seg.argmax())
    if seg[k] < 0.35:          # 浊音置信阈值
        return 0.0
    return SR / (lo + k)


def analyze(path: Path) -> dict:
    x = load_pcm(path)
    n = (len(x) - FRAME) // HOP
    f0s, cents = [], []
    win = np.hanning(FRAME).astype(np.float32)
    for i in range(max(n, 0)):
        fr = x[i * HOP:i * HOP + FRAME] * win
        f = f0_autocorr(fr)
        if f > 0:
            f0s.append(f)
        spec = np.abs(np.fft.rfft(fr))
        freqs = np.fft.rfftfreq(FRAME, 1 / SR)
        m = spec.sum()
        if m > 1e-6:
            cents.append((freqs * spec).sum() / m)
    f0 = np.array(f0s)
    voiced = len(f0) / max(n, 1)
    return {
        "file": path.name,
        "dur": round(len(x) / SR, 2),
        "f0_med": round(float(np.median(f0)), 1) if len(f0) else 0,
        "f0_p10": round(float(np.percentile(f0, 10)), 1) if len(f0) else 0,
        "f0_p90": round(float(np.percentile(f0, 90)), 1) if len(f0) else 0,
        "centroid_med": round(float(np.median(cents)), 0) if cents else 0,
        "voicing": round(voiced, 2),
    }


def main():
    src = Path(sys.argv[1])
    files = [src] if src.is_file() else sorted(
        p for p in src.rglob("*") if p.suffix.lower() in (".ogg", ".mp3", ".wav"))
    rows = []
    for p in files:
        try:
            r = analyze(p)
            rows.append(r)
            print(r)
        except Exception as e:
            print(p.name, "FAIL", e)
    if "--csv" in sys.argv:
        out = Path(sys.argv[sys.argv.index("--csv") + 1])
        with open(out, "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print("csv ->", out)


if __name__ == "__main__":
    main()
