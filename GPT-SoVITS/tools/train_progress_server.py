"""训练进度 HTTP 服务：GET http://127.0.0.1:9881/progress
解析 train_err.txt(tqdm 实时 step) + train.log(epoch/保存事件) + 权重目录 + nvidia-smi
stdlib only, 常驻运行, CORS 全开(供 inline widget fetch 轮询)
"""
import glob
import json
import os
import re
import subprocess
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = r"F:\self_project\Sia-ai\GPT-SoVITS"
PKG = os.path.join(ROOT, "GPT-SoVITS-v2pro-20261006")
ERR_LOG = os.path.join(ROOT, "_training", "train_err.txt")
OUT_LOG = os.path.join(ROOT, "_training", "train_log.txt")
WEIGHT_DIR = os.path.join(PKG, "SoVITS_weights_v2ProPlus")
PORT = 9881

TQDM_RE = re.compile(r"(\d+)/(\d+) \[([^\]]*?)<([\d:]+),\s*([\d.]+)s/it")
EPOCH_START_RE = re.compile(r"start training from epoch (\d+)")
SAVED_RE = re.compile(r"Saving model and optimizer state at iteration (\d+)")
TRAIN_EPOCH_RE = re.compile(r"Train Epoch: (\d+) \[(\d+)%\]")
TOTAL_PER_EPOCH = 751
PLANNED_EPOCHS = 3


def tail(path, nbytes=16384):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - nbytes))
            return f.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""


def parse():
    err = tail(ERR_LOG)
    out = tail(OUT_LOG, 65536)

    step, total, eta_s, speed = 0, TOTAL_PER_EPOCH, None, None
    m = None
    for m in TQDM_RE.finditer(err):
        pass
    if m:
        step = int(m.group(1))
        total = int(m.group(2))
        speed = float(m.group(5))
        parts = [int(x) for x in m.group(4).split(":")]
        eta_s = parts[-1] + parts[-2] * 60 if len(parts) >= 2 else parts[0]
        if len(parts) == 3:
            eta_s += parts[0] * 3600

    starts = EPOCH_START_RE.findall(out)
    start_epoch = int(starts[-1]) if starts else 1
    saved_iters = SAVED_RE.findall(out)
    saved_count = len(saved_iters)
    current_epoch = start_epoch + saved_count
    weights_list = sorted(os.path.basename(p) for p in glob.glob(os.path.join(WEIGHT_DIR, "maya_e*.pth")))
    finished = saved_count >= PLANNED_EPOCHS or "maya_e%d.pth" % PLANNED_EPOCHS in weights_list
    te = TRAIN_EPOCH_RE.findall(out)
    train_epoch_last = te[-1] if te else None

    remaining = (PLANNED_EPOCHS - current_epoch) * TOTAL_PER_EPOCH + max(0, total - step)
    eta_min = remaining * speed / 60 if (speed and not finished) else 0

    if step != _step_track["step"]:
        _step_track.update(step=step, t=time.time(), alive=True)
    elif _step_track["alive"] is None or (
        _step_track["alive"] and time.time() - _step_track["t"] > 120
    ):
        _step_track["alive"] = False

    return {
        "current_epoch": min(current_epoch, PLANNED_EPOCHS),
        "planned_epochs": PLANNED_EPOCHS,
        "step": step,
        "total": total,
        "speed": speed,
        "eta_min": round(eta_min),
        "finished": bool(finished),
        "saved_iters": saved_iters[-3:],
        "weights": weights_list,
        "train_epoch_last": train_epoch_last,
        "alive": _step_track["alive"],
        "log_tail": [ln for ln in tail(OUT_LOG, 4096).splitlines()[-6:] if ln.strip()],
        "ts": time.strftime("%H:%M:%S"),
    }


_gpu_cache = {"t": 0, "data": {"util": None, "mem": None}}
_step_track = {"step": -1, "t": 0.0, "alive": None}


def gpu():
    if time.time() - _gpu_cache["t"] > 10:
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            util, mem = out.split(",")
            _gpu_cache["data"] = {"util": int(util), "mem": int(mem)}
            _gpu_cache["t"] = time.time()
        except Exception:
            pass
    return _gpu_cache["data"]


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            try:
                with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "progress.html"), "rb") as f:
                    body = f.read()
                ctype = "text/html; charset=utf-8"
            except OSError:
                self.send_error(404)
                return
        elif self.path == "/progress":
            body = json.dumps({**parse(), "gpu": gpu()}).encode("utf-8")
            ctype = "application/json; charset=utf-8"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"progress server on http://127.0.0.1:{PORT}/progress", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
