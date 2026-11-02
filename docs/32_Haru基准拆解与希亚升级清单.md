# 32 · Haru 基准拆解与希亚升级清单

> 建立：2026-11-01。参考对象：项目当前 Haru Cubism 示例模型。
> 目的：把“参考 Haru”拆成可执行差距，而不是只说画面不够高级。

## 一、本地证据

- 模型：`frontend/public/live2d/haru/haru_greeter_t03.moc3`
- 参数组：`EyeBlink`、`LipSync`
- 表情：8 个 `expressions/F01~F08.exp3.json`
- 动作：5 个 `motion/*.motion3.json`
- 物理：`haru_greeter_t03.physics3.json`，4 组设置
- 组件：`frontend/src/components/stage/Live2dStage.vue`

## 二、Haru 为什么看起来“活”

### 1. 待机动作是 10 秒复合曲线

`haru_g_idle.motion3.json`：

- 时长 10 秒。
- 63 条参数曲线。
- 同时驱动头、眼、眉、嘴、身体、手、头发、呼吸和部件透明度。

关键参数：

- 头：`ParamAngleX/Y/Z`
- 身体：`ParamBodyAngleX/Y/Z`、`ParamBodyUpper`
- 眼：`ParamEyeLOpen/ROpen`、`ParamEyeBallX/Y`、`ParamEyeForm`
- 眉：`ParamBrowL/R*`
- 嘴：`ParamMouthForm`、`ParamMouthOpenY`
- 呼吸：`ParamBreath`
- 手：`ParamArmL/R*`、`ParamHand*`
- 头发：`ParamHairFront/Side/Back`

当前 v10 安全舞台只有整体平移、缩放和轻微倾斜。它无法让头和身体分别运动，也无法独立控眼、嘴和头发。

### 2. 表情是参数叠加，不是整图切换

Haru 的 8 个表情分别修改眼开合、眼笑、眉形、嘴形、眼泪、脸红等参数。

这一点比“准备 8 张整身差分”便宜，也比整图滤镜自然。

### 3. 四组物理

物理输入包含头/身体角度，输出分别是：

- 前发：`ParamHairFront`
- 侧发：`ParamHairSide`
- 后发：`ParamHairBack`
- 围巾：`ParamScarf`

因此 Haru 转身或点头时，头发和围巾有延迟和回弹。

### 4. 点击动作和声音

Tap 动作有时长 2.03 到 5.33 秒的独立 motion，并带动画音效。当前希亚 v10 原型没有动作状态机。

## 三、当前差距

| 能力 | Haru | 当前 v10 安全舞台 |
|---|---|---|
| 整体呼吸 | 有 | 有，但只是图片缩放 |
| 头/身体分离 | 有 | 无 |
| 自动眨眼 | 有 | 无 |
| 眼球跟随 | 有 | 无 |
| 眉/嘴表情 | 参数化 | 无 |
| TTS 口型 | 参数组已定义，待接线 | 无 |
| 头发物理 | 3 组 | 无 |
| 围巾/衣摆物理 | 1 组 | 无 |
| 点击动作 | 2 套 | 无 |
| 表情切换 | 8 个 | 全图滤镜近似 |

## 四、升级优先级

### P0：先得到可分层正面

身份锚定使用 `frontend/public/avatars/stage-realistic-night.png`，参考 `stage-main.png` 锁脸；`sia_out/sia_v10_reference/front_gold.png` 只参考手、鞋和背面结构，不用它的幼态感替代原设定。分层从当前成年花店半身图出发：

- 头组：脸、前发、侧发、后发
- 眼：左右 lash / ball / iris
- 眉、嘴、脸红
- 上身、双臂、手
- 围裙、裙摆、鞋

这一步没完成，就不要再声称能做 Haru 级动作。

### P1：参数接口先对齐 Haru

推荐姿态参数：

```ts
interface SiaPose {
  angleX: number
  angleY: number
  angleZ: number
  bodyX: number
  bodyZ: number
  eyeL: number
  eyeR: number
  gazeX: number
  gazeY: number
  mouthOpen: number
  mouthForm: number
  breath: number
  hairFront: number
  hairSide: number
  hairBack: number
  skirt: number
}
```

行为层只输出这些量，渲染层不直接判断聊天情绪。

### P2：先做四项最小活感

1. 自动眨眼。
2. 眼球跟随指针。
3. 头和身体分离摆动。
4. 头发延迟摆动。

这四项通过后再接表情和口型。

### P3：再做表情和动作库

- 8 个 Mood 参数组。
- 点击头/身体的不同反应。
- TTS RMS 口型和轻量音效。
- 2 到 3 个待机动作，不追求 Haru 的五个完整动作。

## 五、对当前 v10 原型的判断

现在的安全舞台适合短期占位，不适合继续堆 CSS 动作。

原因：

- 只有一张平面图，拆头、眼、发就必然产生接缝。
- 全身大动作和面部微动作不能由一张图同时解决。
- 继续加缩放、滤镜只会更像“会动的海报”。

## 六、授权边界

Haru 示例资产只能作为行为和技术参考，不能把 Haru 的贴图或动作曲线直接当成希亚资产。Sia 的模型、纹理和动作必须来自希亚自有素材。

## 七、下一步

1. 以 `stage-realistic-night.png` 为身份锚、`front_gold.png` 为结构参考，产出第一版正面分层 PSD/PNG 规范。
2. 用现有 `Live2dStage.vue` 的参数控制方式做 Sia 参数接口对照表。
3. 先完成 P2 四项最小活感，再接 TTS。
4. 若需要真实 Cubism 转头，再进入 PSD2Live/moc3，而不是用平图模拟。
