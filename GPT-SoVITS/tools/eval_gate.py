"""三道门禁评测: CER / 能量曲线 / 说话人embedding (+F0 附赠)
用法:
  合成(需 GPU 空闲, api_v2 运行中):
    python eval_gate.py synth --tag full_e12 --gpt GPT_weights_v2ProPlus/maya_full-e12.ckpt
    python eval_gate.py synth --tag sel_e20  --gpt GPT_weights_v2ProPlus/maya-e20.ckpt
  打分(CPU, 不占显存, 可多 tag 对比):
    python eval_gate.py score --tags full_e8 full_e12 sel_e20
输出: _audition/gate/report_<时间戳>.json + 控制台对比表
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import librosa
import numpy as np

ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
PKG = ROOT / "GPT-SoVITS-v2pro-20261006"
PY = PKG / "runtime" / "python.exe"
GATE = ROOT / "_audition" / "gate"
SENT = GATE / "sentences.json"
API = "http://127.0.0.1:9880"
MAYA_LIST = ROOT / "_training" / "maya.list"
WAV_DIR = ROOT / "_training" / "wav"
CENTER_CACHE = GATE / "_maya_center.npy"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


# ---------- synth ----------

def synth_tag(tag, gpt_weight, refset="refs"):
    cfg = json.loads(SENT.read_text(encoding="utf-8"))
    refs_table = cfg.get(refset, cfg["refs"])
    prompt_lang = "ja" if refset == "refs_maya" else "zh"
    out_dir = GATE / tag
    out_dir.mkdir(parents=True, exist_ok=True)
    # 切 GPT 权重
    wp = urllib.request.quote(str(PKG / gpt_weight).replace("\\", "/"), safe="")
    try:
        resp = urllib.request.urlopen(f"{API}/set_gpt_weights?weights_path={wp}", timeout=600).read()
        log(f"set_gpt_weights: {resp[:60]}")
    except Exception as e:
        log(f"切权重失败(检查 api_v2 是否在跑): {e}")
        sys.exit(1)
    ok = 0
    for s in cfg["sentences"]:
        ref_path, prompt = refs_table[s["style"]]
        dst = out_dir / f"{s['id']}.mp3"
        if dst.exists() and dst.stat().st_size > 10000:
            ok += 1
            continue
        body = {
            "text": s["text"], "text_lang": "zh",
            "ref_audio_path": ref_path, "prompt_text": prompt, "prompt_lang": prompt_lang,
            "text_split_method": "cut5",
        }
        try:
            wav = urllib.request.urlopen(
                urllib.request.Request(f"{API}/tts", json.dumps(body).encode(),
                                       {"Content-Type": "application/json"}), timeout=300).read()
            p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "pipe:0", "-b:a", "128k", str(dst)],
                               input=wav, capture_output=True)
            if p.returncode == 0 and dst.stat().st_size > 10000:
                ok += 1
                log(f"OK {s['id']}")
            else:
                log(f"FAIL {s['id']}: {p.stderr[-120:]}")
        except Exception as e:
            log(f"FAIL {s['id']}: {e}")
    log(f"[{tag}] 合成完成 {ok}/20 -> {out_dir}")


# ---------- score helpers ----------

def norm_zh(t):
    return re.sub(r"[^\u4e00-\u9fff0-9a-zA-Z]", "", t)


def cer(ref, hyp):
    r, h = norm_zh(ref), norm_zh(hyp)
    if not r:
        return 1.0
    dp = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        prev = dp[0]
        dp[0] = i
        for j, hc in enumerate(h, 1):
            cur = dp[j]
            dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (rc != hc))
            prev = cur
    return dp[len(h)] / len(r)


def rms_tail_head(y):
    r = librosa.feature.rms(y=y).flatten()
    q = max(1, len(r) // 4)
    return float(r[-q:].mean() / max(r[:q].mean(), 1e-9))


def f0_median(y, sr):
    f0, _, _ = librosa.pyin(y, fmin=80, fmax=400, sr=sr, frame_length=1024)
    v = f0[~np.isnan(f0)]
    return float(np.median(v)) if len(v) else 0.0


_maya_center = None


def maya_center():
    """摩耶原声 embedding 中心(缓存): maya.list 中时长 2-10s 的前 10 条"""
    global _maya_center
    if _maya_center is not None:
        return _maya_center
    if CENTER_CACHE.exists():
        _maya_center = np.load(CENTER_CACHE)
        return _maya_center
    from GPT_SoVITS.sv import SV
    sv = SV("cpu", False)
    embs = []
    for line in MAYA_LIST.read_text(encoding="utf-8").splitlines()[:200]:
        p = Path(line.split("|")[0])
        if not p.exists():
            continue
        y, sr = librosa.load(str(p), sr=16000, mono=True)
        if not (2.0 <= len(y) / sr <= 10.0):
            continue
        t = torch_from(y)
        embs.append(sv.compute_embedding3(t).squeeze().float().cpu().numpy())
        if len(embs) >= 10:
            break
    _maya_center = np.mean(embs, axis=0)
    np.save(CENTER_CACHE, _maya_center)
    log(f"摩耶音色中心已缓存: {len(embs)} 条原声")
    return _maya_center


def torch_from(y16k):
    import torch
    return torch.from_numpy(y16k).float().unsqueeze(0)


def sv_embed(y16k):
    from GPT_SoVITS.sv import SV
    sv = SV("cpu", False)
    e = sv.compute_embedding3(torch_from(y16k)).squeeze().float().cpu().numpy()
    return e


def cos(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


# ---------- score ----------

def load_asr():
    """funasr ASR 强制 CPU(训练占卡时不能抢显存); ms/hf 双源 fallback"""
    from funasr import AutoModel
    common = dict(vad_model="fsmn-vad", device="cpu", disable_update=True)
    last = None
    for kw in (dict(model="FunAudioLLM/Fun-ASR-Nano-2512", hub="ms", trust_remote_code=False),
               dict(model="FunAudioLLM/Fun-ASR-Nano-2512", hub="hf", trust_remote_code=True)):
        try:
            return AutoModel(**kw, **common)
        except Exception as e:
            last = e
            log(f"ASR 源 {kw['hub']} 失败: {str(e)[:80]}")
    raise last


def score_tags(tags):
    cfg = json.loads(SENT.read_text(encoding="utf-8"))
    texts = {s["id"]: s["text"] for s in cfg["sentences"]}
    log("加载 funasr ASR (首次运行会下载模型, 强制 CPU)...")
    wm = load_asr()
    center = maya_center()
    report = {}
    for tag in tags:
        d = GATE / tag
        files = sorted(list(d.glob("*.mp3")) + list(d.glob("*.wav")))
        rows = []
        for f in files:
            sid = f.stem
            if sid not in texts:
                continue
            y, sr = librosa.load(str(f), sr=None, mono=True)
            dur = len(y) / sr
            th = rms_tail_head(y)
            y16 = librosa.resample(y, orig_sr=sr, target_sr=16000)
            emb = sv_embed(y16)
            sim = cos(emb, center)
            f0 = f0_median(y, sr)
            hyp = wm.generate(input=str(f))[0].get("text", "") or ""
            c = cer(texts[sid], hyp)
            rows.append({"id": sid, "dur": round(dur, 1), "cer": round(c, 3),
                         "tail_head": round(th, 2), "spk_sim": round(sim, 3),
                         "f0": round(f0), "hyp": hyp[:40]})
            log(f"{tag}/{sid}: CER={c:.2f} 尾首={th:.2f} spk={sim:.3f} F0={f0:.0f}")
        if rows:
            report[tag] = {
                "rows": rows,
                "avg": {k: round(float(np.mean([r[k] for r in rows])), 3)
                        for k in ("cer", "tail_head", "spk_sim", "f0")},
                "cer_gt_10pct": sum(1 for r in rows if r["cer"] > 0.10),
            }
    ts = time.strftime("%m%d_%H%M")
    out = GATE / f"report_{ts}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n=== 汇总 (report: {out.name}) ===")
    print(f"{'tag':<12} {'CER均值':<8} {'CER>10%':<8} {'尾/首':<7} {'音色sim':<8} {'F0':<5}")
    for tag, r in report.items():
        a = r["avg"]
        print(f"{tag:<12} {a['cer']:<8} {r['cer_gt_10pct']:<8} {a['tail_head']:<7} {a['spk_sim']:<8} {a['f0']:<5}")
    print("门禁阈值: CER<0.10 / 尾首>0.6 / spk_sim 本机校准中(先记录基线)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("synth")
    sp.add_argument("--tag", required=True)
    sp.add_argument("--gpt", required=True, help="相对包根的 GPT ckpt 路径")
    sp.add_argument("--refset", default="refs", choices=["refs", "refs_maya"],
                    help="refs=中文虚构音源, refs_maya=摩耶日文原声")
    sc = sub.add_parser("score")
    sc.add_argument("--tags", nargs="+", required=True)
    args = ap.parse_args()
    os.chdir(PKG)
    sys.path.insert(0, str(PKG))
    sys.path.append(str(PKG / "GPT_SoVITS" / "eres2net"))
    if args.cmd == "synth":
        synth_tag(args.tag, args.gpt, args.refset)
    else:
        score_tags(args.tags)
