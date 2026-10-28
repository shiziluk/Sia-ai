"""全量摩耶 GPT 训练接力: 等 e20(精选版终点) -> 等训练进程退出 -> 全量预处理 -> 全量 GPT 训练
全量 = maya.list 全部 7453 条(不做时长过滤/采样); GPT 训练只需 2-name2text.txt + 6-name2semantic.tsv,
预处理跑 1-get-text + 2-get-hubert-wav32k + 3-get-semantic(semantic 依赖 4-cnhubert/*.pt,
跳过的只有 2-get-sv, 那是 SoVITS s2 训练专用)。
脚本产物带 -0 后缀, 尾部合并成无后缀文件。跳过已完成的 1-get-text(2-name2text-0.txt 已在)。
产物隔离: exp_name=maya_full, opt_dir=logs/maya_full, 存档 maya_full-e4/e8.ckpt
"""
import os
import subprocess
import time
from pathlib import Path

import yaml

ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
PKG = ROOT / "GPT-SoVITS-v2pro-20261006"
PYEXE = PKG / "runtime" / "python.exe"
LIST = ROOT / "_training" / "maya.list"          # 全量 7453 行
WAVDIR = ROOT / "_training" / "wav"              # 全量 7453 wav
E20 = PKG / "GPT_weights_v2ProPlus" / "maya-e20.ckpt"
CHLOG = ROOT / "_training" / "chain_full_log.txt"

BASE_ENV = {
    "inp_text": str(LIST),
    "inp_wav_dir": str(WAVDIR),
    "exp_name": "maya_full",
    "opt_dir": "logs/maya_full",
    "i_part": "0",
    "all_parts": "1",
    "_CUDA_VISIBLE_DEVICES": "0",
    "is_half": "True",
}
STEPS = [
    ("1-get-text", "GPT_SoVITS/prepare_datasets/1-get-text.py", {
        **BASE_ENV,
        "bert_pretrained_dir": "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large",
    }),
    ("2-hubert-wav32k", "GPT_SoVITS/prepare_datasets/2-get-hubert-wav32k.py", {
        **BASE_ENV,
        "cnhubert_base_dir": "GPT_SoVITS/pretrained_models/chinese-hubert-base",
        "sv_path": "GPT_SoVITS/pretrained_models/sv/pretrained_eres2netv2w24s4ep4.ckpt",
    }),
    ("3-get-semantic", "GPT_SoVITS/prepare_datasets/3-get-semantic.py", {
        **BASE_ENV,
        "pretrained_s2G": "GPT_SoVITS/pretrained_models/v2Pro/s2Gv2ProPlus.pth",
        "s2config_path": "GPT_SoVITS/configs/s2v2ProPlus.json",
    }),
]

cfg_log = lambda *a: print(*a, flush=True)


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    cfg_log(line)
    with CHLOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def gpu_mem():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return int(out.splitlines()[0])
    except Exception:
        return -1


def wait_e20():
    log("等待精选版 e20 落盘...")
    while not E20.exists():
        time.sleep(60)
    log(f"e20 已出现: {E20.name}")


def wait_gpu_free():
    log("等待训练进程退出/GPU 释放...")
    stable = 0
    fail = 0
    while stable < 4:
        m = gpu_mem()
        if m < 0:   # nvidia-smi 不可达(schtasks 环境 PATH 差异) -> 改用 s1_train 进程存活判断
            fail += 1
            if fail >= 3:
                log("nvidia-smi 不可达, 改用 s1_train 进程检测放行")
                try:
                    import psutil
                except ImportError:
                    log("psutil 不可用, 直接放行(GPU 已人工确认 0MB)")
                    return
                while True:
                    alive = any("s1_train" in " ".join(p.info["cmdline"] or [])
                                for p in psutil.process_iter(["cmdline"]))
                    if not alive:
                        log("s1_train 进程已退出, 放行")
                        return
                    time.sleep(30)
            time.sleep(30)
            continue
        fail = 0
        if 0 <= m < 500:
            stable += 1
        else:
            stable = 0
        time.sleep(30)
    log("GPU 已释放")


def preprocess():
    for name, script, cfg_env in STEPS:
        log(f"=== 全量预处理 {name} 开始 ===")
        env = {**os.environ.copy(), **cfg_env}
        p = subprocess.run([str(PYEXE), "-s", script], cwd=str(PKG), env=env)
        if p.returncode != 0:
            raise SystemExit(f"预处理 {name} 失败 returncode={p.returncode}")
        log(f"=== 全量预处理 {name} 完成 ===")
    # 合并 -0 后缀产物 -> 无后缀(webui 风格), s1_train 只认无后缀
    opt = PKG / "logs/maya_full"
    part = opt / "2-name2text-0.txt"
    full = opt / "2-name2text.txt"
    full.write_text(part.read_text(encoding="utf8").strip("\n") + "\n", encoding="utf8")
    log(f"合并 {full.name}: {len(full.read_text(encoding='utf8').splitlines())} 行")
    part = opt / "6-name2semantic-0.tsv"
    full = opt / "6-name2semantic.tsv"
    body = part.read_text(encoding="utf8").strip("\n")
    full.write_text("item_name\tsemantic_audio\n" + body + "\n", encoding="utf8")
    log(f"合并 {full.name}: {len(body.splitlines())} 行")
    part.unlink()
    (opt / "2-name2text-0.txt").unlink()
    # 产物核验
    for fn in ("2-name2text.txt", "6-name2semantic.tsv"):
        n = len((opt / fn).read_text(encoding="utf-8").splitlines())
        log(f"产物 {fn}: {n} 行")
        assert n > 7000, f"{fn} 行数异常"


def train():
    with open(PKG / "GPT_SoVITS/configs/s1longer-v2.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data["train"].update({
        "batch_size": 2,
        "epochs": 8,
        "save_every_n_epoch": 4,          # e4 / e8 各存一版
        "if_save_every_weights": True,
        "if_save_latest": True,
        "if_dpo": False,
        "half_weights_save_dir": "GPT_weights_v2ProPlus",
        "exp_name": "maya_full",
    })
    data["pretrained_s1"] = "GPT_SoVITS/pretrained_models/s1v3.ckpt"
    data["train_semantic_path"] = "logs/maya_full/6-name2semantic.tsv"
    data["train_phoneme_path"] = "logs/maya_full/2-name2text.txt"
    data["output_dir"] = "logs/maya_full/logs_s1_v2ProPlus"
    cfg = PKG / "tmp_s1_full.yaml"
    cfg.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
    os.makedirs(PKG / data["output_dir"], exist_ok=True)
    env = {**os.environ.copy(),
           "_CUDA_VISIBLE_DEVICES": "0", "hz": "25hz",
           "TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD": "1"}
    cmd = f'"{PYEXE}" -s GPT_SoVITS/s1_train.py --config_file "{cfg}"'
    out = open(ROOT / "_training" / "gpt_full_log.txt", "w", encoding="utf-8", errors="replace")
    err = open(ROOT / "_training" / "gpt_full_err.txt", "w", encoding="utf-8", errors="replace")
    p = subprocess.Popen(cmd, cwd=str(PKG), shell=True, env=env, stdout=out, stderr=err)
    log(f"全量训练已启动 pid={p.pid} epochs=8 batch=2, 日志 _training/gpt_full_*.txt")


if __name__ == "__main__":
    assert LIST.exists() and LIST.read_text(encoding="utf-8").count("\n") > 7000, "maya.list 非全量"
    wait_e20()
    wait_gpu_free()
    preprocess()
    train()
    log("接力完成, 全量训练运行中 (预计 ~2.5-3h)")
