# -*- coding: utf-8 -*-
"""RVC maya 模型变声: Edge-TTS 念稿(20句) -> 摩耶音色 -> _audition/gate/svc_edge/*.wav
前置: assets/weights 里已有 maya_svc_e*.pth(训练链产物)
用法: RVC包根下  runtime\\python.exe F:\\...\\tools\\svc_convert.py [--key 0]
"""
import os
import sys
from pathlib import Path

PKG = Path(r"F:\self_project\Sia-ai\RVC\pkg\RVC20260718Nvidia")
SRC = Path(r"F:\self_project\Sia-ai\RVC\src_edge")
OUT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\gate\svc_edge")

sys.path.insert(0, str(PKG))
os.chdir(PKG)
os.environ["weight_root"] = "assets/weights"


def pick_weight():
    ws = sorted(Path("assets/weights").glob("*maya_svc_e*.pth"),
                key=lambda p: p.stat().st_mtime)
    if not ws:
        return None
    # 优先总 epoch 最高的(e200 > e150 ...)
    best = max(ws, key=lambda p: int(p.stem.split("_e")[-1].split("_")[0]))
    return best.name


def main():
    from configs.config import Config
    from infer.vc.modules import VC

    OUT.mkdir(parents=True, exist_ok=True)
    sid = pick_weight()
    if sid is None:
        print("no maya_svc weight yet")
        sys.exit(1)
    print("weight:", sid)

    idxs = sorted(Path("logs/maya_svc").glob("added_*.index"))
    index = str(idxs[-1]) if idxs else ""
    print("index:", index)

    key = 0
    if "--key" in sys.argv:
        key = int(sys.argv[sys.argv.index("--key") + 1])

    cfg = Config()
    vc = VC(cfg)
    vc.get_vc(sid)

    files = sorted(SRC.glob("*.mp3"))
    ok = 0
    for f in files:
        dst = OUT / f"{f.stem}.wav"
        if dst.exists() and dst.stat().st_size > 10000:
            ok += 1
            continue
        try:
            info, audio = vc.vc_single(sid, str(f), key, "rmvpe",
                                       index, 0.75, 0, 0.25, 0.33)
            if audio is None:
                print(f"FAIL {f.stem}: {info}")
                continue
            sr, np_audio = audio
            import soundfile as sf
            sf.write(str(dst), np_audio, sr)
            ok += 1
            print(f"OK {f.stem}")
        except Exception as e:
            print(f"FAIL {f.stem}: {str(e)[:120]}")
    print(f"转换完成 {ok}/{len(files)} -> {OUT}")


if __name__ == "__main__":
    main()
