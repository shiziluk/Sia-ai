"""e3 权重监听 + 自动对比合成 (e2 版修复: openapi 探活 + GET 切权重)
轮询 maya_e3.pth → 停训练 → 重启 api_v2 → 切 e3 权重 → 合成 3 条关键对比
→ _audition/finetuned_e3/ 。幂等, 已有 mp3 跳过。
"""
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
PKG = ROOT / "GPT-SoVITS-v2pro-20261006"
PY = PKG / "runtime" / "python.exe"
WEIGHT = PKG / "SoVITS_weights_v2ProPlus" / "maya_e3.pth"
OUT = ROOT / "_audition" / "finetuned_e3"
API = "http://127.0.0.1:9880/tts"

REF_ZH = {
    # c1: 重做的 B2 ref — 旧ref(xiaoyi_b) 能量中后段塌陷(46/53), GPT 复刻包络导致每句后半发软; c1 全程 69-87 平稳
    "B2_akuma": (ROOT / "_audition/ref_zh/xiaoyi_c1.mp3", "喂，别装傻了！我都看见了，就是你干的吧？"),
    "B1_wenrou": (ROOT / "_audition/ref_zh/xiaoxiao_a.wav", "哎呀，被你发现了。其实这些话，我一直都想找机会告诉你。"),
}
TEXTS = {
    "akuma": "才不是担心你呢，只是你不在的话，会有人偷偷哭鼻子的。",
    "wenrou": "今天也辛苦了，回来得正好，我刚把汤热好。",
}
JOBS = [  # (ref_key, text_key)
    ("B2_akuma", "akuma"),   # 主对比: e2 里语气最好的那条
    ("B2_akuma", "wenrou"),
    ("B1_wenrou", "wenrou"),
]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def synth(ref_path, prompt_text, text, dst):
    body = {
        "text": text, "text_lang": "zh",
        "ref_audio_path": str(ref_path).replace("\\", "/"),
        "prompt_text": prompt_text, "prompt_lang": "zh",
        "text_split_method": "cut5",
    }
    req = urllib.request.Request(API, json.dumps(body).encode(), {"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            wav = urllib.request.urlopen(req, timeout=300).read()
            dst.parent.mkdir(parents=True, exist_ok=True)
            mp3 = dst.with_suffix(".mp3")
            p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "pipe:0", "-b:a", "128k", str(mp3)],
                               input=wav, capture_output=True)
            if p.returncode == 0 and mp3.stat().st_size > 10000:
                log(f"OK {mp3.name} {mp3.stat().st_size//1024}KB")
                return True
            log(f"ffmpeg fail {mp3.name}: {p.stderr[-200:]}")
        except Exception as e:
            log(f"attempt{attempt} {dst.stem}: {e}")
            time.sleep(5)
    return False


def api_ready():
    try:
        urllib.request.urlopen("http://127.0.0.1:9880/openapi.json", timeout=3).read()
        return True
    except Exception:
        return False


def kill_port(pid_port):
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    pids = set()
    for line in out.splitlines():
        if f":{pid_port}" in line and "LISTENING" in line.upper():
            parts = line.split()
            if parts and parts[-1].isdigit() and int(parts[-1]) != os.getpid():
                pids.add(int(parts[-1]))
    for pid in pids:
        subprocess.run(["taskkill", "/f", "/pid", str(pid), "/t"], capture_output=True)
    return pids


def start_api():
    subprocess.Popen(
        f'"{PY}" api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml',
        cwd=PKG, shell=True,
        stdout=open(ROOT / "_training" / "apiv2_log.txt", "w", encoding="utf-8"),
        stderr=subprocess.STDOUT)
    for _ in range(120):
        if api_ready():
            log("api_v2 就绪")
            return
        time.sleep(5)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log("等待 maya_e3.pth ...")
    while not WEIGHT.exists():
        time.sleep(60)
    log("e3 权重已出, 停训练释放显存")
    subprocess.run(["schtasks", "/end", "/tn", "maya_train"], capture_output=True)
    time.sleep(10)
    if kill_port(9880):
        time.sleep(5)
    start_api()

    switch = urllib.request.quote(str(WEIGHT).replace("\\", "/"), safe="")
    req = urllib.request.Request(f"http://127.0.0.1:9880/set_sovits_weights?weights_path={switch}")
    resp = urllib.request.urlopen(req, timeout=600).read()
    log(f"set_sovits_weights: {resp[:80]}")

    ok = fail = 0
    for ref_key, t_key in JOBS:
        ref_path, prompt = REF_ZH[ref_key]
        dst = OUT / f"{ref_key}_{t_key}.mp3"
        if dst.exists():
            ok += 1
            continue
        if synth(ref_path, prompt, TEXTS[t_key], dst):
            ok += 1
        else:
            fail += 1
    log(f"完成: {ok} 成功 / {fail} 失败 → {OUT}")


if __name__ == "__main__":
    main()
