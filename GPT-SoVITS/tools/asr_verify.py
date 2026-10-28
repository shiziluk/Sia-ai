"""ASR 回验: 合成音频内容 vs 设定文本
funasr paraformer-large (整合包已缓存, CPU 跑)
verify(path, expected) -> (ok, transcript)
"""
import re
from pathlib import Path

ASR_DIR = Path(r"F:\self_project\Sia-ai\GPT-SoVITS\GPT-SoVITS-v2pro-20261006\tools\asr\models")
_model = None


def _norm(t: str) -> str:
    return re.sub(r"[，。！？、,.!?~～\s]", "", t)


def get_model():
    global _model
    if _model is None:
        from funasr import AutoModel
        _model = AutoModel(
            model=str(next(ASR_DIR.glob("speech_paraformer-large*"))),
            vad_model=str(next(ASR_DIR.glob("speech_fsmn_vad*"))),
            device="cpu", disable_update=True, disable_pbar=True,
        )
    return _model


def verify(mp3_path, expected: str):
    """转写并归一化对比。返回 (是否一致, 转写文本)"""
    wav = Path(mp3_path).with_suffix(".verify.wav")
    import subprocess
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(mp3_path),
                    "-ar", "16000", "-ac", "1", str(wav)], capture_output=True)
    r = get_model().generate(input=str(wav), batch_size_s=60)
    text = r[0]["text"] if r else ""
    wav.unlink(missing_ok=True)
    return _norm(expected) == _norm(text), text


if __name__ == "__main__":
    import sys
    ok, text = verify(sys.argv[1], sys.argv[2])
    print(("PASS" if ok else "MISMATCH"), "|", text)
