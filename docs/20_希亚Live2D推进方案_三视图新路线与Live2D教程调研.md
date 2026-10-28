# 20 · 希亚 Live2D 推进方案（三视图新路线 + Live2D 完整教程调研）

> 调研日期：2026-10-28。缘起：用户指示搜 ComfyUI 生成正确人物视图的图文/视频教程 + Live2D 完整制作教程，为 Live2D 推进找头绪。
> 关联文档：[docs/17_Haru级Live2D制作路线调研.md](file:///f:/self_project/Sia-ai/docs/17_Haru级Live2D制作路线调研.md)（工具链与鬼图复盘）、[docs/13_生图全流程自检体系.md](file:///f:/self_project/Sia-ai/docs/13_生图全流程自检体系.md)（批次记录与反面案例库）。
> 本文档只做「教程调研 → 路线选型」；执行时按对应既有文档的检查表走。

## 一、结论（TL;DR）

1. **卡点重定位**：Live2D 链路（三视图 → see-through 拆件 → PSD2Live 绑定 → selfcheck → 前端替换）中，后四环工具链已就绪，**唯一卡点是三视图底图质量**。v9→v10 六个批次的失败史（视图数失控/发长失控/围裙正背漂移/融腿/手消失）证明：SDXL + IPAdapter + ControlNet + prompt 战争这条路线有天花板，不是 prompt 调参能根治的。
2. **2025→2026 社区共识已换解法**：一致角色多视图不再靠「参考图 + prompt 硬压」，而是用**指令式编辑大模型**（Qwen-Image-Edit 系 / FLUX Kontext 系）直接「把这张图转成三视图」——身份/服装/比例由模型保证。现有 Consistent Character Creator 3.x 工作流即此路线的成品封装。
3. **本机可行性（2026-10-28 实测 nvidia-smi）**：GTX 1050 Ti **4GB** + 16GB 内存。Qwen-Image-Edit-2509（GGUF Q4 约 7GB）/ FLUX.2 Klein 9B（4bit 约 13GB）本地跑不动 → 走**魔搭免费云端位**（AIGC 专区 / API-Inference / Qwen Chat，均零成本）或朋友桌面端（显存待确认，≥12GB 可本地部署 GGUF）。
4. **推荐双轨**：A 轨 = 魔搭免费 Qwen-Image-Edit 验证三视图质量（零成本、立即可做）；C 轨 = 本机按批次 7 既定对策再跑一轮 SDXL（变量已定，作对照兜底）。哪边先出合格三视图用哪边。
5. **Live2D 学习线**：官方 6 课教程 + 拆件规范已挖透（本文档第三节），中文视频课选定「摹形计划免费公开课（入门）→ 卡米雷特 54 课时课（全流程，带工程文件）」；**学习的主要产出物 = see-through 拆件质量的验收标准**（官方插图加工课的拆件粒度 + 遮挡补画规范），而非从零手写模型。

## 二、ComfyUI 人物三视图：教程调研与路线对比

### 2.1 调研发现的四条路线

| 路线 | 核心方法 | 一致性来源 | 显存需求 | 本机 4GB 可行性 | 参考教程 |
|---|---|---|---|---|---|
| **A. Qwen-Image-Edit 编辑式** | 参考图 + 文字指令（"转成 front/side/back 三视图"），多图参考支持 | 模型原生身份保持（2511 版再增强） | FP8 约 16GB / GGUF Q4 约 7-8GB | ✗ 本地，✓ 魔搭免费云端 | Consistent Character Creator 3.0（Mickmumpitz）；B站 BV1VqCjB5EWQ |
| **B. CharacterSheet 多视图 LoRA** | FLUX.2 Klein 9B / Krea 2 + 现成 TripleView/QuadView LoRA + 官方 workflow JSON | 训练 LoRA（约 300 张角色设定图训练集） | Klein 9B 4bit 约 13GB | ✗ | HuggingFace Alissonerdx/CharacterSheet + comfyui-wiki 介绍 |
| **C. 现有 SDXL+CN 管线** | IPAdapter 形象参考 + union promax 姿势锁定 + prompt 权重战 | IPAdapter 风格传递（弱） | 已在 4GB 跑通 | ✓（已在用） | docs/13 全部批次记录 |
| **D. 角色 LoRA 训练** | 三图基准扩 15-30 张数据集 → kohya_ss 训练希亚 LoRA → LoRA 出三视图 | LoRA 把身份锁进权重（最彻底） | SDXL 训练需 8GB+（全套省内存配置） | ✗ 本地（8GB 机器曾有过）；中期项 | locallyuncensored 2026-10 更新训练指南；B站 BV1VqCjB5EWQ 后半段 |

### 2.2 路线 A 详解（推荐主攻）

- **Consistent Character Creator 3.0**（Mickmumpitz 开发，RunComfy 有完整工作流页可下载 workflow.json）：单张参考图 → 正/侧/背视图 + 表情库 + 转台旋转 + 场景变体，RGthree Bypasser 一键切换模块。表情库模块正好对应我们 docs/12 的表情差分需求。
- **模型版本演进**：Qwen-Image-Edit-2509（2025-09，多图输入）→ 2511（角色一致性再提升、内置 LoRA 能力）。Qwen-Image-2.1（7B，最多 10 张参考图）API 已上线。
- **与我们的契合点**：
  1. 多参考图输入正好喂**三图基准**（stage-main.png 面部基准 + 品红原型 00001/00002）——用户定的「以此三张为原型」规则直接满足；
  2. 编辑式生成「脸不漂移」是模型原生能力，正面回答了 v6 批次「IPAdapter 半身像先验导致发长失控」的根因（不再让参考图全程参与采样）；
  3. 中立站姿要求可用指令描述（对比 prompt 权重战）。
- **免费云端执行位**（本机 4GB 跑不动 GGUF，零成本方案）：
  1. **魔搭 AIGC 专区**（modelscope.cn，FlowBench 云端工作流，支持 QwenImageEdit）——网页操作；
  2. **魔搭 API-Inference**（免费 API 额度）——可程序化批量出图、接自检脚本；
  3. **Qwen Chat 图像编辑**——手动单张验证最快。
- **风险与对策**：编辑式输出分辨率/画风可能与 SDXL 厚涂风有差 → 先用 stage-main.png 单图试出「正面 turnaround」，与原脸逐项比对（阶段 4 对比图流程照走）；三视图内不挤多人（逐视图生成策略不变）。

### 2.3 路线 B 详解（备选）

- CharacterSheet（HF: Alissonerdx/CharacterSheet）：TripleView_klein9b_v1 / QuadView_klein9b_v1 / QuadView_krea2_v1 三个 LoRA + 配套 workflow JSON，触发词固定（"Convert the character in the image to a Character Sheet showing front, side and back full body views"），推荐 1536×1024、8 步、CFG 1、LoRA strength 1.0。
- **官方自述限制对我们全是雷**：跨视图解剖/五官/服饰差异、侧面背面需多次生成或手工清理、**非对称设计（X 背带！）、手、复杂服装难以精确保持**。训练集以真人为主，二次元「可以但一致性下降」。
- 结论：优先级低于 A（A 是官方大模型 + 免费，B 是 300 张训练集的社区 LoRA + 本地跑不动）；若 A 的画风不符再试。

### 2.4 路线 C（本机兜底）与批次 7 对策确认

批次 7 对策已在 docs/13 批次 6 结论定死：白裤袜正面提权 `(white pantyhose:1.35)` 前置、围裙撕边负面 `(ragged hem:1.3), (torn cloth:1.3), (apron train:1.3)`、正侧强调 `(pure side view, profile silhouette:1.2)`。保持 IPAdapter end_at 0.7。**批次 7 的意义调整为「对照组」**：若 3-5 张内仍无精确 3 视图，果断停止 prompt 战争，全线转 A。

### 2.5 路线 D（中期增强项）

- 要点（locallyuncensored 2026-10-19 更新版指南）：15-30 张多变图（角度/景别/表情变化，身份不变）、虚构触发词、**caption 只写可变项（姿势/服装/背景），身份特征不写**（写了反而变成变量）；SDXL 训练 8GB 起步（batch 1 + 梯度检查点 + 8bit 优化器 + 缓存 latents + 768px bucket）；首批 LoRA 约 1-3 小时。
- 对我们的价值：拿到三视图定稿后，用 Qwen-Image-Edit 扩出 20 张合格图 → 训练希亚 LoRA → 之后所有立绘/表情差分/服装变体都由 LoRA 保底（表情差分批量产出效率大增）。
- 前提：需要 ≥8GB 显存机器（本机 4GB 不行；朋友桌面端若 ≥12GB 可承担，或届时用云端训练租卡）。

### 2.6 视频教程索引（B站）

| 视频 | 内容 | 用途 |
|---|---|---|
| BV1yjnBzmE71《comfyui工作流：AI一键生成三视图保持人物一致性 保姆级教程》 | 三视图工作流实操 | 理解编辑式三视图工作流结构 |
| BV1Cxg2z7Edd《Flux Kontext 终极玩法：一键生成完美三视图》 | Flux Kontext 路线（与 Qwen 同类） | 对照理解同类路线 |
| BV1VqCjB5EWQ《解决角色一致性/创建一致性 AI 角色（免费本地）》 | **前半：Qwen Image Edit 工作流；后半：自训练角色 LoRA** | A/D 两路线的中文完整教程 |

## 三、Live2D 完整教程调研

### 3.1 官方教程体系（免费，权威度最高）

- **基础教程共 6 课**（docs.live2d.com/zh-CHS/cubism-editor-tutorials，每课带视频 + 素材下载，模特=桃濑日和）：
  1. 插图加工（PSD 拆件）2. 准备移动插图（导入/网格/变形器）3. 添加表情 4. 添加身体动作 5. 添加脸部 XY 动作 6. 创建动画
- **第 1 课「插图加工」拆件规范全文已挖透**（这正是我们 see-through 拆件质量的验收标准）：

| 部件 | 拆分层级 | 关键规则 |
|---|---|---|
| 头发 | 前发 / 侧发 / 后发（+呆毛单层，左右侧发分左右层） | **必须加绘原图中被遮挡的部分**（否则动起来穿帮） |
| 眼睛 | 睫毛 / 眼珠 / 眼白 三层 | 眼白做成剪贴素材；外眼角上挑部分单独分 |
| 眉/鼻 | 单独层 | 变换少，简单分即可 |
| 嘴 | 上唇 / 下唇 / 口内 | **口内画大一圈 + 嘴唇上补肤色块遮盖**（官方建议口内不用剪贴蒙版，避免容量负担与突出穿帮） |
| 脸轮廓/耳 | 轮廓加绘成纯肤色圆头；耳朵可分 | 圆头更易出立体感和 XY 动作 |
| 身体 | 脖子 / 躯干 / 上臂+前臂 / 裙+左腿+右腿 | 脖子多加绘防止转头露边；丝带/领子/开衫单独分更易动 |
| 导入规范 | 线稿与填充**合并为一层**；按部件分组管理 | 官方提供 PS 合并脚本；PSD 保存 |

- 配套手册页：〔关于素材拆分〕〔创建 PSD 的注意事项〕（docs.live2d.com/zh-CHS/cubism-editor-manual/）；官方 Photoshop 脚本下载；桃濑日和教学 PSD 免费下载（cubism.live2d.com/editor-tutorial/momose1/momose_tutorial01.zip）。
- **Live2D JUKU**（juku.live2dcs.jp）：官方在线付费课，2026 版基础课程。

### 3.2 中文视频课（选定两级学习路径）

| 课程 | 平台 | 价格 | 定位 |
|---|---|---|---|
| **摹形计划 byMOCTHINK**《Live2D Cubism 编辑器入门公开课》Day1-3 | B站（space.bilibili.com/23306371 收藏夹有整理） | 免费 | 入门第一站：软件界面/建模流程概览（2025-05） |
| **卡米雷特**《Live2D建模指南（全流程含工程）》 | B站课堂（cheese/play/ep524166） | 158 元 / 54 课时 | 全流程实操：带原画 PSD + 工程文件，零基础到进阶；另有高阶课（90° 转头/手部捕捉/走路动画 ss564916140） |
| 即兴改模系列（直播切片） | B站（BV1YYEh6dEHa 等） | 免费 | 进阶观察：实际改模中的拆件思路 |

### 3.3 行业委托流程参考（用于验收 see-through 产出）

- dajoong.cloud《Live2D Rigging Commission Guide》：从接单到交付 9 步流程 + rigger 视角的 **PSD 结构要求清单**——用它验收 see-through 输出的 PSD 是否达到「可绑定」标准。
- v-oshi.net 2026 版 VTuber 立绘/Live2D 制作与委托指南：立绘 → 建模 → 参数 → 物理的行业分工全景。

### 3.4 学习目的重定位（重要）

我们的路线不是从零手写模型（PSD2Live 自动绑定 + see-through 自动拆件已把两个最脏的活自动化），**学习教程的核心产出是三个验收能力**：
1. **拆件验收**：拿官方拆件规范（§3.1 表格）审 see-through 输出的 23 层 PSD——层粒度够不够、遮挡补画有没有、命名对不对 PSD2Live 规范；
2. **绑定验收**：看懂官方第 2-5 课（网格/变形器/参数/物理）后，才能审 PSD2Live 生成的工程哪里绑错了（鬼图复盘第 0 条「绑定日志警告=前兆」的进阶版）；
3. **精修能力**：Cubism Editor PRO 42 天试用期内，用官方教程知识手工修 cmo3（PSD2Live 导出物可回官方编辑器）。

## 四、推荐执行序（决策树）

```
第 1 步（并行双轨，成本≈0）
  A 轨：魔搭 AIGC 专区/Qwen Chat 免费用 stage-main.png + 品红原型出「正面 turnaround」
        → 对比脸（阶段 4 流程）→ 质量达标则逐视图出正/侧/背
  C 轨：本机 SDXL 批次 7（对策已定，作对照组）
第 2 步：任一轨出合格三视图 → 定稿（走 docs/13 阶段 3/4 自检 + 用户验收）
第 3 步：定稿图 → see-through 拆件（ModelScope 在线版先行，docs/17 既定）
        → 用本文档 §3.1 拆件规范 + dajoong PSD 清单验收
第 4 步：PSD2Live 绑定 → 审日志（警告=前兆）→ selfcheck 隔离自检
第 5 步：用户确认 → 替换前端模型目录
第 6 步（中期）：定稿形象 + Qwen 扩图攒 20 张 → 训练希亚角色 LoRA（需 ≥8GB 显存位）
```

## 五、参考来源

- Consistent Character Creator 3.0（RunComfy 工作流页）：https://www.runcomfy.com/zh-CN/comfyui-workflows/consistent-character-creator-3-0
- CharacterSheet Multi-View LoRAs（ComfyUI Wiki，2026-07-31）：https://comfyui-wiki.com/en/news/2026-07-31-charactersheet-multiview-loras
- Character LoRA Training Locally（2026-10-19 更新）：https://locallyuncensored.com/blog/character-lora-training-local.html
- 官方插图加工教程（拆件规范）：https://docs.live2d.com/zh-CHS/cubism-editor-tutorials/psd/
- 官方 6 课教程总入口：https://docs.live2d.com/zh-CHS/cubism-editor-tutorials/top/
- Live2D JUKU 官方课：https://juku.live2dcs.jp/en/course/course-87/
- dajoong Rigging Guide：https://dajoong.cloud/en/guide/
- Qwen-Image-Edit-2511 发布文（魔搭免费体验说明）：https://developer.aliyun.com/article/1696719
- 魔搭 FlowBench 云端工作流（支持 QwenImageEdit）：https://modelscope.cn/learn/1689
- Qwen-Image-2.1 ComfyUI 原生工作流：https://docs.comfy.org/tutorials/image/qwen/qwen-image-2-1
- Qwen-Image-Edit GGUF 显存参考（16GB 推荐 / GGUF 下探）：https://resources.oreateai.com/resources/qwenimageedit2509-gguf-enables-precise-local-image-editing-on-consumer-hardware
- FLUX.2 Klein 显存参考（comfy 官方博客）：https://blog.comfy.org/p/flux2-klein-4b-fast-local-image-editing
- B站视频：BV1yjnBzmE71 / BV1Cxg2z7Edd / BV1VqCjB5EWQ / BV1YYEh6dEHa；卡米雷特课 ep524166
