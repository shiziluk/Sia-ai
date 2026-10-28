"""GPT 续训实时进度监控服务 (127.0.0.1:9881)
数据源: Lightning tfevents (logs/maya/logs_s1_v2ProPlus/logs_s1_v2ProPlus/version_*) + ckpt 目录 + nvidia-smi
"""
import json
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tensorboard.backend.event_processing import event_accumulator

PKG = Path(r"F:\self_project\Sia-ai\GPT-SoVITS\GPT-SoVITS-v2pro-20261006")
TBROOT = PKG / "logs/maya/logs_s1_v2ProPlus/logs_s1_v2ProPlus"
TBROOT_FULL = PKG / "logs/maya_full/logs_s1_v2ProPlus/logs_s1_v2ProPlus"
GPT_W = PKG / "GPT_weights_v2ProPlus"
# 训练档案: 精选版 20ep / 全量版 8ep, tfevents mtime 最新的为活跃训练
RUNS = {
    "maya":      {"tb": TBROOT,      "total": 20, "ms": ["maya-e15", "maya-e20"],      "label": "精选版 1500条"},
    "maya_full": {"tb": TBROOT_FULL, "total": 8,  "ms": ["maya_full-e4", "maya_full-e8"], "label": "全量版 7453条"},
}
_cache = {"t": 0.0, "data": None}

# 全量管线阶段检测: 解析 chain_full_log 线性扫描最后状态 + 实时计数
ROOT = Path(r"F:\self_project\Sia-ai\GPT-SoVITS")
CHAIN_LOG = ROOT / "_training" / "chain_full_log.txt"
OPT_FULL = PKG / "logs/maya_full"
N_FULL = 7453
PHASE_TEXT = {
    "idle": "未运行",
    "text": "1-get-text 文本+BERT 特征提取中",
    "text_done": "1-get-text 完成",
    "hubert": "2-hubert-wav32k 音频特征提取中",
    "hubert_done": "2-hubert-wav32k 完成",
    "semantic": "3-get-semantic vq 语义码提取中(结束才落盘, 无中途计数)",
    "semantic_done": "预处理完成, 校验合并中",
    "train": "全量 GPT 训练运行中",
    "train_done": "全量训练完成 (maya_full-e8 已落盘)",
}


def pipe_stage():
    try:
        lines = CHAIN_LOG.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return {"phase": "idle", "text": PHASE_TEXT["idle"]}
    state = "idle"
    for l in lines:
        if "1-get-text 开始" in l:
            state = "text"
        elif "1-get-text 完成" in l:
            state = "text_done"
        elif "2-hubert-wav32k 开始" in l:
            state = "hubert"
        elif "2-hubert-wav32k 完成" in l:
            state = "hubert_done"
        elif "3-get-semantic 开始" in l:
            state = "semantic"
        elif "3-get-semantic 完成" in l:
            state = "semantic_done"
        elif "全量训练已启动" in l:
            state = "train"
    if state == "train" and (GPT_W / "maya_full-e8.ckpt").exists():
        state = "train_done"
    d = {"phase": state, "text": PHASE_TEXT[state]}
    if state in ("hubert", "semantic"):
        d["count"] = len(list((OPT_FULL / "4-cnhubert").glob("*.pt")))
        d["total"] = N_FULL
    return d


def active_run():
    """返回 (key, tb_dir): 谁的 tfevents 更新谁活跃; 都无则默认精选"""
    best = ("maya", TBROOT, 0.0)
    for k, cfg in RUNS.items():
        for p in cfg["tb"].glob("version_*/events*"):
            if p.stat().st_size > 0 and p.stat().st_mtime > best[2]:
                best = (k, cfg["tb"], p.stat().st_mtime)
    return best[0], best[1], best[2]


def gpu():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5).stdout.strip()
        u, m = out.split(",")
        return {"util": int(u), "mem": int(m)}
    except Exception:
        return {"util": 0, "mem": 0}


def read_tb(tb_parent):
    """读 tfevents -> epoch/loss/acc 曲线; 按 mtime 选最活跃的 events 文件.
    空训练存根 mtime 老, 断点续训的新文件体积虽小但 mtime 最新, 必须以 mtime 为准
    (按体积选会把续训小文件抢输给上一轮死亡的大文件, 页面就会显示尸体数据)"""
    evs = [p for p in tb_parent.glob("version_*/events*") if p.stat().st_size > 0]
    if not evs:
        return None
    f = max(evs, key=lambda p: p.stat().st_mtime)
    ea = event_accumulator.EventAccumulator(str(f), size_guidance={"scalars": 2000})
    ea.Reload()
    res = {"version": f.parent.name, "file_mtime": f.stat().st_mtime}
    for tag in ("epoch", "total_loss_step", "top_3_acc_step"):
        try:
            s = ea.Scalars(tag)
            res[tag] = [(e.step, e.value, e.wall_time) for e in s]
        except Exception:
            res[tag] = []
    return res


def snapshot():
    if _cache["data"] and time.time() - _cache["t"] < 4:
        return _cache["data"]
    run_key, _, _ = active_run()
    run = RUNS[run_key]
    total = run["total"]
    tb = read_tb(run["tb"])
    ep = tb and tb.get("epoch") or []
    cur_epoch = int(ep[-1][1]) if ep else -1          # tfevents epoch 最后值
    steps = [(s, v) for s, v, _ in (tb and tb.get("total_loss_step") or [])]
    acc = [(s, v) for s, v, _ in (tb and tb.get("top_3_acc_step") or [])]
    per_epoch = None
    # 真实单 epoch 用时: 取最近两次整数 epoch 跳变的 wall_time 差
    # (epoch 标量是按 step 采样的浮点值, 直接取相邻两点差得到的是秒级假速度)
    crossings = [e for i, e in enumerate(ep) if i and int(e[1]) > int(ep[i - 1][1])]
    if len(crossings) >= 2:
        per_epoch = crossings[-1][2] - crossings[-2][2]
    elif len(crossings) == 1:
        per_epoch = time.time() - crossings[-1][2]   # 续训首 epoch: 用当前 epoch 已进行时间兜底
    remaining = max(0, total - 1 - cur_epoch)
    eta = per_epoch * remaining if per_epoch and remaining > 0 else None
    ms = {m.stem: m.stat().st_mtime for m in GPT_W.glob("maya*.ckpt")}
    data = {
        "now": time.time(),
        "gpu": gpu(),
        "run_key": run_key,
        "run_label": run["label"],
        "milestone_keys": run["ms"],
        "version": tb and tb.get("version"),
        "tb_mtime": tb and tb.get("file_mtime"),
        "cur_epoch": cur_epoch,
        "running_epoch": cur_epoch + 1,
        "total": total,
        "per_epoch_sec": per_epoch,
        "eta_sec": eta,
        "loss": steps[-300:],
        "acc": acc[-300:],
        "milestones": ms,
        "steps": len(steps),
    }
    stage = pipe_stage()
    data["phase"] = stage["phase"]
    data["phase_text"] = stage["text"]
    if "count" in stage:
        data["phase_count"] = stage["count"]
        data["phase_total"] = stage["total"]
    _cache["t"] = time.time()
    _cache["data"] = data
    return data


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Maya GPT 训练监控</title>
<style>
body{margin:0;font-family:Consolas,'Microsoft YaHei',monospace;background:#0d1117;color:#e6edf3}
.wrap{max-width:880px;margin:0 auto;padding:24px}
h1{font-size:16px;color:#7ee787;margin:0 0 4px}
.sub{color:#8b949e;font-size:12px;margin-bottom:20px}
.big{font-size:44px;font-weight:700;color:#58a6ff}
.bar{height:22px;background:#21262d;border-radius:11px;overflow:hidden;margin:10px 0 24px}
.bar>div{height:100%;background:linear-gradient(90deg,#1f6feb,#7ee787);border-radius:11px;transition:width 1s}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px}
.k{font-size:11px;color:#8b949e}.v{font-size:20px;font-weight:600;margin-top:4px}
.ms{display:flex;gap:10px;margin-bottom:20px}
.pill{padding:6px 14px;border-radius:14px;background:#21262d;color:#8b949e;font-size:13px}
.pill.on{background:#1a3a1f;color:#7ee787;border:1px solid #2ea043}
.live{color:#7ee787}.dead{color:#f85149}
.pipe{display:flex;gap:8px;margin:0 0 10px}
.pstep{flex:1;text-align:center;padding:7px 2px;border-radius:6px;background:#21262d;color:#8b949e;font-size:12px;border:1px solid transparent}
.pstep.act{background:#0c2d6b;color:#79c0ff;border-color:#1f6feb}
.pstep.done{background:#1a3a1f;color:#7ee787}
svg{background:#161b22;border:1px solid #30363d;border-radius:8px;width:100%;height:120px}
</style></head><body><div class="wrap">
<h1>Maya GPT 训练监控 <span id="live" class="dead">●</span></h1>
<div class="sub" id="sub"></div>
<div class="pipe" id="pipe"></div>
<div class="k" id="ptext" style="margin:2px 0 8px"></div>
<div id="preUI" style="display:none">
<div class="big"><span id="pcnt">-</span><span style="font-size:20px;color:#8b949e"> <span id="ptotal"></span> <span id="plabel"></span></span></div>
<div class="bar"><div id="pbar" style="width:0%"></div></div>
</div>
<div id="trainUI">
<div class="big"><span id="ep">-</span><span style="font-size:20px;color:#8b949e"> / <span id="total">-</span> epoch<span id="epstate" style="color:#58a6ff"></span></span></div>
<div class="bar"><div id="bar" style="width:0%"></div></div>
<div class="grid">
<div class="card"><div class="k">进行中 epoch</div><div class="v" id="run">-</div></div>
<div class="card"><div class="k">速度 (分/epoch)</div><div class="v" id="speed">-</div></div>
<div class="card"><div class="k">GPU 利用率</div><div class="v" id="gpu">-</div></div>
<div class="card"><div class="k">显存</div><div class="v" id="mem">-</div></div>
</div>
<div class="ms" id="ms"></div>
</div>
<div class="k">loss (近300采样点)</div><svg id="los"></svg>
<div class="k" style="margin-top:10px">top-3 acc</div><svg id="acc"></svg>
</div><script>
function spark(id, pts, color){
  const el=document.getElementById(id); if(!pts||pts.length<2){el.innerHTML='';return;}
  const W=el.clientWidth,H=120,ys=pts.map(p=>p[1]);
  let mn=Math.min(...ys),mx=Math.max(...ys); if(mx-mn<1e-9)mx=mn+1e-9;
  const X=i=>i/(pts.length-1)*(W-10)+5, Y=v=>H-8-(v-mn)/(mx-mn)*(H-16);
  el.innerHTML='<polyline fill="none" stroke="'+color+'" stroke-width="1.5" points="'+
    pts.map((p,i)=>X(i)+','+Y(p[1])).join(' ')+'"/><text x="6" y="14" fill="#8b949e" font-size="11">'+
    mx.toFixed(2)+'</text><text x="6" y="'+(H-4)+'" fill="#8b949e" font-size="11">'+mn.toFixed(2)+'</text>';
}
const PH=['text','hubert','semantic','train'];
const PL={text:'1 文本+BERT',hubert:'2 hubert/wav32k',semantic:'3 semantic 提取',train:'4 全量 GPT 训练'};
const SIDX={idle:-1,text:0,text_done:.5,hubert:1,hubert_done:1.5,semantic:2,semantic_done:2.5,train:3,train_done:3.5};
function update(d){
  const live = d.gpu.util>20;
  document.getElementById('live').className=live?'live':'dead';
  // 管线四阶段条
  const cur = SIDX[d.phase]===undefined?-1:SIDX[d.phase];
  const pe=document.getElementById('pipe'), pkey='p'+d.phase;
  if(pe.dataset.k!==pkey){
    pe.dataset.k=pkey; pe.innerHTML='';
    PH.forEach((s,i)=>{
      const c=document.createElement('div'); c.className='pstep'; c.textContent=PL[s];
      if(cur>=i+1)c.classList.add('done'); else if(cur>=i)c.classList.add('act');
      pe.appendChild(c);
    });
  }
  document.getElementById('ptext').textContent=d.phase_text||'';
  const pre = d.phase && d.phase!=='train' && d.phase!=='train_done';
  document.getElementById('preUI').style.display=pre?'':'none';
  document.getElementById('trainUI').style.display=pre?'none':'';
  if(pre){
    const lb={text:'条文本',text_done:'条文本',hubert:'hubert 特征',hubert_done:'hubert 特征',semantic:'条特征就绪',semantic_done:'条特征就绪'}[d.phase]||'';
    document.getElementById('pcnt').textContent=d.phase_count!=null?d.phase_count.toLocaleString():'···';
    document.getElementById('ptotal').textContent=d.phase_total?'/ '+d.phase_total.toLocaleString():'';
    document.getElementById('plabel').textContent=lb;
    document.getElementById('pbar').style.width=(d.phase_count!=null&&d.phase_total)?(d.phase_count/d.phase_total*100)+'%':'0%';
    document.getElementById('sub').textContent='全量语音包管线 · GPU '+d.gpu.util+'% / '+d.gpu.mem+'MB · 更新于 '+new Date().toLocaleTimeString();
  }else{
    document.getElementById('total').textContent=d.total;
    document.getElementById('ep').textContent=Math.max(0,d.cur_epoch);
    document.getElementById('epstate').textContent=d.running_epoch<1?'（全部完成）':('（e'+d.running_epoch+' 训练中）');
    document.getElementById('bar').style.width=Math.min(100,d.cur_epoch/d.total*100)+'%';
    document.getElementById('run').textContent=d.running_epoch<1?'-':('e'+d.running_epoch);
    document.getElementById('speed').textContent=d.per_epoch_sec?(d.per_epoch_sec/60).toFixed(1):'-';
    // 里程碑 pills 随训练档案动态渲染
    const msEl=document.getElementById('ms');
    const want=d.milestone_keys.join('|');
    if(msEl.dataset.k!==want){
      msEl.dataset.k=want; msEl.innerHTML='';
      d.milestone_keys.forEach(k=>{
        const s=document.createElement('span');
        s.className='pill'+(d.milestones[k]?' on':'');
        s.textContent=k.includes('full')?('全量 '+k.split('-e')[1]):k.replace('maya-','');
        s.dataset.k=k; msEl.appendChild(s);
      });
    }
    [...msEl.children].forEach(s=>s.classList.toggle('on', !!d.milestones[s.dataset.k]));
    const eta=d.eta_sec?('约 '+Math.ceil(d.eta_sec/3600)+'h'+Math.round(d.eta_sec%3600/60)+'m 后完成'):'';
    const stale=d.tb_mtime&&d.tb_mtime<Date.now()/1000-600?' (tfevents '+Math.round((Date.now()/1000-d.tb_mtime)/60)+'min 未更新!)':'';
    document.getElementById('sub').textContent='['+d.run_label+'] '+d.version+' '+eta+stale+' 更新于 '+new Date().toLocaleTimeString();
  }
  document.getElementById('gpu').textContent=d.gpu.util+'%';
  document.getElementById('mem').textContent=d.gpu.mem+'MB';
  spark('los',d.loss,'#f0883e'); spark('acc',d.acc,'#7ee787');
}
// SSE: 后端数据变化时才推送, 前端零轮询
const es = new EventSource('/stream');
es.onmessage = e => update(JSON.parse(e.data));
es.onerror = () => document.getElementById('live').className='dead';
// 兜底: 首帧拉一次
fetch('/api').then(r=>r.json()).then(update).catch(()=>{});
</script></body></html>"""


class H(BaseHTTPRequestHandler):
    def _page(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.encode())

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        last = None
        try:
            while True:
                snap = snapshot()
                payload = json.dumps(snap, sort_keys=True)
                if payload != last:          # 数据有变化才推
                    last = payload
                    self.wfile.write(f"data: {payload}\n\n".encode())
                    self.wfile.flush()
                time.sleep(2)
        except (BrokenPipeError, ConnectionAbortedError, OSError):
            pass

    def do_GET(self):
        if self.path == "/api":
            b = json.dumps(snapshot()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
        elif self.path == "/stream":
            self._sse()
        else:
            self._page()

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", 9881), H).serve_forever()
