"""e2 权重监听 + 自动试听矩阵合成
轮询 maya_e2.pth → 停训练 → 起 api_v2 → 合成 A(日文ref)/B(中文ref) 对比矩阵 → 退出
音频输出 _audition/finetuned/，文件名自解释。
用整合包 runtime python 跑。
"""
import csv
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
WEIGHT = PKG / "SoVITS_weights_v2ProPlus" / "maya_e2.pth"
OUT = ROOT / "_audition" / "finetuned"
API = "http://127.0.0.1:9880/tts"

REF_JA = {  # 日文 ref: wav路径(训练集32k) + 官方台词
    "A1_wenrou": (ROOT / "_training/wav/z6005_0655.wav", "疲れたら、祐馬のだらしない顔を見て、ほっと一息つけるし"),
    "A2_akuma": (ROOT / "_training/wav/z3007_0275.wav", "あんたをからかうためだけに残るわけないでしょ？"),
}
REF_ZH = {  # 中文 ref: edge-tts 生成, prompt_text=同句
    "B1_wenrou": (ROOT / "_audition/ref_zh/xiaoxiao_a.wav", "哎呀，被你发现了。其实这些话，我一直都想找机会告诉你。"),
    "B2_akuma": (ROOT / "_audition/ref_zh/xiaoyi_b.wav", "喂，别装傻了。该不会，是想让我一直等你吧？"),
}
TEXTS = {
    "wenrou": "今天也辛苦了，回来得正好，我刚把汤热好。",
    "akuma": "才不是担心你呢，只是你不在的话，会有人偷偷哭鼻子的。",
    "richang": "那本书我看了两遍了，结尾那段写得特别好。",
}


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def synth(ref_path, prompt_text, prompt_lang, text, dst):
    body = {
        "text": text, "text_lang": "zh",
        "ref_audio_path": str(ref_path).replace("\\", "/"),
        "prompt_text": prompt_text, "prompt_lang": prompt_lang,
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
    """打只读端点 /openapi.json 探活, 避免误触 /tts(服务端会当真合成处理)"""
    try:
        urllib.request.urlopen("http://127.0.0.1:9880/openapi.json", timeout=3).read()
        return True
    except Exception:
        return False


def kill_port(pid_port):
    """按监听端口精确杀进程, 不碰自己"""
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
    log("等待 maya_e2.pth ...")
    while not WEIGHT.exists():
        time.sleep(60)
    log("e2 权重已出, 停训练释放显存")
    subprocess.run(["schtasks", "/end", "/tn", "maya_train"], capture_output=True)
    time.sleep(10)
    if kill_port(9880):
        time.sleep(5)

    if not api_ready():
        log("启动 api_v2 (底模态起, 后面切权重)")
        start_api()
    else:
        log("api_v2 已在运行")


    # 切微调权重(此版 api_v2 该端点为 GET + query 参数)
    switch = urllib.request.quote(str(WEIGHT).replace("\\", "/"), safe="")
    req = urllib.request.Request(f"http://127.0.0.1:9880/set_sovits_weights?weights_path={switch}")
    resp = urllib.request.urlopen(req, timeout=600).read()
    log(f"set_sovits_weights: {resp[:80]}")

    # 合成矩阵
    ok = fail = 0
    for ref_key, (ref_path, prompt) in {**REF_JA, **REF_ZH}.items():
        lang = "ja" if ref_key.startswith("A") else "zh"
        for t_key, text in TEXTS.items():
            dst = OUT / f"{ref_key}_{t_key}.mp3"
            if dst.exists():
                ok += 1
                continue
            if synth(ref_path, prompt, lang, text, dst):
                ok += 1
            else:
                fail += 1
    log(f"完成: {ok} 成功 / {fail} 失败 → {OUT}")


if __name__ == "__main__":
    main()
