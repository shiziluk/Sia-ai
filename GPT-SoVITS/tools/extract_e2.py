"""从训练 checkpoint (G_233333333333.pth) 提取 e2 推理权重
复刻 process_ckpt.savee + my_save2 的保存逻辑(v2ProPlus 头 b"06", half 精度)。
用法: runtime\\python.exe extract_e2.py
"""
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path

PKG = Path(r"F:\self_project\Sia-ai\GPT-SoVITS\GPT-SoVITS-v2pro-20261006")
sys.path.insert(0, str(PKG / "GPT_SoVITS"))
os.chdir(PKG)

import torch
from utils import HParams
from process_ckpt import my_save2, model_version2byte

CKPT = PKG / "logs" / "maya" / "logs_s2_v2ProPlus" / "G_233333333333.pth"
CFG = PKG / "tmp_s2.json"
OUT = PKG / "SoVITS_weights_v2ProPlus" / "maya_e2.pth"

OUT.parent.mkdir(parents=True, exist_ok=True)

ck = torch.load(CKPT, map_location="cpu", weights_only=False)
state = ck["model"] if isinstance(ck, dict) and "model" in ck else ck
print("checkpoint keys:", list(ck.keys()) if isinstance(ck, dict) else type(ck))
print("weight tensors:", len(state))

opt = OrderedDict()
opt["weight"] = {k: v.half() for k, v in state.items() if "enc_q" not in k}
opt["config"] = HParams(**json.loads(CFG.read_text(encoding="utf-8")))
opt["info"] = "2epoch_1502iteration"
my_save2(opt, str(OUT), "v2ProPlus")
print(f"OK -> {OUT}  {OUT.stat().st_size // 1024 // 1024}MB")
