"""三方声学对比: 合成 vs 摩耶原声 vs 中文 ref
输出: F0 统计 / MFCC 余弦相似度矩阵 / RMS 首尾比(门禁2)
用整合包 runtime python 运行(自带 librosa)
"""
import sys
import numpy as np
import librosa

FILES = {
    "B2合成(akuma/e3)":   r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\finetuned_e3\B2_akuma_akuma.mp3",
    "sel_e20合成(wenrou)": r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\full_vs_sel\sel_e20_wenrou.mp3",
    "摩耶原声1":           r"F:\self_project\Sia-ai\GPT-SoVITS\_training\wav\z0003_0819.wav",
    "摩耶原声2":           r"F:\self_project\Sia-ai\GPT-SoVITS\_training\wav\z0003_0835.wav",
    "摩耶原声3":           r"F:\self_project\Sia-ai\GPT-SoVITS\_training\wav\z0003_0842.wav",
    "中文ref_c1(akuma)":  r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\ref_zh\xiaoyi_c1.mp3",
    "中文ref_a(wenrou)":  r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\ref_zh\xiaoxiao_a.wav",
}


def features(path):
    y, sr = librosa.load(path, sr=None, mono=True)
    y, _ = librosa.effects.trim(y, top_db=30)
    dur = len(y) / sr
    f0, _, _ = librosa.pyin(y, fmin=80, fmax=400, sr=sr, frame_length=1024)
    f0v = f0[~np.isnan(f0)]
    mf = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=20).mean(axis=1)
    rms = librosa.feature.rms(y=y).flatten()
    q = max(1, len(rms) // 4)
    tail_head = float(rms[-q:].mean() / max(rms[:q].mean(), 1e-9))
    return {
        "dur": dur, "f0_med": np.median(f0v), "f0_p10": np.percentile(f0v, 10),
        "f0_p90": np.percentile(f0v, 90), "mfcc": mf, "tail_head": tail_head,
    }


def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


feats = {}
for name, path in FILES.items():
    try:
        feats[name] = features(path)
        f = feats[name]
        print(f"{name}: dur={f['dur']:.1f}s F0中位={f['f0_med']:.0f}Hz "
              f"10-90分位=[{f['f0_p10']:.0f},{f['f0_p90']:.0f}] "
              f"RMS尾/首={f['tail_head']:.2f}")
    except Exception as e:
        print(f"{name}: FAIL {e}")

print("\n=== MFCC 余弦相似度 (音色接近度, 越高越像) ===")
names = list(feats)
sims = [(cos(feats[a]["mfcc"], feats[b]["mfcc"]), a, b)
        for i, a in enumerate(names) for b in names[i+1:]]
sims.sort(reverse=True)
for s, a, b in sims:
    print(f"{s:.3f}  {a}  <->  {b}")

# 摩耶原声平均 MFCC 作为"摩耶音色中心"
maya_names = [n for n in names if n.startswith("摩耶")]
maya_center = np.mean([feats[n]["mfcc"] for n in maya_names], axis=0)
print("\n=== 到摩耶音色中心的距离 ===")
for n in names:
    if not n.startswith("摩耶"):
        print(f"{cos(feats[n]['mfcc'], maya_center):.3f}  {n}")
