# 21 · 魔搭 Qwen-Image-2.1 出图实操情报（A 轨执行手册）

> 记录日期：2026-10-28。来源：本日浏览器实操 + 模型卡研读。上位文档：[docs/20_希亚Live2D推进方案_三视图新路线与Live2D教程调研.md](file:///f:/self_project/Sia-ai/docs/20_希亚Live2D推进方案_三视图新路线与Live2D教程调研.md)（路线选型）。
> 效力：A 轨（Qwen-Image-Edit 云端出三视图）每次执行前先读本文档，避免重踩。

## 一、魔搭 AIGC 专区结构（实测）

- 入口：`https://modelscope.cn/aigc`（首页 composer 直接可用）+ 模型详情页 `https://modelscope.cn/aigc/models/Qwen/Qwen-Image-2.1`（页内有「一键生成」入口，点开右侧生成面板）
- **登录墙**：未登录时点生成/一键生成会弹登录框（密码 / 短信验证码均可）。2026-10-28 用户已登录。
- **魔粒系统**：登录奖励每日 +200，当前余额 50；提示「平台魔粒需在个人信息完善后方可使用」——生成若报额度错误，先检查个人信息/邮箱是否已验证（页内有「立即验证」按钮）。
- 首页 composer 默认模型 Z-Image-Turbo，下拉可切：Z-Image-Turbo / FLUX.1-dev / FLUX.2-dev（均标「千问·平台调用免费」）+「查看更多」全量列表；模型详情页选 Qwen-Image-2.1 后「一键生成」面板才是我们的目标位。
- **生成面板能力**（Qwen-Image-2.1）：上传区「点击上传或拖拽图片到这里」，**最多 10 张参考图像**；prompt 用 textarea；有比例选项（1:1 / 4:3 / 3:4 / 16:9 / 9:16 / 1:2）与 Agent 模式 / 自定义模式切换。
- Token 页：`https://modelscope.cn/my/settings/token`（最多 10 个令牌）；API-Inference 文档入口 `/docs/model-service/API-Inference/intro`。用户已有 3 个令牌（default / image_use / DIfy_文生图）。

## 二、Qwen-Image-2.1 模型卡要点（2026.10.09 发布）

- 统一生成+编辑模型：**视觉生成组件仅 70 亿参数（32 层单流 DiT）**，仓库总参 16.2B；Qwen 研究许可协议（注意商用限制）。
- **多功能编辑**：支持最多 10 张参考图像，可用圆形区域、手绘标注、独立遮罩指定局部编辑区域，**保留人物和产品身份特征**——正是三视图生成需要的核心能力。
- 原生 RGBA 透明图生成（特定提示词格式）——对 Live2D 拆件前的抠图环节可能是捷径（待验证）。
- 官方宽高比表（diffusers）：
  | 比例 | 分辨率 |
  |---|---|
  | 1:1 | 2048×2048 |
  | 4:3 | 2400×1792 |
  | 3:4 | 1792×2400 |
  | 3:2 | 2528×1696 |
  | 2:3 | 1696×2528 |
  | 16:9 | 2752×1536 |
  | 9:16 | 1536×2752 |
- diffusers 用法：`QwenImage21Pipeline.from_pretrained("Qwen/Qwen-Image-2.1", torch_dtype=torch.bfloat16).to("cuda")`；内存优化 `pipe.enable_model_cpu_offload()`（Notebook/大显存机用）。
- Demo 空间：https://huggingface.co/spaces/Qwen/Qwen-Image-2.1 ；GitHub：QwenLM/Qwen-Image-2.1。
- 模型页显示 API-Inference 状态为「**待机态**」（beta）——首次调用可能触发冷启动唤醒，耗时较长属预期。

## 三、API-Inference 调用情报（待令牌到手后验证）

### 2026-10-28 API 实测结论（两张实跑后定论）

- **邮箱验证后 API 跑通**：`Qwen/Qwen-Image-Edit` 提交即 `task_status:SUCCEED` 返回 task_id，~30s 出图（无冷启动）；`image` 字段 = data_url 单图即可（形态 A 一次过）
- **❌ v1 Edit 走 API 做全身视角重构，身份保持不可用**（实锤过程）：
  - 第 1 张（ms3v_front_163915，弱指令）：姿势/解剖/构图全对（中立站姿模板完美），但花店围裙整套丢失→素色连衣裙、红瞳大圆眼→灰棕杏眼、厚涂→平涂
  - 第 2 张（ms3v_front_164505，强编辑指令）：更糟——粉发+绿吊带长裙+赤脚+编造 choker，与参考图（银白发/绿毛衣/白围裙裙/黑鞋，本批"品红"指批次名非发色）零关系，且与第 1 张互相矛盾
  - 定性：v1 Edit 强项是局部编辑（改背景/换色/去物），「视角重构+严格身份保持」是 2509/2.1 的能力，二者均不在免费 API 列表 → **API 免费位此路不通，别再烧额度试 prompt**
- **⚠️ 内容审核坑**：payload 带 `negative_prompt` / `true_cfg_scale` 必被 400「Input data may contain inappropriate content」拦（裸 prompt 同图同指令就过；400 不建任务不烧额度）。API 版干脆不传这俩参数
- **魔粒消耗**：2 次成功任务，余额待查（起步 50 + 每日 200）
- 执行脚本留档：[sia_out/ms_qwen_edit.py](file:///f:/self_project/Sia-ai/sia_out/ms_qwen_edit.py)（gen/probe、--no-opt、失败不自动重试）；产物在 sia_out/ms_out/（两张反面样本留档）
### 2026-10-28 Notebook 全自动路线探测进展（用户拍板「全自动」后，交接状态）

**已确认情报**：
- 魔搭 Notebook 新用户 **100 小时免费 GPU** + 不限时免费 CPU（官方快读页）；另有 AMD ROCm 免费笔记本社区帖证实可跑大模型推理
- **JupyterLab 自带 REST API**（`/api/kernels` 执行代码、`/api/contents` 读写文件含 base64）→ 拿到 JupyterLab URL（内含 token）即可**本机全自动**：传参考图→跑 diffusers→拉产物，无需浏览器
- 社区帖 435314：Notebook 容器内可自建 SSH（SCP/SFTP 全通，需 Tailscale 打通）；435302：JupyterLab 网页可被自动化控制（xterm.js 可 type_text）——均备用
- 前端 bundle（`g.alicdn.com/sail-web/maas/2.13.170/umi.js`）grep 出实例管理真实路由：`/api/v1/notebooks`（曾 500，路径存在缺参数）、`/v1/notebooks/specs`、`/v1/notebooks/image|image/recommend`、`/v1/notebooks/paid/{list,get,open,open/check,start,stop,url}`、`/v1/notebooks/stop`；UI 路由 `/my/mynotebook`

**待验证（下一步）**：
1. 跑 [sia_out/ms_notebook_probe.py](file:///f:/self_project/Sia-ai/sia_out/ms_notebook_probe.py)（交接脚本）：Bearer 令牌能否过实例管理 API——**网页端可能走 cookie 会话**，若 401/重定向则令牌路线止步
2. Bearer 不通 → **主线降级**：用户网页开 GPU 实例（100h 免费额度内，显存挑最大）→ 把 JupyterLab 地址栏 URL（含 token）发回 → Jupyter REST API 全自动接管
3. 实例环境探测（GPU 卡型/显存/torch）→ 定模型：**2509（QwenImageEditPlusPipeline，多图+身份强化）vs 2.1（QwenImage21Pipeline）**，模型 30-40GB 走魔搭内网下载快
4. 出正面视图 → docs/13 阶段 1-4 自检

**措辞情报**（docs/22 §1.1 提炼，出图时用）：身份锚句 "same outfit and appearance"；多图必须 "image 1," 前缀绑定；多参考图各司其职（图1=身份/图2=服装）+ prompt 显式「只取图2的衣服不取脸」；逐角度分开出不拼贴；seed 淘汰法 3-5 发属正常。

## 交接状态快照（2026-10-28 晚，智能体积分将尽，供后续接手）

- **A 轨（云端三视图）**：API 免费位已定性不可用（见上）；Notebook 全自动路线停在「鉴权探测」步——执行序见上节待验证 1→4。token 在 `sia_out/_ms_token.txt`（gitignore）。实测脚本 `sia_out/ms_qwen_edit.py`（API 位）、`sia_out/ms_notebook_probe.py`（Notebook 位）。反面样本 `sia_out/ms_out/` 两张（身份漂移铁证，别再试 v1 API 视角重构）
- **C 轨（本机批次 7）**：GPU 被 SoVITS 训练占（PID 5884），等空闲；对策见 §六
- **教程调研**：已完成归档——路线选型 [docs/20](file:///f:/self_project/Sia-ai/docs/20_希亚Live2D推进方案_三视图新路线与Live2D教程调研.md)、方法细节 [docs/22](file:///f:/self_project/Sia-ai/docs/22_教程深挖归档_ComfyUI三视图方法与Live2D技法.md)（25+ 源交叉，含 4GB 可跑方案、身份锚句、Live2D 拆件/变形器/物理参数表、IRIAM 硬指标）
- **复盘锚点**：Live2D 链路与鬼图教训在 [docs/17](file:///f:/self_project/Sia-ai/docs/17_Haru级Live2D制作路线调研.md)；出图自检体系在 [docs/13](file:///f:/self_project/Sia-ai/docs/13_生图全流程自检体系.md)

### 原始调用形态备忘（预期，需实测校准）

  - base_url `https://api-inference.modelscope.cn/v1`，Authorization: Bearer <令牌>
  - 图像生成：`POST /v1/images/generations`（openai images 接口形态）
  - 大模型走异步：请求头 `X-ModelScope-Async-Mode: true` 提交拿 task_id → 轮询 `GET /v1/tasks/{task_id}`（头 `X-ModelScope-Task-Type`）→ 结果为 OSS 临时 URL，需及时下载
- 若 `image` 字段两形态都被拒，备选按序：
  1. 备选 A：**魔搭免费 Notebook**（「Open in Notebook」入口，免费 GPU 配额，跑完整 diffusers 多图编辑管线，数据不出平台）
  2. 备选 B：网页生成面板手动传图（自动化不可行，见 §四）
  3. 备选 C：阿里云百炼 DashScope qwen-image-edit API（付费但便宜，`MultiModalConversation.call` messages 格式，支持 base64/公网 URL，含免费额度）——格式见 help.aliyun.com《Qwen-Image-Edit 使用指南》
- ⚠️ SPA 陷阱：modelscope.cn 的 docs/posts 页面是前端渲染，**WebFetch 只能抓到壳**，正文要用浏览器读或找站内帖子的 Notebook 源。

## 四、浏览器自动化踩坑实录（2026-10-28，browseruse 操作魔搭）

1. **ant-upload 隐藏 file input 拿不到 ref**：`input[type=file]` 隐藏（offsetParent=null），snapshot 无论怎么过滤都返回 0 节点 → `browser_upload_file` 无 ref 可用。
2. **点击上传区会弹 Windows 原生文件选择框**，自动化无法驱动：此后 snapshot 直接报错（modal state 阻塞）——**结论：网页上传参考图这条路对自动化不可行**，上传环节要么用户手动、要么走 API/Notebook。
3. **坐标点击要用 getBoundingClientRect 现算**：snapshot 报的 scroll 值可能滞后（实测显示 scroll=0 实际已滚 967px），直接用 snapshot 的 viewport 坐标算 offset 会点到屏外（报 "coordinates outside the visible viewport"）。先 `evaluate` 拿目标与锚元素的相对坐标再 click。
4. **用户接管浏览器后 webview 会 detach**：恢复手段 = `browser_navigate({url, newTab: true})` 开新标签重新加载，旧引用全失效。
5. **evaluate 里正则转义**：`\d` 等写进 script 字符串时注意转义层级，报 SyntaxError 会连带整个 evaluate 失败。
6. 模型详情页的「一键生成」按钮是嵌套 span（无 button/a 包装），a11y 树不暴露——只能 evaluate 找 span 后点其父元素。

## 五、三图基准（A 轨输入，用户定的长期规则）

| 用途 | 文件 |
|---|---|
| 面部基准（脸型/五官不得改） | `f:\self_project\Sia-ai\frontend\public\avatars\stage-main.png` |
| 品红原型 00001（黑丝版全身） | `f:\self_project\Sia-ai\sia_out\sia_char_magenta_00001_.png` |
| 品红原型 00002（围裙版全身，花店服装） | `f:\self_project\Sia-ai\sia_out\sia_char_magenta_00002_.png` |

出图指令要点（沿用 docs/13 多视图姿势模板规范）：中立站姿、双臂自然垂放离身一拳、手指自然微曲、双腿微分、发梢止于腰、背面露出 X 背带、三视图等高对齐；逐视图生成优先于一张挤三视图。

## 六、环境互斥备忘

- 本机 GPU = GTX 1050 Ti 4GB（1050 Ti 4GB + 16GB RAM，2026-10-28 实测），与 GPT-SoVITS 训练互斥：2026-10-28 SoVITS runtime 占卡（PID 5884，15:34 启动）期间批次 7 出图挂起，等训练结束或用户点头再跑。
- C 轨批次 7 对策不变：白裤袜正面 `(white pantyhose:1.35)` 前置、`(ragged hem:1.3), (torn cloth:1.3), (apron train:1.3)` 负面、`(pure side view, profile silhouette:1.2)`、IPAdapter end_at 0.7 保持。
