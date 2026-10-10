# Live2D 升级调研报告 + 实施待办清单

> 调研日期：2026-10-10。调研背景：当前前端立绘是写实立绘（`frontend/src/components/stage/StageSprite.vue` + `frontend/src/utils/emotionAnim.ts`，切图 + CSS transform），用户不满意，要升级为真 Live2D（情绪/口型实时驱动）。
> 本文档同时是 workbuddy 接手用的交接待办清单。

## 一、Web 端 Live2D 渲染库

- **guansss/pixi-live2d-display**：~1.5k star，MIT，支持 Cubism 2/3/4（不含 5），2024-08 后停更。但生态有活跃分支：
  - **@jannchie/pixi-live2d-display**：内置 `model.speak(audio)` 自动口型同步 + 麦克风口型，最贴合 edge-tts 音频驱动方案
  - **@naari3/pixi-live2d-display**：支持 Cubism 5
  - **@laplace.live/pixijs-live2d**：PixiJS v8 续作，Cubism 5，弃 Cubism 2
  - **pixi-live2d-display-lipsyncpatch**（RaSan147）：口型补丁，Open-LLM-VTuber 旧版曾用
- **stevenjoezhang/live2d-widget**：~11k star，GPL-3.0（有传染性），仍在维护，但只是"看板娘"挂件，Cubism 2 为主，无情绪/口型深度驱动 → **不适合本项目**
- **oh-my-live2d**（已改名 **l2d-widget**）：支持 model2/3/4，MIT，活跃度待确认
- **官方 Cubism SDK for Web 许可**：专有许可，**一般用户/小规模企业（年营收 < 1000 万日元，约 50 万人民币）可免费商用发布**；示例模型对一般用户/小企业免费商用（初音 Miku、Unity-chan 除外）

## 二、带真 Live2D 的开源 AI 伴侣项目（可借鉴）

| 项目 | Star | 技术栈 | Live2D 驱动方式 | 许可证 |
|---|---|---|---|---|
| **Open-LLM-VTuber** | ~14k | React+Electron+Vite / Python 后端 | WebSocket 下发情绪/动作指令 + 音频流；v1.2.0 起改用官方 Cubism SDK（Cubism 5）；情绪标签切 expression/motion + TTS 音频驱动口型 | MIT（示例模型除外） |
| **moeru-ai/airi** | ~50k | **Vue 3 + Vite + TS**，Live2D + VRM 双支持 | Live2D 动作控制、auto-blink/auto-lookAt/idle 眼动、实时语音 | MIT |
| **SillyTavern** | ~34k | 原生 JS | Live2D 扩展：classify 表情识别 → 映射 expression/motion；talkinghead 扩展可用单张静态图生成类 Live2D 动作 + 任意 TTS 口型 | AGPL-3.0 |
| **Moemate** | — | 闭源商业产品（GitHub 上 moemateio 已 404），只可借鉴产品形态 | — | 闭源 |
| **xiaozhi-esp32** | ~25k | ESP32 硬件语音对话 | 无 Live2D 渲染，参考价值低 | MIT |

**借鉴结论**：
- **airi** 与本项目技术栈最贴近（同为 Vue 3），其 stage-ui 的 Live2D 组件封装可直接参考
- **Open-LLM-VTuber** 的协议设计最成熟："LLM 输出携带情绪标签 → 后端解析 → 随音频下发 WebSocket 指令"

## 三、Live2D 模型资源

- **官方免费示例数据集**（Hiyori、Haru、Mao、Shizuku 等）：一般用户/小企业可免费商用（Miku、Unity-chan 除外）
- **nizima**（官方市场）、**BOOTH**：大量免费/付费模型，逐个看授权
- **"红发白发异色瞳"专属模型**（对应希亚设定）：
  1. 委托：米画师/哔哩哔哩工房，基础皮套约 2000–3000 元起，商用权需写进合同
  2. 自建：Cubism Editor（免费版可用，PRO 付费）手工绑骨
- **ComfyUI 可参与环节**：立绘生成（SDXL/Illustrious 系）→ 分割/inpainting 补全遮挡 → See-through 类工具把单图自动切分为分层 PSD；但网格化+变形器+参数绑骨仍需 Cubism Editor 手工完成，全自动管线（waifuai 等）尚属实验性

## 四、推荐集成路线（调研结论）

**pixi-live2d-display 系（首选 @jannchie fork）+ LLM 输出情绪标签切 expression/motion + edge-tts 音频经 `model.speak()` 驱动口型**；模型先用官方免费示例（如 Mao/Hiyori），后期 ComfyUI 生成立绘 → 自动分层 PSD → 委托绑骨成专属红发白发模型。

---

## 五、实施待办清单（按此顺序执行）

1. **技术验证 ✅（2026-10-10 已完成）**
   - 已安装 `@jannchie/pixi-live2d-display@1.4.0` + `pixi.js@^8`（⚠️ 纠偏：该 fork 1.4.0 的 peer 依赖实际要求 PixiJS **v8**，本文档早前写的 v7 已过时）
   - ⚠️ 坑：必须从 `@jannchie/pixi-live2d-display/cubism4` 子路径导入，主入口（index）会在初始化时强制检查 Cubism 2 runtime（live2d.min.js）导致路由崩溃
   - 模型：官方示例 Haru（Cubism 3，Free Material License，一般用户/小企业可商用）已放 `frontend/public/live2d/haru/`；Cubism Core 5.1 在 `frontend/public/live2d/live2dcubismcore.min.js`（index.html 引入）
   - 组件：`frontend/src/components/stage/Live2dStage.vue`（pixi 8 异步 init + `Live2DModel.from(url, { ticker, autoHitTest: false, autoFocus: false })` + 等比缩放贴底居中；（`autoFocus` 于 2026-10-11 由 `true` 改为 `false` 自接管，见下方补记）），StageView 里用 HUD 🎭 按钮与写实立绘互切
   - 验证结果：渲染 ✓ / auto-blink 眨眼 ✓（ParamEyeLOpen 采样抓到 1→0.0017→1）/ 点击 ✓（**2026-10-10 复测纠偏**）
   - ⚠️ 点击纠偏记录（接手者必读）：早前记录的"点击触发 tap motion ✓"是**假阳性**——Haru 的 `Idle` 组含 3 条 motion（idle/m07/m15）会轮流播，姿态变化被误读成点击响应，实际 `pointertap` 从未收到。根因两条：①`autoHitTest` 依赖 PixiJS v8 的 `pointertap` 命中路由，实测收不到（而同源的 `globalpointermove` 视线跟随正常，故表现为"视线跟随正常但点击无反应"）；②库的 `tap()` 只 `emit('hit')`、**不会自己播动作**，即使命中也没有可见反应。
   - 修复方案（已验证）：改为监听 canvas 原生 `pointerup` → 换算画布内坐标 → `model.tap(x, y)`（绕开 PixiJS 命中路由），并在 `hit` 回调里显式 `void model.motion('Tap')`。
   - 实测证据：点击 → 状态徽标变「点击命中：Head」→ `motionManager.state.currentGroup` 由 `Idle` 变 `Tap` → 姿态变化；控制台无非 200 请求（Haru 的 Tap 音效 `../shizuku/sounds/flickHead_*.mp3` 已补齐到 `frontend/public/live2d/shizuku/sounds/`，缺它只会 warn、不阻断动作）
   - **2026-10-11 补记（三项修复，接手者必读）**
     - **① 待机动作轮播修复**：Haru 的 `Idle` 组原先含 `haru_g_idle`/`haru_g_m07`/`haru_g_m15` 三条；库源码里 `setIsLoop()` 从未被调用 → 动作 JSON 中的 `Loop: true` 被忽略，每条播完即结束，随后 `startRandomMotion(Idle)` 随机再挑一条 → 表现为待机时姿态"换人式"跳变。修复：改 `frontend/public/live2d/haru/haru_greeter_t03.model3.json`，`Idle` 组只保留**首尾均回归中立姿势**的 `haru_g_idle` 单条（配合 2s 淡入无缝循环）；`haru_g_m07`/`m15` 文件保留在仓库，留作后续情绪动作复用（可挂到独立 `Gesture` 组）。
     - **② 视线左右不对称修复**：根因两条 —— 库自带映射 `resolveFocusTargetFromWorld` 先做 `坐标/宽*2-1` 再取 `atan2` 单位向量（大小恒为 1 且带固定偏移），手感上呈"左转得多、右几乎不转"；叠加待机/点击动作里烘焙的 `ParamAngleX/Y/Z` 会与聚焦控制器叠加。修复（`Live2dStage.vue`）：`autoFocus: false` 改为自接管 `onPointerMove` —— 以模型屏幕中心为原点把指针位置归一化到 `[-1,1]`（`clampNorm`），天然左右对称，再调 `focusController.focus(nx, ny)`；并用 `muteHeadCurves`/`muteAllHeadCurves` 把动作曲线里的 `ParamAngleX/Y/Z` 改名成 `__muted__*`（动作应用时 `getParameterIndex == -1` 会跳过该曲线），把朝向完全交给聚焦控制器。
     - **③ WebGL 上下文静默丢失兜底**：内嵌 webview 在被遮挡/切走时会"静默"回收 GPU 上下文却不派发 `webglcontextlost`（实测表现：模型加载成功过——徽标曾显示"点击命中：Body"——之后画布变空白）。兜底：每 3s 轮询 `gl.isContextLost()` + 防抖 1.5s 重建 + 最多重试 3 次，60s 内超 3 次则提示手动 F5；另在 `webglcontextlost` 事件与 `visibilitychange`（回前台）各补一道检查。
     - 说明：②的**运行期左右对称验证**因内嵌浏览器持续丢上下文，未能自动完成（代码层逻辑已审、`npm run type-check` 通过、HMR 无编译错误）；曾临时加过左下角数值读数（鼠标 `nx/ny` + `ParamAngleX/Y/ParamEyeBallX`）供日常观察——**该临时读数连同调试句柄已于 ⑤ 一并移除**。
     - **④ 容器尺寸变化导致"人物消失"修复**（2026-10-11，接手者必读）：现象＝"只有人物没了、HUD/对话框还在、F5 才恢复"。根因：Pixi 的 `ResizePlugin` **只监听 `window.resize`、不监听容器自身尺寸**（见 `pixi.js/lib/app/ResizePlugin.js`）；容器一旦被压成 0（面板显隐/布局切换），renderer 停在 0×0，而旧 `fitModel()` 在 `app.screen` 为 0 时会把 `model.scale` 算成 0 → 人物永久不可见（WebGL 上下文没丢，故 HUD 仍在，也恰好解释了"刷新就好"）。修复（`Live2dStage.vue`）：①`fitModel()` 加防御——`screen.width/height < 1` 直接 return，杜绝 scale=0；②新增 `syncSize()`，读宿主 `clientWidth/Height`，与 `app.screen` 不一致时 `app.renderer.resize()` 再 `fitModel()`；③用 `ResizeObserver` 监听宿主容器（面板显隐/布局切换时即使无 window resize 也能自愈）；④3s 健康轮询里顺带 `syncSize()` 兜底；⑤`destroyStage()` 断开 observer。实测：折叠容器→人物消失（复现用户现象）→恢复容器且**不触发** window resize→模型自动恢复（修复前此态必须 F5）。
     - **⑤ 临时验证 UI 已清理**（2026-10-11）：移除左上角状态徽标 `.live2d-status`、左下角视线读数 `.live2d-debug`、右上角表情预览条 `.live2d-exprs`（含 `EXPRESSION_PREVIEW`/`previewExpression`/`followMood`），以及调试句柄 `window.__siaLive2d` 与 `window.__siaDiag`（`diag` 改为模块内局部常量，仅服务防抖重建）。原先搭在徽标上的恢复/加载失败提示改为 `console.warn/error`；`Live2dStage.vue` 模板现仅剩 canvas 容器。
     - **⑥ "人物又没了"静默失效修复**（2026-10-11，与 ④ 是两种不同病根，接手者必读）：④ 修的是"容器被压成 0 → scale=0"（尺寸问题）；本题是**渲染静默失效**——用户再报"人物没了"。实测取证（用调试探针读 `setupState`）：模型对象仍在场景里、`visible=true`、`scale=0.227`、`gl.isContextLost()===false`、`app.ticker` 正常跑（~120fps）、画布/渲染器尺寸都正常，**但 `gl.getError()` 持续返回 `1282`（INVALID_OPERATION）、`internalModel` 纹理为空、画面整片空白**；且组件的 `diag.ctxLost` 为空 → **没有 `webglcontextlost` 事件、没有重建**（即 `isContextLost()` 探测不到）。根因：内嵌 webview / HMR 反复重建被浏览器回收了 GPU 资源（Cubism 纹理/缓冲失效），上下文既没"lost"、事件也收不到，于是每帧 draw 都失败但 JS 侧一切"正常"。**修复（`Live2dStage.vue`）**：新增 `getGlError()`（读并清空 GL 错误码；实测健康态恒为 0、失效态恒为 1282），在 3s 健康轮询里——除原有 `isGlLost()` 外，增加"**连续两轮（约 6s）都报非 0 GL 错误且 `ready && !recoverPending`**"即判定静默失效并 `scheduleRecover()` 重建；`onVisibilityChange`（回到前台）也补一次 GL 错误检查。实测验证：人为向上下文注入持续 GL 错误（`bindTexture(null)`+`texParameteri`，确认产 1282）→ `diag.rebuilds` 由 1→2、`isContextLost()` 全程 false → 自动重建后人物恢复。
     - **⑦ "人物时不时消失"的根治（2026-10-11，接手者必读；④⑥ 都是"事后补救"，本项才是根因治理）**：用户反馈问题仍反复，要求"好好解决"。复盘出三层病根与对策：
       - **根因 1 · 上下文泄漏（"越修越坏"的恶性循环）**：原方案「一检测到失效就整体重建」每次都 `new Application()`（＝新建一个 WebGL 上下文）。浏览器对同页并发 WebGL 上下文有上限（约 8~16 个），旧上下文若不彻底释放就会累积，逼近上限时浏览器强制回收最旧的那个 → 又一次静默失效。此外 **HMR（热更新换模块）会让旧模块 closure 持有的 Application 变成"孤儿"**，其上下文不会被 `onBeforeUnmount` 回收 —— 多次快速热更新后页面直接白屏（本次实测复现：连续改文件后舞台 canvas 消失）。
       - **对策 1 · 单上下文约束**：新增模块级全局注册表 `globalThis.__siaLive2dStage`（跨 HMR 共享），保证任一时刻只有一个 Application；`initStage` 开头清理孤儿实例；新增 `hardDestroyApp()` 显式调 `WEBGL_lose_context.loseContext()` 释放上下文（Pixi 的 `destroy` 内部也会调，这里再兜底一次）；新增 `import.meta.hot.dispose(() => destroyStage())` 在模块被替换前主动回收。
       - **根因 2 · 静默失效时"重建"反而制造新上下文**：上下文还活着、只是纹理等 GPU 资源被回收（每帧报 1282）时，重新上传资源即可恢复，根本不需要新建上下文。
       - **对策 2 · 原地重载优先**：新增 `reloadModel()` —— 只销毁旧 `Live2DModel` 并在**同一上下文**里重新 `Live2DModel.from()`（重传纹理）。`runRecover` 分流：`silent`（上下文在）→ 先原地重载；`lost`（上下文丢）或原地重载已试过仍失效 → 才整体重建。
       - **根因 3 · 检测太慢**：原来 3 秒 `setInterval` + 连续两轮 + 1.5s 防抖，最坏约 6 秒才恢复。
       - **对策 3 · 帧级巡检**：健康巡检从 `setInterval(3000)` 改为挂在 `app.ticker` 上、每 `HEALTH_CHECK_FRAMES=30` 帧（约 0.5s）检查一次 `getGlError()`，防抖从 1500ms 降到 `RECOVER_DEBOUNCE_MS=400`ms，最坏恢复时间从 ~6s 降到 ~1s。
       - **实证（2026-10-11，用注册表里的 `gl` 做注入测试）**：
         - ① 正常全新加载：`[Live2dStage]` 无报错，canvas 已创建，角色可见。
         - ② 伪装"静默失效"（把 `gl.getError` 临时改为恒返回 1282 共 2s）→ 结果 `{rec:{mode:'silent'}, done:{mode:'silent', ok:true}, sameApp:true}`：**恢复成功且 `app` 实例未变 → 复用同一上下文，没有新建上下文**（根治点达成）。
         - ③ 强制丢上下文（`WEBGL_lose_context.loseContext()`）→ `{mode:'lost', ok:true, sameApp:false}`：正确整体重建为新上下文，**截图确认角色恢复可见**。
       - 备注：全局注册表 `window.__siaLive2dStage` 是**有意的设计探针**（供排障读取当前 app），不是临时调试 UI，故保留；⑤ 里清理的是状态徽标/读数条等**可见**临时 UI。
2. **情绪驱动接入**（✅ 已接入并实机核准，2026-10-11）
   - 后端 `chat.py` 的情绪判定已有（`detect_emotion` 返回 开心/难过/生气/疲惫/兴奋/平静/焦虑/感动/害羞/惊讶/傲娇 等），在 WS/SSE 响应里把 emotion 字段带给前端
   - 前端建 情绪 → expression/motion 映射表（参考 emotionAnim.ts 现有映射结构），替换/并存 `StageSprite.vue`
   - 参考 airi 的 stage-ui 组件封装与 Open-LLM-VTuber 的指令协议
   - **✅ 初版已接入（2026-10-11）**：链路 = 后端 `emotion` → `StageView` 的 `reactionMood()` → `Mood` → `Live2dStage` 的 `mood` prop。新增 `MOOD_EXPRESSION` 映射（happy→`f01` 张嘴笑 / sad→`f07` 嘴角下撇 / angry→`f02` 压眉 / anxious→`f03` 皱眉 / sleepy→`f03` / shy→`f06` 含 `ParamTere` / surprised→`f05` 睁大眼 / tsundere→`f02`），`StageView.vue` 传 `:mood="mood"`。
   - ⚠️ 两点必读：①该映射最初是按各 `exp3.json` 改动的参数语义**推测**的（Haru 未附表情说明）；②库的坑 —— `model.expression()` 无参不是"复位"而是 `setRandomExpression()`（随机），复位必须显式调 `motionManager.expressionManager.resetExpression()`。
   - **✅ 2026-10-11 实机逐一点按截图核对（结论已回写代码与预览条标签）**：f00 微张嘴 ｜ f01 **张嘴笑＝开心** ｜ f02 压低眉+张嘴（不满/喊）｜ f03 皱眉抿嘴（失落/忧伤）｜ f04 **闭眼微笑 ^_^**（需特殊处理，见下）｜ f05 睁大眼（惊愕）｜ f06 腮红（害羞）｜ f07 闭眼+嘴角下撇（难过）。
   - **⚠️ f04「失效」根因与修复（接手者必读）**：f04 的效果是把 `ParamEyeLOpen/ROpen` **乘 0**（即闭眼 ^_^）。但库的每帧更新时序是「`expressionManager.update()` 先跑 → `eyeBlink.updateParameters()` 后跑」（见 `cubism4.js` 的 `update()`），而眨眼用的是 `setParameterValueById`（**覆写**而非相乘），于是每帧把 `EyeLOpen` 硬写回 1，f04 的闭眼被冲掉 → 表现"点了几乎没变化"。修复：`Live2dStage.vue` 增加 `BLINK_OFF_EXPRESSIONS = new Set(['f04'])`，套用这些表情时 `model.setEyeBlinkEnabled(false)`、切走/复位时恢复 `true`（眼睛本就闭着，无需再眨）。修复后实机截图＝清晰闭眼微笑。
   - 决策：`happy` 仍映射 **f01**（张嘴笑且保留自然眨眼）；f04 虽已可用，但它会让角色持续闭眼、观感偏"睡着"，仅保留给短促反应/预览使用，不用于常驻 mood。
   - 映射复核：`happy→f01` 与 `sad→f07`、`shy→f06`、`surprised→f05` 一一对应；`angry/tsundere` 共用 `f02`、`anxious/sleepy` 共用 `f03`（Haru 仅 8 表情，同组需靠动作/速度区分，暂可接受）。
   - **✅ 2026-10-11 触发源扩充：点击身体部位 → 反应表情**（用户原本的设计意图 = 表情由"说的话"或"戳身体某处"触发）
     - Haru 有两个命中区（`model3.json` 的 `HitAreas`：`Head`/`Body`）。实测命中范围：**头 ≈ 画布 y 20–140**，肩部空隙 ≈ y 170，**身体 ≈ y 200 以下**（由 `model.hitTest()` 逐点扫描得出）。
     - 规则见 `Live2dStage.vue` 的 `HIT_REACTION`：**戳头 → `f06` 害羞（腮红）**、**戳身 → `f02` 不满（压眉张嘴）**；同时仍播 `Tap` 动作。
     - 反应为**短暂覆盖**：`REACTION_MS = 2000`，2 秒后自动回到当前心情（`triggerHitReaction` + `currentExpression`）。优先级：**点击反应 > 心情映射 > 复位待机**。
     - 实测：戳头→腮红，2.4s 后（mood=tsundere 时）回到 f02 而非待机；戳身→张嘴压眉，2.6s 后恢复。两条链路互不干扰。
     - 触发源小结：**① 用户说的话**（`emotionAnim.ts` 的 `reactionMood`，LOVE→害羞 / PRAISE→傲娇 / AMAZED→惊讶，**本地即时，不等后端**；后端 `emotion` 到了再覆盖）＋ **② 点击身体部位**（本项）。
   - motion 维度暂未接（Haru 仅 `Idle`/`Tap` 两组）；`haru_g_m07`/`m15` 可另挂独立 `Gesture` 组复用。
3. **口型同步接入**
   - edge-tts 返回的音频流交给 `model.speak(audio)`（@jannchie fork 自带口型同步）
   - 注意音频播放与现有 TTS 播放逻辑（朗读按钮）的衔接
4. **保留傲娇表情动画的兼容**
   - `emotionAnim.ts` 的 tsundere 等映射保留，能映射到 Live2D 的 expression 就映射，映射不到的先保留 CSS 兜底
5. **设定注意事项（写提示词/交互文案时）**
   - 希亚的存在论用语是"人造意识"，她绝不能自称 AI；"AI"只许作为她痛恨的贬称出现（详见项目记忆）
   - 项目英文名最终定为 Sia-ai（Sia 是她给自己取的英文名，源自 Xiya OS 简写的设定彩蛋）
6. **专属模型（后期，等 ComfyUI 到位后）**
   - **生成工具已定：只用 ComfyUI，不再装 SD WebUI/A1111**（模型通用，ComfyUI 工作流可复现进 git、自带 API 可被后端调用，Live2D 分层新工具也首发 ComfyUI 节点）
   - ComfyUI 生成立绘（红发褪白、左红右金异色瞳，设定见 F:\设定的对话集合\novel\01-希亚.md）
   - 自动分层 PSD → Cubism Editor 绑骨或委托（约 2000–3000 元起，商用权写进合同）
7. **模型「可替换结构」（✅ 2026-10-11 已搭好，等模型后补）**
   - 单一配置源：`frontend/src/config/live2d.ts` 集中了 `MODEL_URL` / `MOOD_EXPRESSION` / `BLINK_OFF_EXPRESSIONS` / `HIT_REACTION` / `REACTION_MS`，组件 `Live2dStage.vue` 只从这里 import，自身不含任何模型相关常量
   - 换模型 4 步（只改这一个文件）：① `MODEL_URL` 指向新模型 `.model3.json`；② `MOOD_EXPRESSION` 按新模型 `Expressions[].Name` 重填；③ `HIT_REACTION` 按新模型 `HitAreas` 重填；④ 新模型若无"闭眼造型"类表情则 `BLINK_OFF_EXPRESSIONS` 留空
   - 当前 `MODEL_URL` 仍指向官方示例 Haru；希亚模型就绪后改成 `/live2d/sia/sia.model3.json` 并把模型全套文件放进 `frontend/public/live2d/sia/` 即可
8. **术语改名「静态立绘」→「写实立绘」（✅ 2026-10-11）**
   - 用户可见文案已改：`StageView.vue` HUD 🎭 按钮 `:title`「切回写实立绘」；组件注释与本文档术语同步（旧称"伪 2D 立绘"一并弃用）
   - 写实立绘画面本身改用 ComfyUI 重新生成（见第 6 条），完成后替换 `frontend/src/config/sprite.ts` 的 `MAIN_SPRITE`

## 附：主要来源

- [pixi-live2d-display](https://github.com/guansss/pixi-live2d-display) · [@jannchie fork](https://www.npmjs.com/package/@jannchie/pixi-live2d-display) · [@naari3 fork](https://www.npmjs.com/package/@naari3/pixi-live2d-display) · [@laplace.live fork](https://www.npmjs.com/package/@laplace.live/pixijs-live2d)
- [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) · [moeru-ai/airi](https://github.com/moeru-ai/airi) · [SillyTavern Live2D 文档](https://docs.sillytavern.app/extensions/live2d/) · [talkinghead 文档](https://docs.sillytavern.app/extensions/talkinghead/)
- [Cubism SDK for Web 许可](https://www.live2d.com/zh-CHS/sdk/license/) · [官方示例数据集](https://www.live2d.com/zh-CHS/learn/sample/)
- [单图到 Live2D 自动管线博客](https://blog.return.moe/en/2026/07/19/towards-fully-automated-live2d-style-animation/)
