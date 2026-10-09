# 希亚前端 · Galgame 全屏舞台改版计划

## Context（背景与目标）

用户验收前端时提出完整愿景：主界面应是**全屏立绘舞台（galgame 演示风）**——立绘朝鼠标方向倾斜（伪视线跟随）、鼠标晃太快触发"发晕"反馈、底部对话框打字机显示回复并语音播报、历史记录以 galgame backlog 方式收起/打开、设置隐藏可呼出。

已与用户确认的三项决策：

1. **伪动态立绘过渡**：不用真 Live2D，用现有 PNG 立绘 + 视差/呼吸/倾斜动效，**零新增 npm 依赖**
2. **完全替换**旧双栏聊天页（不留经典模式）
3. **分两期**：本期做舞台体验全量（含 TTS 语音回复），"我说她也说"的自动语音循环留下期

后端本期**零改动**（chat/voice 接口齐全，回复自带中文情绪标签可驱动动效）。

## 实施步骤

### 步骤 1：立绘选定（用户参与，阻塞项）
- dev server 已运行，让用户在浏览器查看 `/avatars/` 全部 9 张 PNG，挑 1 张主立绘 + 2~3 张情绪差分
- 把选中文件**复制**为语义化文件名：`stage-main.png`、`stage-happy.png`、`stage-sad.png` 等
- 必须复制改名而非引用原名：PWA 对 `/avatars/` 是 CacheFirst 30 天缓存（vite.config.ts L33-L41），换图不换名会被缓存钉死

### 步骤 2：常量与配置层
- 新建 `frontend/src/config/sprite.ts`：`MAIN_SPRITE`、`EXPRESSION_DIFFS`（emotion 前缀 → 图片路径）、`PARALLAX_MAX_DEG`、`DIZZY_SPEED_THRESHOLD`——立绘与参数的单一配置源，换图只改此文件
- 新建 `frontend/src/utils/emotionAnim.ts`：`emotionAnimClass(emotion?)`，复用 `src/utils/emoji.ts` 的"精确→模糊包含"匹配模式。映射：开心/喜悦/兴奋→`anim-bounce`；难过/伤心→`anim-sad`；生气→`anim-angry`；焦虑/紧张→`anim-anxious`；疲惫/困→`anim-sleepy`；未知→呼吸 idle；发晕独立类 `anim-dizzy`

### 步骤 3：四个 composables（纯逻辑先行）
- 新建 `frontend/src/composables/useParallax.ts`：pointermove 归一化 nx/ny∈[-1,1] → 目标 rotateY±6°/rotateX∓4°/translate±12px，rAF 内 lerp(0.08) 逼近，`pointerleave` 回零；触屏或 `prefers-reduced-motion` 降级静态；同时暴露指针瞬时速度 px/s
- 新建 `frontend/src/composables/useDizzy.ts`：状态机 `idle→dizzy(2.5s)→cooldown(8s)→idle`；触发=速度>2500px/s 的采样在 500ms 内≥3 次；冷却期忽略重复触发
- 新建 `frontend/src/composables/useTypewriter.ts`：`typedText/start/skip`，约 35ms/字，新回复打断重放，点击对话框 skip
- 新建 `frontend/src/composables/useTTS.ts`：`textToSpeech` → `new Audio(blobURL)`；`play()` 被 NotAllowedError 拒绝时置 `autoplayBlocked=true` 保留 blob 等用户点击；统一 revoke URL；打字机与 TTS 并行互不等待

### 步骤 4：舞台组件
- 新建 `frontend/src/components/stage/StageSprite.vue`：两层 `<img>` opacity crossfade(400ms) 实现表情差分；动态拼情绪动画类；dizzy 时摇晃 keyframes + 头顶 😵‍💫 气泡随机台词；外层 `perspective:1000px` 容器接收视差 transform
- 新建 `frontend/src/components/stage/DialogBox.vue`：名牌"希亚" + 打字机文本区 + 输入框/🎤/发送（**搬 ChatView 的 draft/send/onKeydown/autoResize 与 useRecorder**）；sending 时省略号动效；TTS 被拦截时显示"🔊 点此播放"胶囊
- 视觉规格：对话框 max-width 880px 贴底居中；日间 `rgba(255,255,255,.6)+blur(14px)`、夜间 `rgba(30,25,42,.72)+blur(14px)`；底部垫 `linear-gradient(transparent→rgba(0,0,0,.4))` 暗角保可读性

### 步骤 5：StageView 组装 + 路由 + store
- 新建 `frontend/src/views/StageView.vue`：`100dvh overflow:hidden` 全屏；`onMounted` 调 `chat.init()`（搬 ChatView）；HUD 右上（📜历史/💞面板/⚙️设置/🌙主题/🔊TTS 开关 + 好感度 badge）
- 改 `frontend/src/router/index.ts`：`/` → StageView；删除 `/settings` 路由但**保留重定向** `{ path:'/settings', redirect:'/' }` 防 PWA 旧缓存入口 404
- 改 `frontend/src/stores/ui.ts`：加 `overlay: 'none'|'history'|'panels'|'settings'`（互斥）与 `ttsEnabled`（localStorage 持久化）；移除废弃的 `sidebarOpen`

### 步骤 6：三个覆层（Teleport + v-if + Transition）
- 新建 `frontend/src/components/stage/HistoryOverlay.vue`：全屏黑纱 blur，居中 860px 滚动列表，galgame backlog 式纯文本（名牌+正文），直接渲染 `chat.messages`，进入滚到底
- 新建 `frontend/src/components/stage/SettingsDrawer.vue`：右侧 400px 滑出抽屉，**整段搬 SettingsView 的表单逻辑**（persona store、保存/重置好感/清空历史），收编人格自检开关
- 新建 `frontend/src/components/stage/PanelsOverlay.vue`：全屏覆层 + tab（关系/搜索/记忆/日记），**零改动复用** AffinityPanel/SearchPanel/MemoryPanel/DiaryPanel
- ESC / 点遮罩均可关闭

### 步骤 7：清理旧界面
- 删除（删后 grep 复查无 import 残留）：`views/ChatView.vue`、`views/SettingsView.vue`、`components/MessageBubble.vue`、`components/TypingIndicator.vue`、`components/SidePanel.vue`、`components/CharacterSprite.vue`
- 保留：4 个 Panel 组件、全部 stores/api/composables/utils
- 改 `frontend/src/styles/main.css`：舞台玻璃面板变量 + `prefers-reduced-motion` 全局兜底

### 步骤 8：验证 + Git 同步
1. `npm run type-check` / `npm run lint` / `npm run build` 全过
2. dev server 手工清单：发消息→打字机→TTS 出声；晃鼠标→发晕动画+气泡+8s 冷却；历史/设置/面板覆层开关；明暗主题切换；移动端视口
3. 浏览器实际验收（用户亲眼确认视觉）
4. git commit + push 到 GitHub（用户要求实时同步）

## 风险与对策
- **自动播放策略**：发送点击构成 user activation 基本放行；Safari 严格 → useTTS 拦截检测 + 手动播放胶囊兜底
- **移动端无鼠标**：视差降级为触摸拖拽 + 静态呼吸；陀螺仪留下期
- **PWA 缓存**：registerType autoUpdate 足够；立绘靠语义化改名绕开 CacheFirst
- **情绪词自由文本**：映射必须模糊匹配，未知词回落 idle

## 关键文件清单
| 动作 | 文件 |
|------|------|
| 新建 | `src/views/StageView.vue`、`src/components/stage/{StageSprite,DialogBox,HistoryOverlay,SettingsDrawer,PanelsOverlay}.vue`、`src/composables/{useParallax,useDizzy,useTypewriter,useTTS}.ts`、`src/config/sprite.ts`、`src/utils/emotionAnim.ts` |
| 修改 | `src/router/index.ts`、`src/stores/ui.ts`、`src/styles/main.css`、`public/avatars/`（新增 stage-*.png） |
| 删除 | `src/views/{ChatView,SettingsView}.vue`、`src/components/{MessageBubble,TypingIndicator,SidePanel,CharacterSprite}.vue` |
| 复用 | `stores/chat.ts`、`stores/persona.ts`、`api/*`、`composables/useRecorder.ts`、`utils/emoji.ts`（匹配模式）、4 个 Panel 组件 |
