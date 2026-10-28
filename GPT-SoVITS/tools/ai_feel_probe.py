"""AI感声学代理: F0微抖动(jitter代理) + 能量微动态 + F0曲率
真人(摩耶原声) vs edge-tts合成ref vs GPT输出 —— 定位AI感的来源
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
SR = 32000
FRAME = 1024  # 32ms
HOP = 320     # 10ms

REAL = [  # 摩耶真人原声(不同阶段)
    ROOT / "_voices/z6005_0655.ogg",
    ROOT / "_voices/z3007_0275.ogg",
    ROOT / "_voices/z6003_0499.ogg",
    ROOT / "_voices/z6006_0056.ogg",
]
SYNTH = [  # edge-tts 合成 ref
    ROOT / "_audition/ref_zh/xiaoyi_c1.mp3",
    ROOT / "_audition/ref_zh/xiaoyi_c4.mp3",
    ROOT / "_audition/ref_zh/xiaoxiao_a.wav",
]
OUT = [  # GPT 输出
    ROOT / "_audition/finetuned_gpt/E_wenrou_c4.mp3",
    ROOT / "_audition/finetuned_gpt/F_wenrou_basegpt.mp3",
    ROOT / "_audition/finetuned_gpt/E_akuma_fix.mp3",
    ROOT / "_audition/finetuned_gpt/F_akuma_basegpt.mp3",
]


def load(path):
    wav = Path(tempfile.gettempdir()) / "ai_t.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ar", str(SR), "-ac", "1", str(wav)], capture_output=True)
    return sf.read(wav, dtype="float32")[0]


def f0_track(x):
    """FFT自相关F0轨迹 (voice_profile_fast 同源)"""
    f0s, ts, rms = [], [], []
    for i in range(0, len(x) - FRAME, HOP):
        f = x[i:i + FRAME] * np.hanning(FRAME)
        e = np.sqrt(np.mean(x[i:i + FRAME] ** 2))
        rms.append(e)
        if e < 0.01:
            f0s.append(0); ts.append(i / SR); continue
        sp = np.abs(np.fft.rfft(f, 4096))
        sp[: int(60 / (SR / 4096)) + 1] = 0          # <60Hz 滤除
        sp[int(900 / (SR / 4096)):] = 0              # >900Hz 截断
        ac = np.fft.irfft(sp * sp)
        lo, hi = int(SR / 900), int(SR / 60)
        seg = ac[lo:hi]
        if len(seg) < 2 or seg.max() <= 0:
            f0s.append(0)
        else:
            f0s.append(SR / (lo + seg.argmax()))
        ts.append(i / SR)
    return np.array(f0s, float), np.array(rms, float)


def metrics(f0, rms):
    v = f0[f0 > 0]
    if len(v) < 10:
        return None
    d1 = np.diff(v)
    d2 = np.diff(v, 2)
    jitter = np.mean(np.abs(d2)) / np.mean(v)          # F0曲线不规律度
    flip = np.mean(np.abs(np.sign(d1[1:]) - np.sign(d1[:-1])) > 0)  # 方向翻转密度
    dr = rms[rms > 0.005]
    emicro = np.mean(np.abs(np.diff(dr))) / np.mean(dr)  # 能量微动态
    return jitter, flip, emicro, len(v)


def group(paths, label):
    js, fs, es = [], [], []
    for p in paths:
        f0, rms = f0_track(load(p))
        m = metrics(f0, rms)
        if m:
            js.append(m[0]); fs.append(m[1]); es.append(m[2])
    print(f"{label:12s} jitter={np.mean(js):.4f}  翻转密度={np.mean(fs):.3f}  能量微动态={np.mean(es):.4f}  (n={len(js)})")


if __name__ == "__main__":
    print("指标: jitter=F0二阶差分/均值(越高越不规律=越真人), 翻转密度=F0方向变化率, 能量微动态=RMS变化率")
    group(REAL, "真人(摩耶)")
    group(SYNTH, "edge-tts")
    group(OUT, "GPT输出")
