# 29 · 希亚 Live2D P0 协作方案

> 建立：2026-11-01。定位：把 DSH 的鲸鱼娘范式拆解、Codex++ 的桌宠路线和当前 Vue/PixiJS 代码合成一个可执行的第一阶段。
>
> **2026-11-01 方案修正**：初始 P0 安全舞台曾使用 v10 00018，但同日原设定复核后已改回 `stage-realistic-night`。旧 `final_apron` 面部拆层仅保留为隔离实验。
>
> Haru 的 63 曲线待机、8 表情、4 组物理拆解见 [docs/32_Haru基准拆解与希亚升级清单.md](32_Haru基准拆解与希亚升级清单.md)。这证明单图安全舞台只能是占位，真正升级必须先做正面分层。
>
> **同日原设定复核**：v10 与小说中的成年千年旅者不一致。默认安全舞台改回 `frontend/public/avatars/stage-realistic-night.png`；v10 只保留结构参考。见 [docs/33_希亚原设定视觉核对.md](33_希亚原设定视觉核对.md)。

## 一、当前判断

希亚现在缺的不是“完整 Cubism”，而是第一眼能看出活着的角色表现。

P0 只验证四件事：

1. 会眨眼。
2. 眼珠会跟随指针。
3. 说话时嘴型随 TTS 音量变化。
4. 8 个 `Mood` 能切换，且不跳脸。

P0 不做：

- 三视图和背面。
- Cubism moc3 绑骨。
- 全身骨骼。
- 8 张整身差分图。
- 新的自动抠图模型。

## 二、两条形象支线

| 支线 | 输入 | 输出 | 负责 |
|---|---|---|---|
| 桌宠 A | 单正面全身图 | 正面动作 WebM → 透明桌宠 | Codex++ |
| 舞台 P0 | `frontend/public/avatars/stage-realistic-night.png` | 原设定优先的安全半身舞台 | Codex++ 原型，DSH 负责合入 |

两条线共用一张正面底图，但不强行共用运行时。桌宠是视频池，舞台是参数化渲染。

## 三、P0 运行时选型

P0 使用 **Canvas 2D 面部层 + 原图底图**，不新开 WebGL。

原因：

- 当前 Haru Live2D 和 `StageParallax` 已经证明项目里存在 WebGL 上下文回收风险。
- 脸只占整张图的一小块，Canvas 2D 足够，且调试成本低。
- P0 可以先证明眨眼、视线、口型和表情的视觉价值，再决定是否迁移到 P1/P2。

P1 才复用现有 `StageParallax.vue` 的 PixiJS Mesh 和深度图，做头发、呼吸和轻微位移。P3 只有在需要真实转头时才进入 PSD2Live。

## 四、组件契约

建议新增一个舞台层组件，名字暂定 `SiaFaceStage`。DSH 拥有 `frontend/src/**`，接口先按下列契约对齐：

```ts
export type SiaMood =
  | 'neutral'
  | 'happy'
  | 'sad'
  | 'angry'
  | 'anxious'
  | 'sleepy'
  | 'shy'
  | 'surprised'
  | 'tsundere'

export interface SiaPose {
  mood: SiaMood
  talk: number      // 0..1，来自 TTS RMS
  gazeX: number     // -1..1
  gazeY: number     // -1..1
  blink: number     // 0..1，1=完全睁开
  breath: number    // -1..1
}
```

约束：

- 行为状态机不放进 Vue 组件，组件只消费姿态参数。
- 指针、TTS、Mood 由上层 composable/store 提供。
- `prefers-reduced-motion` 时关闭呼吸、倾斜和自动眨眼，保留嘴型。
- P0 提供透明回退：Canvas 失败时显示静态 `frontend/public/avatars/stage-realistic-night.png`。
- 不创建第二个长期 WebGL 上下文。

## 五、TTS 口型输入

现有 `useTTS()` 只返回 `speaking` 布尔值，无法驱动嘴型。

P0 增加 `talkLevel: Ref<number>`：

1. TTS 返回 Blob 后创建 `HTMLAudioElement`。
2. 播放时通过 `AudioContext.createMediaElementSource()` 接 `AnalyserNode`。
3. 每帧读取时域数据，算 RMS，平滑到 0..1。
4. 播放停止、失败或切歌时归零。
5. 自动播放拦截时，用户点击 `resume()` 后才创建/恢复音频上下文。

音频上下文失败时，`talkLevel` 恒为 0，文字和脸部渲染不能中断。

## 六、P0 接口与状态流

```text
chat.reply.emotion ─┐
lastUserText ───────┼→ reactionMood() → SiaPose.mood
pointer move ───────┼→ gazeX / gazeY
useTTS.talkLevel ───┼→ talk
blink state machine ┬→ blink
breath clock ───────┘→ breath
```

P0 不改变聊天协议，不改后端。口型只消费前端音频，与后端使用哪种 TTS 无关。

## 七、分层资产

具体坐标和 bbox 见 [docs/28_希亚P0面部分层资产规格.md](28_希亚P0面部分层资产规格.md)。

最低图层：

- face base / skin patch
- eyeL_lash / eyeL_ball / eyeL_iris
- eyeR_lash / eyeR_ball / eyeR_iris
- brows
- neutral_mouth
- blush

异色瞳必须保持：画面左侧金色，画面右侧红色。不能用全局换色覆盖。

## 八、验收门

### P0

- 10 秒录屏里至少出现 2 次自然眨眼，接缝不可见。
- 指针移动时两只眼睛有视线变化，远眼位移不超过近眼。
- TTS 播放时嘴型随音量变化，停止后归零。
- 8 个 Mood 至少能切换 3 个可辨状态，不出现整脸闪白、错位或跳回旧图。
- Canvas 非空像素数大于 1000，页面无控制台异常。
- 自动播放被拦截时，脸部仍可渲染，不抛异常。

### P1

- 前发/侧发/后发有轻微延迟和回弹。
- 整体呼吸 30 秒不僵。
- 写实立绘模式仍可回退。
- 不产生 WebGL 上下文泄漏。

## 九、协作边界

- DSH：`frontend/src/**` 渲染层、`docs/26`、`docs/12`。
- Codex++：分层资产、TTS RMS 接线建议、独立原型、验收脚本、桌宠 A 支线。
- 共同交汇：`docs/28` 的图层 manifest、`SiaPose` 契约、P0 录屏验收。

任何一边先跑通，都不能直接覆盖另一边的视觉标准；先合入独立原型，再由用户验收。

## 十、2026-11-01 原型结果

隔离原型已落地：

- 默认安全舞台：`prototypes/live2d-p0/index.html` + `safe.js`
- 隔离面部实验：`prototypes/live2d-p0/face-redraw.html` + `face-redraw.js`
- 默认冒烟：`prototypes/live2d-p0/smoke-check.mjs`
- 资产规格：[docs/28_希亚P0面部分层资产规格.md](28_希亚P0面部分层资产规格.md)

安全舞台 Chromium smoke test 通过：

- 采用 `frontend/public/avatars/stage-realistic-night.png`。
- 画布尺寸 `896×896`，成年花店半身完整可见。
- `Mood` 可切换，微动效可暂停。
- 截图：`sia_out/safe_stage_setting_preview.png`。

隔离面部实验的旧测试记录仍然保留：

- 画布非空采样 `14874`。
- `Mood` 成功切到 `shy`。
- 手动眨眼 openness 降到 `0.02`。
- 口型参数达到 `0.8`。
- 6 张 P0 图层全部加载。
- 新增静止视觉门禁 `scripts/sia_face/check_face_layers.py`：眼部 MAE 必须 ≤ 5，嘴部 MAE 必须 ≤ 8。
- 修复双瞳/空眼窝后，同视线截图保存为 `sia_out/sia_face_p0/gaze_preview.png`。

默认安全舞台仍不能冒充正式 Live2D：

1. 只有呼吸、轻微倾斜和指针视差，没有眼动、口型或表情差分。
2. 面部拆层实验仍有眼窝 inpaint、眼白/睫毛分离和嘴型缺口。
3. v10 00018 只能做结构参考，成年感和角色身份不符。

这些缺口完成前，本阶段只能作为“安全 2.5D 舞台”，不算正式 Live2D。
