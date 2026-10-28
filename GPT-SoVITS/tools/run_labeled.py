"""用户标注的 13 条锚点样本 → 声学画像表"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from voice_profile import analyze

LABELED = [
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\z0001\z0001_0306.ogg", "会长"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\z0001\z0001_0343.ogg", "老师"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_audition\z4001\z4001_0022.ogg", "月岛叶"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0002_0131.ogg", "电话(主角+雪乃)"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_0073.ogg", "瑠奈"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_0220.ogg", "雪乃"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_0381.ogg", "瑠奈"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_0655.ogg", "月岛叶"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_2090.ogg", "摩耶"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_2094.ogg", "摩耶"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_2096.ogg", "摩耶"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_2262.ogg", "摩耶"),
    (r"F:\self_project\Sia-ai\GPT-SoVITS\_voices\z0003_2027.ogg", "电话(主角+摩耶)"),
]

rows = {}
for path, who in LABELED:
    r = analyze(Path(path))
    r["who"] = who
    rows.setdefault(who, []).append(r)

hdr = f"{'角色':<10} {'n':>2} {'f0_med':>14} {'f0_p10':>14} {'f0_p90':>14} {'centroid':>9} {'voicing':>8}"
print(hdr)
for who, rs in rows.items():
    def agg(k):
        v = [x[k] for x in rs if x[k]]
        return f"{min(v):.0f}~{max(v):.0f}" if v else "-"
    print(f"{who:<10} {len(rs):>2} {agg('f0_med'):>14} {agg('f0_p10'):>14} {agg('f0_p90'):>14} "
          f"{agg('centroid_med'):>9} {agg('voicing'):>8}")
