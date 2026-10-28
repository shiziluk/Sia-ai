"""GPT(e5/e10) 训练完成监听 + 三方对比合成
等 e10 权重出(=全训练结束) → 停训练 → 起 api(SoVITS=e3, GPT=底模) →
对照组合成 → 切 gpt_e5 → 合成 → 切 gpt_e10 → 合成 → _audition/finetuned_gpt/
ref 全部换摩耶原声(后日谈/g线, 女友态定律), prompt_lang=ja。
"""
import json
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
PKG = ROOT / "GPT-SoVITS-v2pro-20261006"
PY = PKG / "runtime" / "python.exe"
GPT_DIR = PKG / "GPT_weights_v2ProPlus"
SOVITS_E3 = PKG / "SoVITS_weights_v2ProPlus" / "maya_e3.pth"
OUT = ROOT / "_audition" / "finetuned_gpt"
API = "http://127.0.0.1:9880/tts"

# 摩耶原声 ref (阶段已核验: z6005=后日谈甜妹, z3007=g线情侣初期) + 官方日文台词
REFS = {
    "wenrou": (ROOT / "_voices" / "z6005_0655.ogg",
               "疲れたら、祐馬のだらしない顔を見て、ほっと一息つけるし"),
    "akuma": (ROOT / "_voices" / "z3007_0275.ogg",
              "あんたをからかうためだけに残るわけないでしょ？"),
}
TEXTS = {
    "wenrou": "今天也辛苦了，回来得正好，我刚把汤热好。",
    "akuma": "才不是担心你呢，只是你不在的话，会有人偷偷哭鼻子的。",
}
# 对照组 = GPT 底模(api 启动默认), 然后 e5, e10
ROUNDS = [("base", None), ("gptE5", "e5"), ("gptE10", "e10")]


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def api_ready():
    try:
        urllib.request.urlopen("http://127.0.0.1:9880/openapi.json", timeout=3).read()
        return True
    except Exception:
        return False


def kill_port(port):
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    for line in out.splitlines():
        if f":{port}" in line and "LISTENING" in line.upper():
            pid = line.split()[-1]
            if pid.isdigit():
                subprocess.run(["taskkill", "/f", "/pid", pid, "/t"], capture_output=True)


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
    raise RuntimeError("api 启动超时")


def set_weights(kind, path):
    from urllib.parse import quote
    q = quote(str(path).replace("\\", "/"), safe="")
    r = urllib.request.urlopen(
        f"http://127.0.0.1:9880/set_{kind}_weights?weights_path={q}", timeout=600).read()
    log(f"set_{kind}_weights: {r[:60]}")


def synth(tag, ref_key):
    ref_path, prompt = REFS[ref_key]
    body = {
        "text": TEXTS[ref_key], "text_lang": "zh",
        "ref_audio_path": str(ref_path).replace("\\", "/"),
        "prompt_text": prompt, "prompt_lang": "ja",
        "text_split_method": "cut5",
    }
    dst = OUT / f"{tag}_{ref_key}.mp3"
    if dst.exists():
        log(f"跳过 {dst.name}")
        return True
    req = urllib.request.Request(API, json.dumps(body).encode(), {"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            wav = urllib.request.urlopen(req, timeout=300).read()
            p = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", "pipe:0", "-b:a", "128k", str(dst)],
                               input=wav, capture_output=True)
            if p.returncode == 0 and dst.stat().st_size > 10000:
                log(f"OK {dst.name} {dst.stat().st_size // 1024}KB")
                return True
        except Exception as e:
            log(f"attempt{attempt} {dst.stem}: {e}")
            time.sleep(5)
    return False


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    log("等待 GPT e10 权重(=全部训练结束)...")
    while not list(GPT_DIR.glob("maya-e10*.ckpt")):  # s1 保存命名: maya-e5.ckpt (连字符+ckpt)
        time.sleep(60)
    log("e10 已出, 等训练进程退出释放显存")
    time.sleep(90)
    kill_port(9880)
    time.sleep(3)
    start_api()
    set_weights("sovits", SOVITS_E3)

    for tag, ep in ROUNDS:
        if ep:
            w = list(GPT_DIR.glob(f"maya-{ep}*.ckpt"))[0]
            set_weights("gpt", w)
        for rk in REFS:
            synth(tag, rk)

    log("全部完成 → " + str(OUT))


if __name__ == "__main__":
    main()
