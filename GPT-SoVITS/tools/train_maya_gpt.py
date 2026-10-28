"""方案 C: GPT(s1) 微调配置生成 + 启动器
复刻 webui open1b(GPT训练) 的构造逻辑。预处理产物复用 logs/maya 现成的
2-name2text.txt / 6-name2semantic.tsv, 无需重跑预处理。
用法:
  python train_maya_gpt.py          # 只生成 tmp_s1.yaml 并打印命令
  python train_maya_gpt.py --go     # 生成配置并启动训练(需 GPU 空闲)
注意: 训练前必须停掉 SoVITS 训练/api_v2 释放显存。
"""
import os
import subprocess
import sys
from pathlib import Path

import yaml

PKG = Path(r"F:\self_project\Sia-ai\GPT-SoVITS\GPT-SoVITS-v2pro-20261006")
os.chdir(PKG)

TEMPLATE = "GPT_SoVITS/configs/s1longer-v2.yaml"
CFG_OUT = PKG / "tmp_s1.yaml"
GPT_ROOT = "GPT_weights_v2ProPlus"

with open(TEMPLATE, encoding="utf-8") as f:
    data = yaml.safe_load(f)

data["train"].update({
    "batch_size": 2,              # 1050Ti 4GB, webui 默认 mem//2
    "epochs": 20,
    "save_every_n_epoch": 5,      # 续训: e10 resume -> e15 / e20 各存一版
    "if_save_every_weights": True,
    "if_save_latest": True,
    "if_dpo": False,
    "half_weights_save_dir": GPT_ROOT,
    "exp_name": "maya",
})
data["pretrained_s1"] = "GPT_SoVITS/pretrained_models/s1v3.ckpt"
data["train_semantic_path"] = "logs/maya/6-name2semantic.tsv"
data["train_phoneme_path"] = "logs/maya/2-name2text.txt"
data["output_dir"] = "logs/maya/logs_s1_v2ProPlus"

(CFG_OUT).write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
os.makedirs(PKG / data["output_dir"], exist_ok=True)
os.makedirs(PKG / GPT_ROOT, exist_ok=True)   # webui open 时才建, 提前建防 e2 式保存崩溃

cmd = f'"{PKG / "runtime" / "python.exe"}" -s GPT_SoVITS/s1_train.py --config_file "{CFG_OUT}"'
print("config ->", CFG_OUT)
print("cmd:", cmd)

if "--go" in sys.argv:
    env = os.environ.copy()
    env["_CUDA_VISIBLE_DEVICES"] = "0"
    env["hz"] = "25hz"
    env["TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD"] = "1"  # resume ckpt 含 WindowsPath pickle, torch2.6 默认 weights_only=True 会拒载
    log = open(PKG.parent / "_training" / "gpt_train_err.txt", "w", encoding="utf-8", errors="replace")
    out = open(PKG.parent / "_training" / "gpt_train_log.txt", "w", encoding="utf-8", errors="replace")
    p = subprocess.Popen(cmd, cwd=PKG, shell=True, env=env, stdout=out, stderr=log)
    print("started pid:", p.pid)
