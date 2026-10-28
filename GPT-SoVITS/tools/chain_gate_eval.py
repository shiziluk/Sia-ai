"""e16 完成后自动评测链: 等 GPU 空闲 -> api_v2 -> 合成4档x20句 -> 三道门禁评分
触发: schtasks gate_eval_chain (5min 轮询由脚本内 sleep 实现, 单次任务)
产出: _audition/gate/report_*.json + gate_chain_log.txt
"""
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
PKG = ROOT / "GPT-SoVITS-v2pro-20261006"
PY = PKG / "runtime" / "python.exe"
E16 = PKG / "GPT_weights_v2ProPlus" / "maya_full-e16.ckpt"
TAGS = [
    ("base_gpt", "GPT_SoVITS/pretrained_models/s1v3.ckpt", "refs"),
    ("full_e8",  "GPT_weights_v2ProPlus/maya_full-e8.ckpt", "refs"),
    ("sel_e20",  "GPT_weights_v2ProPlus/maya-e20.ckpt", "refs"),
    ("full_e12", "GPT_weights_v2ProPlus/maya_full-e12.ckpt", "refs"),
    ("full_e16", "GPT_weights_v2ProPlus/maya_full-e16.ckpt", "refs"),
    # ref 消融: 同 sel_e20 权重, 换摩耶日文原声 ref -> 验证洋腔的 ref 因素
    ("sel_e20_mr", "GPT_weights_v2ProPlus/maya-e20.ckpt", "refs_maya"),
]


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


def train_alive():
    out = subprocess.run(["wmic", "process", "where", "name='python.exe'", "get", "commandline"],
                         capture_output=True, text=True).stdout
    return "s1_train" in out


def gpu_free():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.strip()
    try:
        return int(out) < 1500
    except ValueError:
        return False


def api_ready():
    try:
        urllib.request.urlopen("http://127.0.0.1:9880/openapi.json", timeout=3).read()
        return True
    except Exception:
        return False


def start_api():
    subprocess.Popen(
        f'"{PY}" api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml',
        cwd=PKG, shell=True,
        stdout=open(ROOT / "_training" / "apiv2_log.txt", "w", encoding="utf-8"),
        stderr=subprocess.STDOUT)
    for _ in range(120):
        if api_ready():
            log("api_v2 就绪")
            return True
        time.sleep(5)
    return False


def kill_api():
    out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True).stdout
    pids = {int(l.split()[-1]) for l in out.splitlines()
            if ":9880" in l and "LISTENING" in l.upper() and l.split()[-1].isdigit()}
    for pid in pids:
        subprocess.run(["taskkill", "/f", "/pid", str(pid), "/t"], capture_output=True)


def main():
    log("等待 e16 落盘且训练退出 ...")
    while True:
        if E16.exists() and not train_alive():
            break
        time.sleep(300)
    log("e16 已出, 训练已退出")
    time.sleep(20)
    for _ in range(30):
        if gpu_free():
            break
        time.sleep(60)
    kill_api()
    if not start_api():
        log("api_v2 启动失败, 退出")
        return
    for tag, gpt, refset in TAGS:
        r = subprocess.run([str(PY), str(ROOT / "tools" / "eval_gate.py"), "synth",
                            "--tag", tag, "--gpt", gpt, "--refset", refset],
                           capture_output=True, text=True, cwd=str(PKG))
        log(f"[{tag}] synth rc={r.returncode}")
        print(r.stdout[-500:], flush=True)
    kill_api()
    log("合成全部完成, 释放显存后进入评分 (CPU)")
    r = subprocess.run([str(PY), str(ROOT / "tools" / "eval_gate.py"), "score",
                        "--tags", "base_gpt", "full_e8", "sel_e20", "full_e12", "full_e16", "sel_e20_mr"],
                       capture_output=True, text=True, cwd=str(PKG))
    log(f"score rc={r.returncode}")
    print(r.stdout[-3000:], flush=True)
    log("评测链结束")


if __name__ == "__main__":
    main()
