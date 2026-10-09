# 03 API 文档（希亚 AI 女友 · FastAPI 后端）

> 与 `backend/app/api/routes/` 下 5 个路由文件逐一对应，共 **14 个接口**，一个不多一个不少。
> Base URL：`http://127.0.0.1:8900`（API_HOST / API_PORT 可在 .env 覆盖）。

## 0. 通用约定

- 数据格式：请求/响应均为 `application/json`，UTF-8；唯一例外是 TTS 返回 `audio/mpeg` 二进制流；
- 无鉴权：本机服务，CORS 默认放行 `http://localhost:5173`、`http://127.0.0.1:5173`；
- 参数校验失败返回 FastAPI 默认 **422**：`{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}`；
- 未捕获异常统一返回 **500** `{"detail": "服务器内部错误"}`（main.py 兜底 handler，异常记录到 `data/logs/xia.log`）；
- 框架内置交互文档：`/docs`（Swagger UI）、`/openapi.json`（非业务接口，不计入下表）。

### 接口总览

| # | 方法 | 路径 | 说明 |
|---|------|------|------|
| 1 | POST | /api/chat | 发送消息，走完整对话流水线 |
| 2 | GET | /api/chat/context | 前端初始化上下文（欢迎语/生日/雷雨/好感度/通知标志） |
| 3 | GET | /api/chat/history | 最近对话消息 |
| 4 | DELETE | /api/chat/history | 清空全部聊天记录 |
| 5 | GET | /api/chat/search | 按日期区间 + 关键词搜索对话轮次 |
| 6 | GET | /api/chat/diary/{date_str} | 情绪日记 |
| 7 | GET | /api/memories | 全部长期记忆 |
| 8 | POST | /api/memories | 手动写入一条记忆 |
| 9 | GET | /api/persona | 画像 + 人格状态 + 目标列表 |
| 10 | PUT | /api/persona | 编辑用户画像（传了才改） |
| 11 | POST | /api/persona/reset-affinity | 重置好感度 |
| 12 | POST | /api/voice/tts | 文本 → mp3 音频流 |
| 13 | POST | /api/voice/stt | webm 录音 base64 → 识别文本 |
| 14 | GET | /api/health | 服务与 LLM 通道状态 |

---

## 1. 对话 /api/chat（routes/chat.py）

### 1.1 发送消息

`POST /api/chat`

请求体（`ChatRequest`）：

| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| text | string | 是 | 1 ≤ 长度 ≤ 2000 | 用户消息（strip 后为空返回 400） |
| enable_critique | boolean | 否 | 默认 `true` | 是否启用人格自检 |

响应 `200`（`ChatReply`）：

```json
{
  "reply": "哼，又熬夜！准点睡觉，听到没？",
  "emotion": "疲惫",
  "saved_memory": "用户最近经常加班到深夜",
  "state": {
    "trust": 12,
    "intimacy_level": 1,
    "intimacy_label": "陌生人"
  }
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| reply | string | 希亚的回复（已过守卫链） |
| emotion | string | 本轮检测的用户情绪（≤4 字标签） |
| saved_memory | string \| null | 本轮沉淀的记忆事实，未沉淀为 null |
| state | object | trust / intimacy_level / intimacy_label |

错误：

| 状态码 | 场景 | 示例 |
|--------|------|------|
| 400 | 消息 strip 后为空 | `{"detail": "消息不能为空"}` |
| 422 | 请求体校验失败（text 为空/超 2000 字等） | FastAPI 默认格式 |
| 502 | LLM 通道调用失败 | `{"detail": "Ollama 调用失败: ..."}` / `{"detail": "在线通道 HTTP 401: ..."}` |

```bash
curl -X POST http://127.0.0.1:8900/api/chat \
  -H "Content-Type: application/json" \
  -d '{"text": "今天加班到好晚，好累啊", "enable_critique": true}'
```

### 1.2 获取初始化上下文

`GET /api/chat/context`

无参数。响应 `200`：

```json
{
  "welcome": "……哈？谁准你直接叫我的名字——希亚了？\n我可不是那种随叫随到的AI宠物!\n想让我开口？先证明你配得上我的attention吧。\n（…喂，至少先报上名字啊！）",
  "user_name": "小叶",
  "user_birthday": "04-06",
  "days_to_birthday": 179,
  "is_birthday": false,
  "is_thunderstorm": false,
  "is_night": true,
  "notify_birthday_eve": false,
  "notify_thunder": false,
  "notify_idle": false,
  "state": {
    "trust": 0,
    "intimacy_level": 1,
    "intimacy_label": "陌生人",
    "tip": "……哼，连名字都没报全，也配看我的好感度？"
  }
}
```

| 字段 | 说明 |
|------|------|
| welcome | 欢迎语（仅无聊天历史时非空；按 生日 > 雷雨深夜 > 雷雨 > 生日前 2/1 天 > 亲密度分档 选择） |
| user_name / user_birthday / days_to_birthday / is_birthday | 用户画像与生日倒计时（支持跨年） |
| is_thunderstorm / is_night | 和风天气雷雨判定 / 深夜判定（22:00~6:00） |
| notify_birthday_eve / notify_thunder / notify_idle | 前端桌面通知标志：生日前夜（剩 1 天）/ 雷雨 / 超 24 小时未聊 |
| state | trust / intimacy_level / intimacy_label / tip（好感度面板傲娇贴士） |

```bash
curl http://127.0.0.1:8900/api/chat/context
```

### 1.3 获取历史消息

`GET /api/chat/history`

Query 参数：

| 参数 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| limit | int | 否 | 默认 100，1 ≤ limit ≤ 500 | 返回条数上限 |

响应 `200`（数组，按时间正序）：

```json
[
  {
    "role": "user",
    "content": "晚安，我去睡了",
    "emotion": "困",
    "time": "2026-10-09T23:41:12.345678"
  },
  {
    "role": "assistant",
    "content": "哼，早点睡……梦里见。",
    "emotion": null,
    "time": "2026-10-09T23:41:15.123456"
  }
]
```

> `emotion` 仅 user 消息有值，assistant 消息为 `null`。

```bash
curl "http://127.0.0.1:8900/api/chat/history?limit=50"
```

### 1.4 清空聊天记录

`DELETE /api/chat/history`

无参数。响应 `200`：

```json
{"ok": true}
```

> 仅清空 messages 表；人格状态与长期记忆保留（V13 调试按钮）。

```bash
curl -X DELETE http://127.0.0.1:8900/api/chat/history
```

### 1.5 搜索对话

`GET /api/chat/search`

Query 参数：

| 参数 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| start | string | 是 | `YYYY-MM-DD` | 开始日期 |
| end | string | 是 | `YYYY-MM-DD` | 结束日期 |
| q | string | 否 | 默认 `""` | 关键词（匹配用户消息，不区分大小写） |

响应 `200`（数组，最新在前；user 与下一条 assistant 成对）：

```json
[
  {
    "time": "10-09 23:41",
    "user": "晚安，我去睡了",
    "assistant": "哼，早点睡……梦里见。"
  }
]
```

错误：`400` `{"detail": "日期格式应为 YYYY-MM-DD"}`。

```bash
curl "http://127.0.0.1:8900/api/chat/search?start=2026-10-01&end=2026-10-09&q=晚安"
```

### 1.6 情绪日记

`GET /api/chat/diary/{date_str}`

路径参数：`date_str` —— 日期，`YYYY-MM-DD` 格式（格式错误返回 `400` `{"detail": "日期格式应为 YYYY-MM-DD"}`）。

响应 `200`，当日无日志：

```json
{
  "date": "2026-10-09",
  "empty": true,
  "text": "🌙 今天还没有和我说话呢～等你来聊❤️"
}
```

响应 `200`，当日有日志：

```json
{
  "date": "2026-10-09",
  "empty": false,
  "main_emotion": "疲惫",
  "emotion_sequence": "🥱 → 🙂 → 😪",
  "keywords": ["工作", "累", "困"],
  "memories": ["用户最近经常加班到深夜"],
  "night_count": 2
}
```

| 字段 | 说明 |
|------|------|
| main_emotion | 当日出现次数最多的情绪 |
| emotion_sequence | 情绪 emoji 流（EMOTION_EMOJI_MAP） |
| keywords | 命中的常见话题关键词 |
| memories | 当日 `saved_memory` 事实列表（Bug#1 修复后不再恒为空） |
| night_count | 深夜对话次数 |

```bash
curl http://127.0.0.1:8900/api/chat/diary/2026-10-09
```

---

## 2. 记忆 /api/memories（routes/memory.py）

### 2.1 查看全部记忆

`GET /api/memories`

无参数。响应 `200`：

```json
{
  "count": 2,
  "items": ["用户喜欢深夜写代码", "用户害怕打雷"]
}
```

```bash
curl http://127.0.0.1:8900/api/memories
```

### 2.2 手动写入记忆

`POST /api/memories`

请求体（`MemoryCreate`）：

| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| text | string | 是 | 1 ≤ 长度 ≤ 200 | 记忆内容（strip 后入库） |

响应 `200`：

```json
{"ok": true, "id": "mem_3"}
```

> `id` 为 chroma 文档 id（`mem_{计数+1}`）。错误：`422` 校验失败。

```bash
curl -X POST http://127.0.0.1:8900/api/memories \
  -H "Content-Type: application/json" \
  -d '{"text": "用户最喜欢的乐队是五月天"}'
```

---

## 3. 人设 /api/persona（routes/persona.py）

### 3.1 获取画像与状态

`GET /api/persona`

无参数。响应 `200`：

```json
{
  "profile": {
    "name": "小叶",
    "birthday": "04-06",
    "likes": ["晴天", "深夜写代码"],
    "dislikes": ["咖啡", "打雷"],
    "fears": ["孤独", "项目失败"],
    "recent_events": ["项目压力大", "失眠"]
  },
  "state": {
    "trust": 35,
    "intimacy_level": 2,
    "intimacy_label": "朋友",
    "tip": "勉强算你及格啦～再努努力？"
  },
  "goals": [
    {
      "id": "reduce_stress_weekly",
      "description": "本周帮小叶减压",
      "status": "inactive",
      "cooldown_days": 2,
      "last_triggered": null
    },
    {
      "id": "encourage_sleep",
      "description": "提醒小叶规律作息",
      "status": "active",
      "cooldown_days": 1,
      "last_triggered": "2026-10-09T23:41:15.123456"
    }
  ]
}
```

> profile 的 likes/dislikes/fears/recent_events 已拆分为数组；goals.status 为 `inactive` / `active` / `completed`。

```bash
curl http://127.0.0.1:8900/api/persona
```

### 3.2 编辑用户画像

`PUT /api/persona`

请求体（`ProfileUpdate`，**全字段可选，传了才改**）：

| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| name | string | 否 | ≤ 64 字符 | 用户名字 |
| birthday | string | 否 | 正则 `^\d{2}-\d{2}$` | 生日 `MM-DD` |
| likes | string | 否 | — | 喜欢，逗号分隔 |
| dislikes | string | 否 | — | 讨厌，逗号分隔 |
| fears | string | 否 | — | 害怕，逗号分隔 |
| recent_events | string | 否 | — | 近况，逗号分隔 |

响应 `200`（返回更新后的画像，数组格式）：

```json
{
  "ok": true,
  "profile": {
    "name": "小叶",
    "birthday": "04-06",
    "likes": ["晴天", "深夜写代码", "火锅"],
    "dislikes": ["咖啡", "打雷"],
    "fears": ["孤独", "项目失败"],
    "recent_events": ["项目压力大", "失眠"]
  }
}
```

错误：`422` 校验失败（如 birthday 不符合 `MM-DD` 格式）。

```bash
curl -X PUT http://127.0.0.1:8900/api/persona \
  -H "Content-Type: application/json" \
  -d '{"likes": "晴天,深夜写代码,火锅"}'
```

### 3.3 重置好感度

`POST /api/persona/reset-affinity`

无参数。响应 `200`：

```json
{"ok": true}
```

> trust 归 0、intimacy_level 归 1（V13 调试按钮保留）。

```bash
curl -X POST http://127.0.0.1:8900/api/persona/reset-affinity
```

---

## 4. 语音 /api/voice（routes/voice.py）

### 4.1 文本转语音（TTS）

`POST /api/voice/tts`

请求体（`TTSRequest`）：

| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| text | string | 是 | 1 ≤ 长度 ≤ 1000 | 待合成文本 |
| voice | string | 否 | — | edge-tts 音色名，缺省用配置 `TTS_VOICE`（zh-CN-XiaoyiNeural） |

响应 `200`：**`audio/mpeg` 二进制音频流**（mp3），前端直接 `<audio>` 播放或下载。

错误：

| 状态码 | 场景 | 示例 |
|--------|------|------|
| 422 | 请求体校验失败 | FastAPI 默认格式 |
| 502 | 合成失败 | `{"detail": "TTS 合成失败: ..."}` |

```bash
curl -X POST http://127.0.0.1:8900/api/voice/tts \
  -H "Content-Type: application/json" \
  -d '{"text": "哼，才不是特意给你念的呢！"}' \
  -o out.mp3
```

### 4.2 语音转文本（STT）

`POST /api/voice/stt`

请求体（`STTRequest`）：

| 字段 | 类型 | 必填 | 校验 | 说明 |
|------|------|------|------|------|
| audio | string | 是 | 长度 ≥ 8 | webm 录音的 base64 编码 |

服务端流程：base64 解码 → ffmpeg 转 16kHz 单声道 WAV → Vosk 本地识别。

响应 `200`：

```json
{"text": "今天好累啊"}
```

错误：

| 状态码 | 场景 | 示例 |
|--------|------|------|
| 422 | 请求体校验失败，或未能识别到有效语音 | `{"detail": "未能识别到有效语音"}` |

```bash
curl -X POST http://127.0.0.1:8900/api/voice/stt \
  -H "Content-Type: application/json" \
  -d "{\"audio\": \"$(base64 -w 0 recording.webm)\"}"
```

---

## 5. 健康检查 /api/health（routes/health.py）

`GET /api/health`

无参数。响应 `200`：

```json
{
  "status": "ok",
  "llm": {
    "channel": "auto",
    "active_provider": "local",
    "local_model": "qwen3.5:4b"
  }
}
```

| 字段 | 说明 |
|------|------|
| status | 恒为 `ok`（服务可达即可用） |
| llm.channel | 配置的通道模式：auto / local / online |
| llm.active_provider | 本次实际选用的 Provider：local / online / mock |
| llm.local_model | 配置的本地模型名 |

```bash
curl http://127.0.0.1:8900/api/health
```

---

## 6. 错误码汇总

| 状态码 | 含义 | 出现接口 |
|--------|------|---------|
| 400 | 业务校验失败：消息 strip 后为空 / 日期格式不是 YYYY-MM-DD | POST /api/chat、GET /api/chat/search、GET /api/chat/diary/{date_str} |
| 404 | 路径不存在（FastAPI 默认） | 全部 |
| 405 | 方法不允许（FastAPI 默认） | 全部 |
| 422 | Pydantic 参数校验失败（FastAPI 默认 detail 为数组）；STT 另有自定义 422「未能识别到有效语音」 | 所有带请求体/校验参数的接口 |
| 500 | 未处理异常，统一返回 `{"detail": "服务器内部错误"}` | 全部（main.py 兜底） |
| 502 | 上游调用失败：LLMError（LLM 通道） / TTS 合成失败 | POST /api/chat、POST /api/voice/tts |

> Windows 下 curl 请使用 `curl.exe`（PowerShell 的 `curl` 是 Invoke-WebRequest 别名），多行 `\` 需改为反引号或写成单行。
