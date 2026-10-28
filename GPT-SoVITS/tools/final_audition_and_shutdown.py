"""终盘编排: 等全量 e8 权重 -> 四档对比合成 -> 关机
四档 = 精选 e15/e20 + 全量 e4/e8 (GPT 侧切换, SoVITS 固定 maya_e3.pth)。
用户指令: 训练跑完后生成试听音频再关机; 无论成败最终都关机 (shutdown /a 可取消)。
产物: _audition/full_vs_sel/ 下 8 个 mp3 (4 档 x 温柔/小恶魔 2 ref)。
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
OUT = ROOT / "_audition" / "full_vs_sel"
E8 = GPT_DIR / "maya_full-e8.ckpt"
API = "http://127.0.0.1:9880/tts"

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
# 四档 (GPT 侧), SoVITS 统一 maya_e3.pth
ROUNDS = [
    ("sel_e15", GPT_DIR / "maya-e15.ckpt"),
    ("sel_e20", GPT_DIR / "maya-e20.ckpt"),
    ("full_e4", GPT_DIR / "maya_full-e4.ckpt"),
    ("full_e8", E8),
]


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
                log(f"killed pid {pid} on :{port}")


def s1_train_alive():
    try:
        import psutil
    except ImportError:
        return None  # 无法判断
    for p in psutil.process_iter(["cmdline"]):
        try:
            if "s1_train" in " ".join(p.info["cmdline"] or []):
                return True
        except Exception:
            pass
    return False


def start_api():
    subprocess.Popen(
        f'"{PY}" api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml',
        cwd=PKG, shell=True,
        stdout=open(ROOT / "_training" / "apiv2_final_log.txt", "w", encoding="utf-8"),
        stderr=subprocess.STDOUT)
    for _ in range(120):
        if api_ready():
            log("api_v2 ready")
            return
        time.sleep(5)
    raise RuntimeError("api start timeout")


def set_weights(kind, path):
    from urllib.parse import quote
    q = quote(str(path).replace("\\", "/"), safe="")
    r = urllib.request.urlopen(
        f"http://127.0.0.1:9880/set_{kind}_weights?weights_path={q}", timeout=600).read()
    log(f"set_{kind}_weights: {Path(str(path)).name} -> {r[:40]}")


def synth(tag, ref_key):
    ref_path, prompt = REFS[ref_key]
    body = {
        "text": TEXTS[ref_key], "text_lang": "zh",
        "ref_audio_path": str(ref_path).replace("\\", "/"),
        "prompt_text": prompt, "prompt_lang": "ja",
        "text_split_method": "cut5",
    }
    dst = OUT / f"{tag}_{ref_key}.mp3"
    if dst.exists() and dst.stat().st_size > 10000:
        log(f"skip {dst.name}")
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
    for _, w in ROUNDS[:-1]:
        assert w.exists(), f"missing weight: {w}"

    # 1) 等全量 e8 推理权重 (s1_train if_save_every_weights 自动落盘)
    log("等待 maya_full-e8.ckpt 落盘 (上限 150min)...")
    deadline = time.time() + 150 * 60
    while not E8.exists():
        if time.time() > deadline:
            log("E8 WAIT TIMEOUT - 用现有档位继续")
            break
        time.sleep(60)
    log(f"e8 exists: {E8.exists()}")

    # 2) 等训练进程退出释放显存 (上限 20min)
    log("等待 s1_train 退出...")
    d2 = time.time() + 20 * 60
    while time.time() < d2:
        alive = s1_train_alive()
        if alive is False:
            log("s1_train 已退出")
            break
        time.sleep(30)
    else:
        log("s1_train 检测超时/不可用, 继续 (api 可能显存吃紧)")
    time.sleep(10)

    # 3) 起 api 合成四档
    rounds = [(t, w) for t, w in ROUNDS if w.exists()]
    log(f"rounds: {[t for t, _ in rounds]}")
    ok, total = 0, 0
    api_pid = None
    try:
        kill_port(9880)
        time.sleep(3)
        start_api()
        set_weights("sovits", SOVITS_E3)
        for tag, w in rounds:
            set_weights("gpt", w)
            for rk in REFS:
                total += 1
                if synth(tag, rk):
                    ok += 1
    finally:
        kill_port(9880)
        log(f"合成完成 {ok}/{total} -> {OUT}")
        # 4) 关机 (用户授权; 120s 缓冲可 shutdown /a 取消)
        log("120s 后关机 (shutdown /a 可取消)")
        subprocess.run(["shutdown", "/s", "/t", "120", "/c",
                        "Sia-ai: audition done, auto shutdown"], capture_output=True)


if __name__ == "__main__":
    main()
