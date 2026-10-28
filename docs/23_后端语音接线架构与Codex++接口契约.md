# 23_后端语音接线架构与 Codex++ 接口契约

> 任务背景：把语音功能的**评测裁决**接进后端 `tts.py`，实现「双语音模式 + 好感度→声线映射」。
> 分工：**本文件作者（WorkBuddy）定架构并落地非推理层代码**；**推理调用层（连本地 GPT-SoVITS / RVC 模型的真实调用）由 Codex++ 实现**。
> 关联文档：`docs/19_语音方案评审与备选路线建议.md`、`docs/20_夜间自动管线与交接快照.md`、`docs/18_语音功能开发计划.md`。

---

## 0. 一句话结论（给 Codex++ 的 TL;DR）

后端已经支持「本地摩耶音色 + edge 降级」。你现在要写的只有一件事：**让 `GptSovitsBackend.synthesize()` 真的能连上本地 `api_v2` 服务并返回 mp3**。其余路由、好感度映射、ref 池结构、SVC 钩子都已就绪。在权重路径和 ref 池填满之前，服务会自动降级到 edge-tts，应用不会崩。

---

## 1. 架构总览

```
前端 /api/voice/tts (POST: text, voice?, intimacy_level?, lang?)
        │
        ▼
backend/app/api/routes/voice.py
        │  - 若未传 intimacy_level，从 DB(PersonalityState) 解析
        ▼
backend/app/services/tts.py :: text_to_speech(text, voice, intimacy_level, lang)
        │
        ├─ intimacy_to_tier(level)  →  LOW(1) / MID(2,3) / HIGH(4)
        ├─ pick_ref(tier, lang)     →  中文按档位池 / 日文按摩耶原声池
        ├─ _weights_for(lang)       →  (gpt_weight, sovits_weight)
        │
        ├─ [svc_enabled?]  → SvcBackend.synthesize()   ← 默认关闭
        ├─ [tts_backend=gpt_sovits?]  → GptSovitsBackend.synthesize()  ← Codex++ 实现
        └─ 任意失败/无 ref  → EdgeTtsBackend.synthesize()  (兜底，始终可用)
                                        │
                                        ▼
                              返回 mp3 字节 (media_type=audio/mpeg)
```

**设计裁决（已定，勿改）**：
- 中文模式 = **底模 GPT + 摩耶 SoVITS e3 + 中文 ref**（评测底模 CER 0.0328 全场最低）
- 日文模式 = **微调 GPT + 摩耶 SoVITS e3 + 摩耶原声 ref**（日文天然无洋腔）
- 好感度三档（低/中/高）→ 声线（高冷/活泼/甜妹），由 **ref 池 + 推理参数** 实现，**不训练三个独立模型**
- SVC 变声路线：音色 sim 裁决未出（训练被用户暂停），**默认关闭**，留钩子

---

## 2. 已实现（WorkBuddy 落地，已语法校验通过）

| 文件 | 改动 |
|---|---|
| `backend/app/services/tts.py` | 重写为双后端架构：枚举 `VoiceLang`/`VoiceTier`、`intimacy_to_tier()`、`RefSample`/`REF_POOLS`/`JA_REF_POOL` 结构、`TTSBackend` 协议、`EdgeTtsBackend`（保留可用）、`GptSovitsBackend`（桩+契约）、`SvcBackend`（桩）、`text_to_speech()` 路由+降级 |
| `backend/app/core/config.py` | 新增语音后端配置块：`tts_backend` / `gpt_sovits_api_url` / `sovits_weight` / `gpt_zh_weight` / `gpt_ja_weight` / `svc_enabled` |
| `backend/app/api/schemas.py` | `TTSRequest` 增加可选 `intimacy_level`(1-4)、`lang`(zh\|ja) |
| `backend/app/api/routes/voice.py` | 注入 `get_db`，未传 `intimacy_level` 时从 DB 解析；透传 `lang` |

> 注意：本机 `backend/.venv` 的 python 重定向到不存在的 `C:\Users\zhaoq\...`，**当前环境无法跑后端单测**。代码仅做了 `py_compile` 语法校验，运行期验证留给 Codex++ 或本地启动。

---

## 3. Codex++ 待实现：推理调用层契约

### 3.1 `GptSovitsBackend.synthesize()` 必须做什么

签名（**不要改签名**，路由依赖它）：
```python
def synthesize(self, *, text, lang, ref_audio, ref_text, gpt_weight, sovits_weight,
               speed=1.0, top_p=0.7, temperature=0.7) -> bytes:  # 返回 mp3 字节
```

执行步骤（参考 `docs/20` §api_v2 用法）：
1. 确保 `api_v2` 服务存活（GET 健康检查；未起则**抛异常**触发降级，不要静默返回空）。
2. 若 `gpt_weight` 非空：`POST /set_gpt_weights?weights_path=<gpt_weight>`。
3. 若 `sovits_weight` 非空：`POST /set_sovits_weights?weights_path=<sovits_weight>`。
4. `POST /tts` 发送 JSON。**字段名以实际 `api_v2.py` 为准**（包在 gitignored 的 `GPT-SoVITS/` 内），标准字段形如：
   ```json
   {
     "text": "<text>",
     "text_lang": "zh" | "ja",
     "ref_audio_path": "<ref_audio 绝对路径>",
     "ref_text": "<ref_text>",
     "ref_lang": "zh" | "ja",
     "top_p": 0.7, "temperature": 0.7, "speed": 1.0
   }
   ```
5. 取回音频（api_v2 通常返回 wav）→ **转 mp3**（`ffmpeg` 路径见 `settings.ffmpeg_path`）→ 返回 mp3 字节。
6. 任何异常向上抛，路由会自动降级 edge。

### 3.2 你要填的「真模型路径」（来自 gitignored 的本地目录）

| 配置项 (`config.py`) | 指向 | 现状 |
|---|---|---|
| `sovits_weight` | `GPT-SoVITS/logs/maya_e3.pth`（定型 SoVITS） | **TODO 填绝对路径** |
| `gpt_zh_weight` | 中文底模 GPT：通常**留空**（用 api_v2 默认加载的底模） | 留空即可 |
| `gpt_ja_weight` | 日文微调 GPT：`GPT-SoVITS/GPT_weights_v2ProPlus/maya_full-e16`（或 sel_e20 精选） | **TODO 填绝对路径** |

> api_v2 启动命令（`docs/20`）：`runtime\python.exe api_v2.py -a 127.0.0.1 -p 9880 -c GPT_SoVITS/configs/tts_infer.yaml`（cwd=GPT-SoVITS 包根）。`/set_gpt_weights` 与 `/set_sovits_weights` 支持热切换，是做对照实验的关键。

### 3.3 你要填的「ref 池」（`REF_POOLS` / `JA_REF_POOL` in `tts.py`）

- `REF_POOLS[LOW/MID/HIGH]`：中文模式每档 3~5 条摩耶「该时期」原声（对应高冷/活泼/甜妹）。
  原声来源：`GPT-SoVITS/_training/wav/`（摩耶 7453 条）；中文 ref 的 `text` 需是**中文朗读稿**（不是日文）。
- `JA_REF_POOL`：日文模式固定用摩耶原声，如 `z6005`（后日谈）/ `z3007`（g线），`text` 填对应日文。
- 每条是 `RefSample(audio="绝对路径", text="...")`。
- `pick_ref()` 当前取池内首条；可自行改为按 `hash(text)` 或随机，保证同一句稳定选同一条。

### 3.4 你要实现的 `SvcBackend`（可选，待 SVC 裁决）

仅当 SVC 训练完成且音色 sim **超过 TTS 路线的 0.712** 时才做。实现同契约（连 RVC 推理），并把 `config.svc_enabled=True`。在那之前保持 `NotImplementedError`，路由不会走到它。

---

## 4. 好感度 → 声线档位 → ref 池 映射

| `intimacy_level` (DB) | `VoiceTier` | 声线情绪 | 对应语音文档档位 | ref 池 |
|---|---|---|---|---|
| 1（陌生人） | LOW | 高冷/疏离 | 共通线高冷声线 → 低好感 | `REF_POOLS[LOW]` |
| 2（朋友） | MID | 活泼 | g线活泼 → 中 | `REF_POOLS[MID]` |
| 3（依赖者/姐姐） | MID | 活泼 | g线活泼 → 中 | `REF_POOLS[MID]` |
| 4（恋人） | HIGH | 甜妹 | 后日谈甜妹 → 高 | `REF_POOLS[HIGH]` |

> 这是把语音文档的「共通线/g线/后日谈」三档桥接到 app 实际四档亲密度的映射，集中在 `intimacy_to_tier()`，如需调整只改这一处。

---

## 5. 关键决策索引（必读，避免推倒重来）

- **`docs/19`**：语音方案评审。核心异议——反对 7453 条全量灌入；指出「日语腔是结构性的，堆训练量反而恶化」（已被评测坐实）。
- **`docs/20`**：夜间管线交接快照 + **评测裁决**。
  - 评测报告 A：`GPT-SoVITS/_audition/gate/report_1028_1949.json`（六档 × 20 句）。
  - 裁决数据（中文模式定型依据）：

    | 档位 | CER↓ | 音色sim↑ | 尾首能量 |
    |---|---|---|---|
    | base_gpt（底模） | **0.0328** | 0.712 | 0.81 |
    | sel_e20 | 0.0328 | 0.707 | 0.91 |
    | full_e8 | 0.0391 | 0.700 | 0.89 |
    | full_e12 | 0.0481 | 0.705 | 0.88 |
    | full_e16 | 0.0792 | 0.688 | 0.73 |
    | sel_e20_mr（摩耶原声ref） | 0.1621 | **0.805** | 0.83 |

  - **CER 随全量 epoch 单调递增**（0.039→0.048→0.079）→ 坐实「微调越久中文越差」，中文用底模。
  - 摩耶原声 ref 音色 sim 最高(0.805)但 CER 崩(0.162) → **仅日文模式用**。
  - 尾首能量比 0.73~0.91 全过 0.6 门禁 → 「后半句发软无力」在 TTS 路线已解决。
- **`docs/18`**：语音功能开发计划（含已回填的坑 33/34/35：RVC 链三处断点）。

---

## 6. 测试计划（Codex++ 实现后跑）

1. **单元**：`intimacy_to_tier(1/2/3/4)` 映射正确；`text_to_speech` 在 ref 池为空 / 权重为空时**不崩**，降级 edge。
2. **集成**：起 `api_v2` + 填权重/ref 后，对**固定 5 句测试集**（陈述/疑问/撒娇/长句/短句）逐句合成，人工盲听定档。
3. **三道门禁**（沿用 `docs/18`）：文本 CER 阈值 + 能量曲线（专治「发软」）+ 说话人相似度余弦。至少复现报告 A 的 0.712 基线。
4. **好感度联动**：用 DB 把 `intimacy_level` 切到 1/3/4，确认取到的 ref 池不同。
5. **SVC 对照**（若做）：SVC 20 句 sim 与 TTS 0.712 对比，决定是否启用。

---

## 7. Open Variables / 风险

- **SVC 裁决悬而未决**：RVC 训练被用户暂停，`RVC/pkg/.../logs/maya_svc/` 权重未出。SVC 路线暂不启用。
- **ref 池为空**：在 Codex++ 填满前，本地后端会因 `pick_ref()` 返 None 而直接降级 edge（符合预期）。
- **api_v2 字段名需核对**：`/tts` 的精确 JSON 字段以实际 `api_v2.py` 为准（包在 gitignored 目录），不要 blindly 信任第 3.1 节的示例。
- **venv 损坏**：本机 `backend/.venv` 的 python 重定向到 `C:\Users\zhaoq\...`（不存在），需在正确环境重新建 venv 或修复后才能跑后端。
- **音频格式**：路由 `media_type=audio/mpeg` 固定，推理层务必返回 mp3（wav 需转码）。
