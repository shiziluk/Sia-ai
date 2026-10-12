# 假 Live2D 驱动 调研报告 + 实施清单

> 调研日期：2026-10-12。调研背景：[docs/10 §四.6](file:///d:/workspace/Sia-ai/docs/10_希亚立绘资产进度留档.md) 流水线第 6 步「假 Live2D 驱动（未开始）：参考 docs/08 Haru 实现」。
> 术语澄清：本条的「假 Live2D」≠ docs/08 的真 Live2D（Haru Cubism 模型 + pixi-live2d-display），也≠ docs/09 的 2.5D 深度视差。它是**第三条路线**——在希亚专属 Cubism 模型（委托绑骨，后期，见 docs/08 §五.6）做好前，用希亚本人的三视图/立绘抠图凑出真 Live2D 的核心特征动效（眨眼/嘴动跟随 TTS/呼吸/视线跟随/情绪表情），作为过渡方案。

## 一、定位与边界

| 路线 | 输入资产 | 动效来源 | 状态 |
|---|---|---|---|
| 真 Live2D（docs/08） | Haru 官方 Cubism 模型 | pixi-live2d-display 库 + model3.json 绑骨 | ✅ 已接入（情绪驱动/点击反应/七项修复全做完）；口型同步待接 |
| 2.5D 深度视差（docs/09） | 希亚立绘 + 深度图 | PixiJS v8 自定义着色器（深度位移） | ✅ 夜版已接线；日版待出 |
| **假 Live2D（本文档）** | **希亚立绘 + 分层/差分图** | **CSS / PixiJS 程序化动（眨眼/嘴动/视线）** | **未开始** |

**互补关系**：视差做「镜头移动感」（近远层位移），假 Live2D 做「角色自身动」（眼/嘴/眉），两者可叠加；真 Live2D 是完整替代方案，与假 Live2D 互斥（不同时用）。

**触发条件**：docs/10 §四流水线前 5 步完成后（三视图重抽→抠图→贴基线脸→补金瞳），拿到的合格立绘才能进假 Live2D 分层。今天 ComfyUI 离线，本调研是「技术选型与实施清单」，不开始分层。

## 二、现状摸底（已有哪些可复用）

| 资产 | 位置 | 复用方式 |
|---|---|---|
| 情绪差分图配置 | [sprite.ts](file:///d:/workspace/Sia-ai/frontend/src/config/sprite.ts) `EXPRESSION_DIFFS` | 当前为空（用 CSS 滤镜近似）；填路径即可自动切图 |
| CSS 一次性情绪动画 | [StageSprite.vue](file:///d:/workspace/Sia-ai/frontend/src/components/stage/StageSprite.vue) `anim-*` keyframes | bounce/sink/shake/tremble/sway/curl/jolt/turnaway/wobble 已就绪 |
| 深度视差 + 呼吸微动 | [StageParallax.vue](file:///d:/workspace/Sia-ai/frontend/src/components/stage/StageParallax.vue) | PixiJS v8 Mesh + 着色器；`uBreath` uniform 已驱动呼吸；假 Live2D 的呼吸可复用 |
| 情绪→mood 映射 | [emotionAnim.ts](file:///d:/workspace/Sia-ai/frontend/src/utils/emotionAnim.ts) `reactionMood` | 撩→害羞/夸→傲娇/惊叹→惊讶，已接 StageView |
| TTS + speaking 状态 | `useTTS` composable（StageView 引用） | `speaking` 布尔值当前只驱动对话框；假 Live2D 嘴动可挂这里 |
| 指针归一化 | `useParallax` composable（`nx/ny`） | 假 Live2D 视线跟随可复用 |
| 全局单实例 WebGL 注册表 | `globalThis.__siaLive2dStage` | 假 Live2D 若走 PixiJS 必须复用，互斥切换 |

**缺口（假 Live2D 要补的）**：
1. 眨眼（auto-blink）——真 Live2D 库自带，假 Live2D 要自己定时驱动
2. 嘴动跟随 TTS——真 Live2D 用 `model.speak(audio)`，假 Live2D 要自己分析音频或帧切换
3. 视线跟随（眼球位移）——目前只有镜头视差，没有角色眼球跟随
4. 情绪表情差分图——`EXPRESSION_DIFFS` 为空

## 三、技术路线对比

| 方案 | 输入 | 实现 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|---|
| **A. 差分图切换** | N 张同构图表情差分图（闭眼/张嘴笑/皱眉…） | 填 `EXPRESSION_DIFFS`，前端按 mood 切图 + CSS 动画 | 复用现有架构，零分层成本；立竿见影 | 不是真「动」是「切图」；嘴动跟随 TTS 需每音素一张嘴形，不现实 | **阶段 1 用**（情绪表情粗粒度切换） |
| **B. 分层 PNG + PixiJS/CSS** | 立绘切成 眼皮/眼球/嘴/眉/发丝/身体 6 层透明 PNG | PixiJS 多 Sprite 叠加，程序化动（眨眼=眼皮 scale Y，嘴动=嘴 scale Y 跟音频，视线=眼球 xy 位移） | 真「动」；可做眨眼/嘴动/视线 | 分层是硬骨头（See-through 实验性 / 手工 inpaint 费时）；需存一套图层 | **阶段 2 用**（眨眼+嘴动+视线） |
| C. talkinghead AI 单图驱动 | 单张静态图 + 音频 | AI 生成类 Live2D 动作（SillyTavern talkinghead） | 零分层，真动 | 需额外模型/服务，画质不稳，可能 GPU 实时 | 不适合（伴侣应用首屏体感） |
| D. 伪 Cubism 模型 | 立绘分层 PSD → Cubism Editor 绑骨 → .model3.json | pixi-live2d-display 加载伪模型 | 即是真 Live2D，效果完整 | 绑骨仍需手工/委托，等于 docs/08 §五.6 专属模型路线 | 不算「假 Live2D」，归后期 |

## 四、推荐落地方案（分阶段）

### 阶段 1：情绪表情差分图（复用 EXPRESSION_DIFFS，零分层）

- **出图**：三视图合格后，用同一 seed/底座出 8 张表情差分（对应 [emotionAnim.ts](file:///d:/workspace/Sia-ai/frontend/src/utils/emotionAnim.ts) 的 8 个 mood：happy/sad/angry/anxious/sleepy/shy/surprised/tsundere），每张只改五官（闭眼笑/张嘴/皱眉/腮红…），身体姿势不变
- **⚠️ 2026-10-12 新规则约束（docs/11 §三.2b）**：
  - 差分图间**形象零漂移**（发长/服装/体型完全一致）
  - 素材姿势必须 **hands visible**（手垂身侧可见，禁藏手——手臂要能活动）
  - 表情差分除 8 个 mood 外，还需为**鼠标点击反应**出差分：普通部位（头/身）与敏感部位**不同反应设计**（参考 docs/08 真 Live2D 的 Head/Body HitAreas 机制，敏感部位反应需单独设计表情+可能的动作差分）
  - 三张基准原型图（stage-main.png + 品红 00001/00002）为所有差分的形象参考；黑丝版必须双腿黑丝完整（不复刻原型单脚瑕疵）
- **出图手段**：ComfyUI 蒙版 inpaint，**脸区不涂蒙版锁死**（沿用 docs/09 §6.1 面部一致性基线），只重绘眉/眼/嘴
- **前端**：填 `EXPRESSION_DIFFS` 路径，[StageSprite.vue](file:///d:/workspace/Sia-ai/frontend/src/components/stage/StageSprite.vue) `currentSrc` 自动切图；mood 滤镜可保留也可去掉（差分图本身已带表情）
- **成本**：8 张 mood 差分 + N 张点击反应差分 inpaint + 改一个 ts 文件

### 阶段 2：分层 PNG + 程序化动（眨眼+嘴动+视线）

- **分层来源**（二选一，待 ComfyUI 到位后评估）：
  - **B1. 手工 inpaint 补全遮挡**：用 ComfyUI inpaint 把眼/嘴/眉/发丝的「遮挡部分」补全，再程序化抠出 6 层透明 PNG（最干净，但要 5 次 inpaint）
  - **B2. See-through 类工具**：`shitagaki-lab/see-through` 单图自动拆 PSD（实验性，质量待验证）
- **前端组件**：新建 `StagePseudoLive2d.vue`，PixiJS v8 多 Sprite 叠加（复用 `__siaLive2dStage` 注册表）
- **动效实现**：
  - 眨眼：定时器每 4-6s 随机触发，眼皮 Sprite `scale.y` 1→0.1→1（150ms），偶尔连眨
  - 嘴动：`useTTS` 的 audio 流接 `AnalyserNode` 提取音量 RMS → 嘴 Sprite `scale.y` 0.2~1.0 实时驱动（音素级分类不做，够用）
  - 视线：`useParallax` 的 `nx/ny` → 眼球 Sprite `x/y` 位移（±4px）
  - 呼吸：复用 [StageParallax](file:///d:/workspace/Sia-ai/frontend/src/components/stage/StageParallax.vue) 的 `uBreath` 逻辑，或独立 CSS keyframes
- **成本**：5 次 inpaint + 抠图脚本 + 新组件 + AnalyserNode 接线

## 五、与视差/真 Live2D 的共存约束

1. **WebGL 上下文**：假 Live2D 走 PixiJS（阶段 2）必须复用 `globalThis.__siaLive2dStage` 注册表，保证任一时刻只有一个 Application；`import.meta.hot.dispose()` 主动回收
2. **互斥切换**：StageView 的 `useLive2d` 三选一扩展为三态（真 Live2D / 写实立绘+视差 / 假 Live2D），HUD 切换按钮改为循环切换；不同屏叠加
3. **假 Live2D 走 CSS（阶段 1 差分图）可与视差叠加**：视差做镜头，差分图做表情，不冲突

## 六、TTS 口型同步衔接

- 真 Live2D：`model.speak(audio)`（@jannchie fork 自带，docs/08 §五.3 待接）
- 假 Live2D 阶段 2：`useTTS` 的 `<audio>` 元素接 `AudioContext` + `AnalyserNode` → `getByteFrequencyData()` 算 RMS → 嘴 Sprite `scale.y`。**注意**：`AudioContext` 要由用户手势激活（点击朗读按钮时创建），避免浏览器自动播放策略拦截
- 降级：`speaking` 布尔值驱动嘴「开/合」二态切换（无幅度，最简）

## 七、实施步骤（待 ComfyUI 到位后按序）

1. **前置**：docs/10 §四流水线 1-5 步完成（三视图重抽→抠图→贴脸→补金瞳），拿到合格立绘
2. **阶段 1**：出 8 张表情差分图（ComfyUI 蒙版 inpaint，锁脸）→ 填 `EXPRESSION_DIFFS` → 验证 mood 切图
3. **阶段 2 分层**：5 次 inpaint 补全眼/嘴/眉/发丝遮挡 → 程序化抠 6 层透明 PNG
4. **阶段 2 组件**：新建 `StagePseudoLive2d.vue`（PixiJS 多 Sprite）→ 接 `useParallax` 视线 + 定时眨眼 + AnalyserNode 嘴动
5. **StageView 三态切换**：`useLive2d` 扩展为 renderMode 枚举，HUD 按钮循环切
6. **验证**：`npm run type-check`；浏览器截图对比眨眼/嘴动/视线；确认与视差/真 Live2D 互斥切换无上下文泄漏

## 八、待确认项

1. 阶段 1 的 8 张表情差分图，是否随三视图 v9 一起出（同批 ComfyUI 跑）？还是三视图定稿后单独出一轮？
2. 阶段 2 分层走 B1（手工 inpaint，5 次）还是 B2（See-through 自动拆）？B2 实验性，可能要回退 B1
3. 嘴动同步：音量 RMS 驱动（够用）还是要做音素分类（A/I/U/E/O 5 嘴形，成本高）？
4. 假 Live2D 与写实立绘+视差是「叠加」还是「互斥」？阶段 1 差分图可与视差叠加；阶段 2 分层 PNG 若走 PixiJS，与视差 PixiJS 是同上下文不同 Sprite，技术上可叠加，但复杂度上升——建议互斥
5. 是否接受「阶段 1 先上，阶段 2 等 ComfyUI 跑通后再做」的渐进路线？还是等阶段 2 一起做？

## 九、与 docs/10 §四.6 的对接

docs/10 §四.6 原文「假 Live2D 驱动（未开始）：参考 docs/08 Haru 实现」应更新为：
- 参考本文档（docs/12）的技术选型与实施步骤
- 阶段 1 与三视图 v9 同批出图（待确认项 1）
- 阶段 2 等 ComfyUI 跑通分层 inpaint 后启动
