# 22 · 教程深挖归档：ComfyUI 三视图方法细节 × Live2D 制作技法

> 调研日期：2026-10-28。定位：[docs/20](file:///f:/self_project/Sia-ai/docs/20_希亚Live2D推进方案_三视图新路线与Live2D教程调研.md) 是路线选型，本文是**方法细节篇**——多源教程交叉提炼出的可执行参数、指令句式、技法标准与翻车对策，不含路线论证。调研方式：两路并行检索 25+ 教程源，同一结论多源一致才可作共识；[多源一致]/[单源] 标注保留。

## 一、ComfyUI 三视图：方法细节

### 1.1 指令式编辑路线（Qwen-Image-Edit 2509/2511）

**节点链**（ComfyUI 官方模板实测一致）：`LoadImage → TextEncodeQwenImageEdit（Qwen2.5-VL 7B 编码器，吃图像输入）→ ModelSamplingAuraFlow → KSampler → VAEDecode`，VAE 用 `qwen_image_vae`，配 **Lightning 4 步 LoRA** 压到 4-8 步。官方文档：[Qwen-Image-Edit-2511 教程](https://docs.comfy.org/zh/tutorials/image/qwen/qwen-image-edit-2511)；单图转四视图有现成官方模板 ["1 Click Multiple Character Angles"](https://comfy.org/workflows/templates-1_click_multiple_character_angles-v1.0-16f123e593db/)。2511 官方明示改进：减少图像漂移、角色一致性增强。

**显存档位**：BF16 40.9GB / FP8 约 16-20GB [多源一致]。4GB 出路：① **nunchaku 4-bit + Lightning 4-8 步**（官方称最低 4GB，提速 3×；ComfyUI-nunchaku 的 `num_blocks_on_gpu=1` 估算 3-4GB）；② **GGUF Q3/Q4 + 分层 offload**（QuantStack/Unsloth 版）。

**指令措辞实战**（身份锚句是核心）：
- 阿里云[百炼官方指令指南](https://help.aliyun.com/zh/model-studio/qwen-image-edit-guide)：视角转换官方句式「得到一张正面视角的图」「脸朝左」；**多图时 prompt 编号必须与图像数组顺序一一对应**
- 身份锚句 [多源一致]：**"same outfit and appearance"**（modl.run 角色设定图指南）；完整句式 `"turn the character to show a side view profile, facing left, same outfit and appearance"` / 背面 `"turn the character around to show the back view, looking away from the viewer"`
- Floyo 工作流：指令必须以 **"image 1," 开头**才绑定到参考图
- 姿势类指令用 seed 淘汰法：3-5 个 seed 出一张干净结果属正常 [modl.run](https://modl.run/guides/character-sheet/)

**多参考图喂法**：`image_1=被编辑图`，其余为素材，prompt 用 `<image1>` 编号寻址（[官方 Qwen-Image-2.1 教程](https://docs.comfy.org/zh/tutorials/image/qwen/qwen-image-2-1)）；**参考图各司其职**（图1=身份、图2=服装），prompt 显式声明「只取图2的衣服，不取脸」[linocut]；脸部特写→全身配 F2P LoRA（fal 模型库）。

**实测基线**（[Code Crafters Corner 四视图实测](https://lilys.ai/it/notes/comfyui-20251213/comfyui-qwen-character-4-sides)）：输入 1024×1024 方图 + 极简 prompt，工作流自动抠背景、输出前后左右四张；可单视角重跑；作者自评成功率 ~90%。翻车实录：换装留旧元素（需二次编辑 pass）、侧面不足 180°（单独重生成）。

### 1.2 FLUX.1 Kontext 路线

[Kontext 一致性技巧](https://selfielabstudio.com/blog/flux1-kontext-character-consistency-tips-20260216)：结构化 prompt `"Four views of [描述], consistent face from reference, front/side/back/3/4, clean background"`；**CFG 降到 2-4** 保身份；img2img denoise 0.6-0.8；脸变→先放大参考图、只 inpaint 非脸区。另有专用 Turnaround Sheet LoRA（触发句 "create turnaround sheet of this exact character, 5 full-body poses on pure white background: front view, 3/4 left, left profile, back view, right profile, 3/4 right"）。

### 1.3 SDXL+IPAdapter+ControlNet 参数共识（4GB 原生可跑）

- **IPAdapter**：PLUS FACE preset + 脸部裁切图，weight **0.8**；scale 0.6-0.8 区间（<0.5 丢身份、>0.9 滤镜化）[多源一致：iimagined/agentbus]
- **ControlNet**：OpenPose **1.0 起步**（僵则降 0.5-0.8）；生产配方 OpenPose 0.95 + Canny 0.55（**end_percent 0.5**，跑满有描边感）；辅助锁构图 weight 0.3-0.5；总强度 <1.0 [多源一致]
- **FaceDetailer**（Impact Pack）：guide_size 512、noise_mask 开、**必须接同一身份源**（否则重绘成路人脸=伪漂移）；全身镜头脸像素太少必漂 [iimagined]
- **关键结论 [多源一致]**：一张图拼四格 grid 快但小面板脸必崩——**逐角度全尺寸分开出图**才可信；reference-only 路线已被 IPAdapter 取代
- 一致性三件套：固定 seed、简短复用的 identity 描述块、先易后难逐变量改

### 1.4 多视图 LoRA 触发词与参数表

| LoRA | 底模 | 触发词/句 | 参数 |
|---|---|---|---|
| CharacterSheet TripleView/QuadView | FLUX.2 Klein 9B | "Convert the character in the image to a Character Sheet showing front, side and back full body views" | 1536×1024、8 步、CFG 1、Euler、LoRA 1.0（[comfyui-wiki](https://comfyui-wiki.com/en/news/2026-07-31-charactersheet-multiview-loras)） |
| CharacterSheet_PosePack_HassakuXL | Illustrious（动漫向） | `(character_sheet_style:1.3), multiple view, three-quarter view, side view` | 权重 0.75-0.9、1024²、20-35 步、CFG 6-7、euler_ancestral |
| CharacterDesignIZT | Z-Image/Illustrious/FLUX/Pony | `CharacterDesignIZT` | 3 视角+色板 helper |

CharacterSheet 局限 [官方 wiki]：视图间解剖/服装可能不一致，**侧背视图常需多次生成或手动修**；训练集真人为主，动漫分布外一致性下降。HassakuXL 类输出 4-8 姿势 collage——单格分辨率低，Live2D 建模需再分切放大。另有全流程套件 [AHEKOT/ComfyUI_VNCCS](https://github.com/AHEKOT/ComfyUI_VNCCS)：三引擎可选 + Pose Studio 骨架驱动，其 Character Cloner 明确要求**全身高质量输入图，否则模型瞎编看不见的部分**。

### 1.5 翻车模式与对策表

| 翻车 | 对策 |
|---|---|
| 服装漂移（脸稳衣不稳）[多源一致] | prompt 点名服装+颜色；参考图保服装清晰 crop；指令加 "same outfit and appearance" |
| 小面板脸崩 [多源一致] | 逐角度全尺寸分开出 + detailer |
| 侧面/背面最易崩 [多源一致] | 单独重 roll 该视角，背面人工逐项检查 |
| 编辑残留旧元素 | 二次编辑 pass 定点清除，不整图重 roll |
| 编辑链代复代漂移（复印机效应） | 一切从 approved master 分支出发，不对编辑结果再编辑 |
| sheet 光影烘焙进脸 | 生成 sheet 必须无影平光纯背景 |
| Qwen 指令不绑图/多图错乱 | "image 1," 前缀；编号与数组顺序一致 |

### 1.6 对希亚项目的执行要点

1. **主路线**：Qwen-Image-Edit（2509/2511）量化版逐角度编辑，**不拼贴**。流程：先出一张批准的正面全身 hero 图（无影平光、纯色背景、空手无道具）→ 逐角度编辑（固定句式+固定 seed，每角度批量 4 张挑优），按 正面→3/4→正侧→背面 顺序，背面单独多试 seed
2. **兜底细化**：现有 SDXL+IPAdapter+ControlNet 管线——IPAdapter PLUS FACE 0.8 锁脸 + OpenPose 0.95（僵则 0.5-0.8/end% 0.85）锁姿势 + FaceDetailer；局部瑕疵 inpaint 定点修，禁止整图重 roll 和对编辑结果再编辑
3. **按 Live2D 规格验收**：每视角独立 1024+ 全尺寸；统一平光纯底；signature 细节（银白长发、红瞳、花店围裙）每次点名颜色；验收逐项对：眼距、鼻颌/下颌线、发际线、刘海分缝、体型比例、围裙系带方向——任何一项漂了即重出该视角

## 二、Live2D 制作：技法标准

### 2.1 拆件规范实操

**粒度基准** [多源一致：官方/NGA]：头发=前发/侧发(左右)/后发三大块，想动的部分（双马尾/呆毛）单独成层；后发画成「带发旋的壳」（亮部低头露头顶、暗部做头发内面 [小小巡山]）。

**眼睛**：睫毛/眼珠/眼白三分 [多源一致]；外眼角上扬部分从睫毛分出更易变形；眼白必画（兼作剪贴蒙版素材）。中文实践更细 [AAA老碇]：上眼皮(眼线+双眼皮)/上睫毛(只留睫毛尖)/下眼皮+睫毛/眼白/眼珠/瞳孔/高光（多个高光分开）。

**嘴**：上下唇分开、口内单独；**口内画得比原图大一号**，凸出部分用唇边肤色块盖住；官方建议嘴部不用剪贴蒙版而用肤色填充遮挡（大量剪贴增加嵌入负担、口内可能穿出）[官方]。嘴唇画张开状态、上下唇带一点皮肤盖得住口内 [多源一致]。

**加绘（遮挡补画）**：原则=「隐藏层之上的层遮住后，下层在重叠区仍看起完整」——脸底在头发下延伸 **50-100px**、脖子画到下巴下且够长、身体皮肤延伸到衣服下、相邻发片互相延伸 [AnimArts]。操作法：复制原图→组内建图层蒙版→在切出部件周围擦除→**加绘务必新建层**，不画在原图层上 [官方]；加绘只需基础色块明暗；切割后必须叠回原图查漏，「越小越细的部件越容易忘拆」[多源一致]。

**命名与画布**：线稿色稿合并为一层再导入；部件投影用正片叠底**单独一层**；按部位分文件夹；英文命名（`L_Eye_Iris`、`Hair_Front_01`）；画布 ≥4000×4000、RGB、图层效果栅格化（发光/叠加带不进 Editor）[多源一致]。典型拆分量 40-80 层，复杂超 100 层 [AnimArts]。

### 2.2 网格与变形器

**网格**：自动生成失败多因 PSD 残留半透明杂点——调大「视为透明的 Alpha 值」[官方]；动起来「裂开」三大原因=顶点太少/网格超出变形器范围/顶点排列不规则——补点、放大箱子、描线重划 [白乌鸦，多源一致]。顶点密度看动量：轮廓大块粗、睫毛发梢细、脸颊口周中等；睫毛/眉/嘴官方建议手动布网格。以三角形为主、避免四边形、边缘留空隙、长条形沿中线布点 [NGA]。接缝裂开用 **Glue**（Shift 选两部件→套索圈重叠区）；复制一方网格粘贴到另一方零成本对齐顶点；**Glue 要在搭变形器之前做完** [白乌鸦]。

**变形器层级（社区标准树）** [r3dhummingbird Cookbook，与官方教程互证]：
```
Body Z > Body Y > (Breath, Face Rotation, Body X, Arm L/R Rotation)
Face Rotation 内每个部件再套各自的 XY 弯转变形器
会摆动的部件（头发）：物理摆动变形器 嵌在 XY 转头变形器 里面
方形部件 2×2/3×3 弯曲、横长 3×2、竖长 2×3；旋转变形器定好初始角后冻结
```

**头部 XY**：X: −30/0/+30、Y: −30/+30 标准参数轴；先只显示轮廓部件做轮廓变形器，再逐部件补；拉变形器手柄看整体透视，别盯部件本身 [多源一致]。

### 2.3 物理与表情

**摆锤四参数典型值** [AnimArts 物理指南，与日文源同构]：
- Length（周期）10-25 / Gravity 0.5-2.0 / Damping 0.1-0.9 / Speed 1.0-3.0
- 短刘海：Length 8-12、Damping 0.4-0.6、Speed 2.0-3.0
- 长发：Length 20-35、Damping 0.2-0.4、Speed 1.5-2.0，**多节点串联让发梢摆幅>发根**
- 粗辫马尾：Gravity 1.2-1.5、Damping 0.5-0.7；耳饰 Length 3-8/Speed 2.5-3.0；呆毛 Damping 0.1-0.2
- **长物件必须 2-3 节点链，单节点整根僵动**

**工序标准**（卡米雷特 54 课目录=行业工序 [单源但完整]）：约稿沟通→原画整理→建工程/绘制顺序/网格→蒙版阴影→**眉毛→眼睛→嘴巴→表情→脸部X→Y（头部九轴）→头部物理→身体九轴→身体物理→特殊参数→动画→导出打包→面捕设置**。闭眼做法：曲线变形把素材压成一条线，开/闭两态都打关键帧 [多源一致]。

### 2.4 行业标准：价位、交付硬指标、立绘验收单

**价位↔质量（2026 国际市场）** [AnimArts/ShiraLive2D]：Lite $50-120（口型+眨眼）→ Standard $150-400（ARKit52 半身+发物理+3-5 表情）→ Premium $500-1200（全身+手部追踪+多服装+10+ 表情）→ 影视级 $1500-3500+。纯绑定比全包便宜 30-40%；国内 B 站工房一条龙 ¥1966-2666/30 天，纯建模 ¥2000（**要求自带合格拆分 PSD**）。工期：Standard 2-3 周、Premium 4-5 周。

**平台硬指标**（IRIAM 审核规范 v1.3 [单源]）：moc3 ≤10MB；贴图 ≤4 张 2048²；剪贴蒙版 ID 组合 ≤37（建议 ≤30）；单 ArtMesh ≤4 参数；AngleX −30~+30、EyeOpen 0~+1 等参数 ID/极值按标准表；贴图集内部件不重叠/出框；常见驳回=转头+张嘴时口周皮肤盖住鼻颊（绘制顺序后置或反转蒙版修）。

**立绘验收单**（米画师真实需求单）：透明底 PSD、图层命名清晰分文件夹、前/后/刘海独立、眼各部件独立、**口型 5 个（A/I/U/E/O）**、衣物与手臂关节分离、遮挡关系清晰。

### 2.5 翻车模式与对策表

| 翻车 | 对策 |
|---|---|
| 转头露底/裂缝 | 加绘缺失→脸底/脖/身按 50-100px 余量补画 |
| 口内/眼白穿出 | 口内画大一号+唇边肤色填充 |
| 动作拉扯变形 | 补顶点、放大变形器箱子、描线重划 |
| 接缝裂开 | Glue 或复制粘贴网格法，变形器之前做 |
| 头发甩进脸/穿模 | 减输出范围、加蒙版 |
| 物理抖动 | 降 Speed / 加 Damping / 输入平滑 |
| 左右摆动不同步 | 对称部件参数镜像严格一致 |
| 关键帧诡异（缩→旋→放大） | 直接旋转曲面变形器所致→改用旋转 Deformer 做 Z 轴 |
| 贴图集穿帮 | Validate placement + 按显示优先级排布 |
| 整体僵硬像截图 | 只有部件动五官不动→转头时五官同步位移 |

### 2.6 对希亚项目（see-through 自动拆件 + PSD2Live 自动绑定）的 3 条关键提醒

1. **自动拆件后必须跑「遮挡完整性」人工审计**：see-through 按像素边界切件，最不可靠的恰是社区共识中最该加绘的地方（眼白、口内大一圈、脖子延长、脸底 50-100px、发片互延）——「隐藏上层逐层检查下层完整性」设为固定验收步骤；部件间投影放正片叠底独立层，否则自动绑定后阴影随件乱飞
2. **自动绑定的变形器树向社区标准结构收敛**：对齐 §2.2 标准树 + 官方标准参数 ID/极值（决定能否接面捕平台）；**Glue（轮廓↔皮肤、发际↔地肌）务必在套变形器前人工补做**，自动工具通常不处理接缝
3. **网格精修只花在动量大的地方**：自动网格对大色块够用，人工精修集中打在睫毛/发梢/口周；贴图集 ≤2048×4、moc3 ≤10MB、剪贴蒙版 ≤30、单网格 ≤4 参数——**精修前校验**而非导出后

## 三、主要来源

- ComfyUI 官方：[Qwen-Image-Edit-2511](https://docs.comfy.org/zh/tutorials/image/qwen/qwen-image-edit-2511) / [Qwen-Image-2.1](https://docs.comfy.org/zh/tutorials/image/qwen/qwen-image-2-1) / [四视图模板](https://comfy.org/workflows/templates-1_click_multiple_character_angles-v1.0-16f123e593db/)
- 指令式编辑实战：[百炼指令指南](https://help.aliyun.com/zh/model-studio/qwen-image-edit-guide) / [modl.run 角色设定图](https://modl.run/guides/character-sheet/) / [RunComfy MultiAngles](https://www.runcomfy.com/zh-CN/comfyui-workflows/qwen-edit-2509-multipleangles-in-comfyui-multi-angle-image-generator) / [Floyo](https://www.floyo.ai/workflows/dynamic-camera-control-for-your-imag-2fn800hyn93q) / [Code Crafters Corner 实测](https://lilys.ai/it/notes/comfyui-20251213/comfyui-qwen-character-4-sides)
- SDXL 路线：[iimagined 一致性工作流](https://iimagined.ai/blog/comfyui-consistent-character-workflow) / [agentbus](https://agentbus.sh/posts/how-to-generate-consistent-characters-across-ai-images/) / [fal.ai](https://fal.ai/learn/tools/ai-character-consistency)
- LoRA：[comfyui-wiki CharacterSheet](https://comfyui-wiki.com/en/news/2026-07-31-charactersheet-multiview-loras) / [ComfyUI_VNCCS](https://github.com/AHEKOT/ComfyUI_VNCCS)
- Live2D 官方：[插图加工(PSD)](https://docs.live2d.com/zh-CHS/cubism-editor-tutorials/psd/) / [素材拆分](https://docs.live2d.com/zh-CHS/cubism-editor-manual/divide-the-material/) / [网格](https://docs.live2d.com/zh-CHS/cubism-editor-manual/mesh-edit/) / [脸部XY](https://docs.live2d.com/zh-CHS/cubism-editor-tutorials/xy/)
- Live2D 社区：[AnimArts PSD Prep](https://animarts.studio/blog/prepare-psd-file-live2d-rigging) / [AnimArts 物理指南](https://animarts.studio/blog/live2d-physics-hair-clothes-guide) / [白乌鸦 Mesh 与 Glue](https://shiroikarasu.net/live2d-mesh-glue-guide/) / [Cubism Cookbook 变形器树](https://r3dhummingbird.gitbook.io/live2d-cubism-cookbook/modeling-and-rigging/deformer-hierarchy) / [NGA 手册](https://nga.178.com/read.php?tid=25357826) / [AAA老碇拆分](https://m.bilibili.com/opus/704623933748412435) / [小小巡山 30min](https://m.bilibili.com/opus/744981271905566787)
- 行业：[AnimArts 价格指南](https://animarts.studio/blog/live2d-model-cost-pricing-guide) / [IRIAM 审核规范 v1.3](https://assets.super.so/13eb03f0-5017-4dd2-9bac-db5250517df0/files/cf41bb89-6610-4bbd-a88a-08b30a264583/IRIAM_Live2D_guidelines_for_US_ver.1.3.0.pdf) / [米画师需求单](https://www.mihuashi.com/projects/12728276) / [卡米雷特建模指南](https://www.bilibili.com/cheese/play/ep524166)
