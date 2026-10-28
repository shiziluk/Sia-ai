"""摩耶 SoVITS 微调一键脚本（停api_v2 → 预处理4步 → 生成配置 → s2_train）

策略: SoVITS 主训(内化音色), GPT 保留底模(保中文韵律) → 只训 s2 不训 s1
前置: _training/maya.list + _training/wav/*.wav 已由 gen_train_list.py 生成
用法: GPT-SoVITS-v2pro-20261006/runtime/python.exe tools/train_maya.py
产出: logs/maya/ 预处理产物; SoVITS_weights_v2ProPlus/maya_e{5,10,...}.pth + latest
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # GPT-SoVITS/
PKG = ROOT / "GPT-SoVITS-v2pro-20261006"  # 整合包根
PYEXE = PKG / "runtime" / "python.exe"
LIST = ROOT / "_training" / "maya_train.list"  # 精选子集(filter_maya_list.py 生成)
WAVDIR = ROOT / "_training" / "wav"
OPT_DIR = "logs/maya"  # 相对包根
VERSION = "v2ProPlus"
BATCH_SIZE = 2
EPOCHS = 3  # 6小时数据过1个epoch已等效社区"10分钟素材×30epoch"的量, 3 epoch足够; 1050Ti实测~5s/step, 每epoch约4-5h
SAVE_EVERY = 1

BASE_ENV = {
    "inp_text": str(LIST),
    "inp_wav_dir": str(WAVDIR),
    "exp_name": "maya",
    "opt_dir": OPT_DIR,
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
    ("2-sv", "GPT_SoVITS/prepare_datasets/2-get-sv.py", {
        **BASE_ENV,
        "cnhubert_base_dir": "GPT_SoVITS/pretrained_models/chinese-hubert-base",
        "sv_path": "GPT_SoVITS/pretrained_models/sv/pretrained_eres2netv2w24s4ep4.ckpt",
    }),
    ("3-semantic", "GPT_SoVITS/prepare_datasets/3-get-semantic.py", {
        **BASE_ENV,
        "pretrained_s2G": "GPT_SoVITS/pretrained_models/v2Pro/s2Gv2ProPlus.pth",
        "s2config_path": "GPT_SoVITS/configs/s2v2ProPlus.json",
    }),
]


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def kill_api_v2():
    """训练前必须停 api_v2：4GB 显存装不下训练+推理并存"""
    try:
        import psutil
    except ImportError:
        log("psutil 不可用，跳过 kill api_v2（请确认 9880 端口无服务）")
        return
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            cl = p.info["cmdline"] or []
            if any("api_v2" in c for c in cl):
                p.kill()
                log(f"killed api_v2 pid={p.pid}")
        except Exception:
            pass


def precheck():
    assert LIST.exists(), f"清单不存在: {LIST}（先跑 gen_train_list.py）"
    n_list = len([l for l in LIST.read_text(encoding="utf-8").splitlines() if l.strip()])
    n_wav = len(list(WAVDIR.glob("*.wav"))) if WAVDIR.exists() else 0
    log(f"清单 {n_list} 行 / wav {n_wav} 条")
    assert n_list >= 1000 and n_wav >= 1000, "训练数据不足，先完成 gen_train_list.py"
    need = [
        PKG / "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large",
        PKG / "GPT_SoVITS/pretrained_models/chinese-hubert-base",
        PKG / "GPT_SoVITS/pretrained_models/sv/pretrained_eres2netv2w24s4ep4.ckpt",
        PKG / "GPT_SoVITS/pretrained_models/v2Pro/s2Gv2ProPlus.pth",
        PKG / "GPT_SoVITS/pretrained_models/v2Pro/s2Dv2ProPlus.pth",
    ]
    missing = [str(p) for p in need if not p.exists()]
    assert not missing, f"底模缺失: {missing}"


def run_preprocess():
    env_base = os.environ.copy()
    for name, script, cfg_env in STEPS:
        log(f"=== 预处理 {name} 开始 ===")
        env = {**env_base, **cfg_env}
        p = subprocess.run(
            [str(PYEXE), "-s", script],
            cwd=str(PKG), env=env,
        )
        if p.returncode != 0:
            raise SystemExit(f"预处理 {name} 失败 returncode={p.returncode}")
        log(f"=== 预处理 {name} 完成 ===")

    opt = PKG / "logs/maya"
    # 合并 2-name2text-0.txt -> 2-name2text.txt
    part = opt / "2-name2text-0.txt"
    full = opt / "2-name2text.txt"
    full.write_text(part.read_text(encoding="utf8").strip("\n") + "\n", encoding="utf8")
    part.unlink()
    log(f"合并 {full.name}: {len(full.read_text(encoding='utf8').splitlines())} 行")

    # 合并 6-name2semantic-0.tsv -> 6-name2semantic.tsv（带 header）
    part = opt / "6-name2semantic-0.tsv"
    full = opt / "6-name2semantic.tsv"
    body = part.read_text(encoding="utf8").strip("\n")
    full.write_text("item_name\tsemantic_audio\n" + body + "\n", encoding="utf8")
    part.unlink()
    log(f"合并 {full.name}: {len(body.splitlines())} 行")


def make_train_config():
    # webui open1Ba 负责建此目录, s2_train 自己不建; 缺失会在 epoch 末 save_checkpoint 时崩
    os.makedirs(str(PKG / f"logs/maya/logs_s2_{VERSION}"), exist_ok=True)
    cfg = json.loads((PKG / "GPT_SoVITS/configs/s2v2ProPlus.json").read_text(encoding="utf-8"))
    cfg["train"].update({
        "batch_size": BATCH_SIZE,
        "epochs": EPOCHS,
        "text_low_lr_rate": 0.5,
        "pretrained_s2G": "GPT_SoVITS/pretrained_models/v2Pro/s2Gv2ProPlus.pth",
        "pretrained_s2D": "GPT_SoVITS/pretrained_models/v2Pro/s2Dv2ProPlus.pth",
        "if_save_latest": True,
        "if_save_every_weights": True,
        "save_every_epoch": SAVE_EVERY,
        "gpu_numbers": "0",
        "grad_ckpt": True,  # 4GB 显存必须开梯度检查点
        "lora_rank": 32,
    })
    cfg["model"]["version"] = VERSION
    cfg["data"]["exp_dir"] = cfg["s2_ckpt_dir"] = OPT_DIR
    cfg["save_weight_dir"] = "SoVITS_weights_v2ProPlus"
    cfg["name"] = "maya"
    cfg["version"] = VERSION
    out = PKG / "tmp_s2.json"
    out.write_text(json.dumps(cfg), encoding="utf-8")
    log(f"训练配置已写 {out}")


def train():
    log("=== s2_train 启动（挂后台跑，权重每5epoch存一次）===")
    p = subprocess.run(
        [str(PYEXE), "-s", "GPT_SoVITS/s2_train.py", "--config", "tmp_s2.json"],
        cwd=str(PKG),
    )
    log(f"=== s2_train 结束 returncode={p.returncode} ===")


if __name__ == "__main__":
    kill_api_v2()
    precheck()
    run_preprocess()
    make_train_config()
    train()
