# -*- coding: utf-8 -*-
"""
rvc_prepare_expdir.py - 补齐 RVC 实验目录缺失的 config.json / filelist.txt

背景：绕过 webui 直接跑 train/train.py 时，train/utils.py:get_hparams() 会硬读
    ./logs/<exp>/config.json
    ./logs/<exp>/filelist.txt   (hparams.data.training_files)
这两个文件平时由 webui.py 的训练入口生成（webui.py:961 写 filelist，:975-985 写 config）。
链脚本若跳过 webui，必须自己补，否则 FileNotFoundError。

用法（cwd 任意）：
    python tools/rvc_prepare_expdir.py --exp maya_svc --sr 40k
    python tools/rvc_prepare_expdir.py --exp maya_svc --sr 40k --dry-run

规则：
- config.json：sr=40k 一律取 configs/v1/40k.json（webui.py:971，与 -v v2 无关）
- filelist.txt：按 webui.py:904-935，取四个子目录文件名交集，spk_id 默认 0
"""
import argparse
import json
import os
import shutil
import sys

PKG_DEFAULT = r"F:\self_project\Sia-ai\RVC\pkg\RVC20260718Nvidia"


def build_filelist(exp_dir, spk_id=0):
    """复刻 webui.py:904-935 的 filelist 生成逻辑。"""
    gt_dir = os.path.join(exp_dir, "0_gt_wavs")
    fea_dir = os.path.join(exp_dir, "3_feature768")
    f0_dir = os.path.join(exp_dir, "2a_f0")
    f0nsf_dir = os.path.join(exp_dir, "2b-f0nsf")

    for d in (gt_dir, fea_dir, f0_dir, f0nsf_dir):
        if not os.path.isdir(d):
            raise SystemExit("[FATAL] 缺少目录: %s （预处理未跑完）" % d)

    names = (
        {n.split(".")[0] for n in os.listdir(gt_dir)}
        & {n.split(".")[0] for n in os.listdir(fea_dir)}
        & {n.split(".")[0] for n in os.listdir(f0_dir)}
        & {n.split(".")[0] for n in os.listdir(f0nsf_dir)}
    )
    if not names:
        raise SystemExit("[FATAL] 四目录交集为空，无有效训练样本")

    # webui 写盘时把 \ 转义成 \\（源码 gt_wavs_dir.replace("\\", "\\\\")），此处保持一致
    esc = lambda p: p.replace("\\", "\\\\")
    gt_e, fea_e = esc(gt_dir), esc(fea_dir)
    f0_e, f0nsf_e = esc(f0_dir), esc(f0nsf_dir)

    lines = [
        "%s\\%s.wav|%s\\%s.npy|%s\\%s.wav.npy|%s\\%s.wav.npy|%s"
        % (gt_e, n, fea_e, n, f0_e, n, f0nsf_e, n, spk_id)
        for n in sorted(names)
    ]
    return lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", default=PKG_DEFAULT, help="RVC 整合包根目录")
    ap.add_argument("--exp", default="maya_svc", help="实验目录名（logs/<exp>）")
    ap.add_argument("--sr", default="40k", choices=["32k", "40k", "48k"])
    ap.add_argument("--spk-id", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    exp_dir = os.path.join(args.pkg, "logs", args.exp)
    if not os.path.isdir(exp_dir):
        raise SystemExit("[FATAL] 实验目录不存在: %s" % exp_dir)

    # 1) config.json —— sr=40k 固定取 v1/40k.json（webui.py:971）
    src_cfg = os.path.join(args.pkg, "configs", "v1", "%s.json" % args.sr)
    dst_cfg = os.path.join(exp_dir, "config.json")
    with open(src_cfg, encoding="utf-8") as f:
        cfg = json.load(f)
    print("[OK] 模板 %s -> %s (sampling_rate=%s)"
          % (os.path.basename(src_cfg), dst_cfg, cfg["data"]["sampling_rate"]))

    # 2) filelist.txt
    lines = build_filelist(exp_dir, args.spk_id)
    dst_fl = os.path.join(exp_dir, "filelist.txt")
    print("[OK] filelist 样本数 = %d -> %s" % (len(lines), dst_fl))
    print("     样例: %s" % lines[0])

    if args.dry_run:
        print("\n[dry-run] 未写入任何文件")
        return

    if os.path.exists(dst_cfg):
        print("[SKIP] config.json 已存在，不覆盖")
    else:
        shutil.copyfile(src_cfg, dst_cfg)
        print("[WRITE] config.json")

    with open(dst_fl, "w", encoding="utf8") as f:
        f.write("\n".join(lines))
    print("[WRITE] filelist.txt (%d 行)" % len(lines))
    print("\n[DONE] 现在可以重跑 svc_train_chain.cmd")


if __name__ == "__main__":
    sys.exit(main())
