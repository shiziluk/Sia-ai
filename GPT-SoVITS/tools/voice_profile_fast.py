"""向量化声学画像器：输出与 voice_profile.py 相同指标，速度 ~20x

原理：所有帧堆成 2D 矩阵 → rfft 批量算质心；自相关经 FFT 批量算 F0
"""
import subprocess
from pathlib import Path

import numpy as np

SR = 16000
FRAME = int(0.040 * SR)
HOP = int(0.010 * SR)
F0_LO, F0_HI = 70, 400
MIN_F0_ENERGY = 0.35


def load_pcm(path: Path) -> np.ndarray:
    # 优先 soundfile（无子进程，快 ~20x），失败回退 ffmpeg
    try:
        import soundfile as sf
        data, sr = sf.read(str(path), dtype="float32", always_2d=False)
        if data.ndim > 1:
            data = data.mean(axis=1)
        if sr != SR:
            n_out = int(len(data) * SR / sr)
            data = np.interp(np.linspace(0, len(data) - 1, n_out),
                             np.arange(len(data)), data).astype(np.float32)
        return data
    except Exception:
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le",
             "-ac", "1", "-ar", str(SR), "-"],
            capture_output=True, check=True).stdout
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def analyze(path) -> dict:
    x = load_pcm(Path(path))
    n = max((len(x) - FRAME) // HOP, 0)
    idx = np.arange(n)[:, None] * HOP + np.arange(FRAME)[None, :]
    frames = x[idx] * np.hanning(FRAME).astype(np.float32)

    # 质心（批量 FFT）
    spec = np.abs(np.fft.rfft(frames, axis=1))
    freqs = np.fft.rfftfreq(FRAME, 1 / SR)
    tot = spec.sum(axis=1)
    cents = (spec * freqs).sum(axis=1) / np.maximum(tot, 1e-9)

    # F0（自相关经 FFT，批量）
    NFFT = 1 << (2 * FRAME - 1).bit_length()
    F = np.fft.rfft(frames, NFFT, axis=1)
    ac = np.fft.irfft(F * np.conj(F), NFFT, axis=1)[:, :FRAME]
    ac /= np.maximum(ac[:, 0:1], 1e-9)
    lo, hi = SR // F0_HI, SR // F0_LO
    seg = ac[:, lo:hi]
    k = seg.argmax(axis=1)
    peak = seg[np.arange(len(seg)), k]
    f0 = SR / (lo + k)
    voiced = f0[(peak >= MIN_F0_ENERGY) & (tot > 0.05)]

    return {
        "dur": round(len(x) / SR, 2),
        "f0_med": round(float(np.median(voiced)), 1) if len(voiced) else 0,
        "f0_p10": round(float(np.percentile(voiced, 10)), 1) if len(voiced) else 0,
        "f0_p90": round(float(np.percentile(voiced, 90)), 1) if len(voiced) else 0,
        "centroid_med": round(float(np.median(cents)), 0) if len(cents) else 0,
        "voicing": round(len(voiced) / max(n, 1), 2),
    }


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        print(Path(p).name, analyze(Path(p)))
