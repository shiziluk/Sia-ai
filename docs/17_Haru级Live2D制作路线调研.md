# Haru 级 Live2D 制作路线调研

> 调研日期：2026-10-13。目标：让希亚拥有与官方 Haru 同级的真 Live2D 形象（当前前端跑的是官方 Haru 运行时文件占位）。
> 关联文档：[docs/08_Live2D升级调研与实施清单.md](file:///e:/self_project/Sia-ai/docs/08_Live2D升级调研与实施清单.md)（早期调研）、[docs/12_假Live2D驱动调研与实施清单.md](file:///e:/self_project/Sia-ai/docs/12_假Live2D驱动调研与实施清单.md)、[docs/13_生图全流程自检体系.md](file:///e:/self_project/Sia-ai/docs/13_生图全流程自检体系.md)（三视图底图迭代）。

## 一、Haru 模型解剖（本地文件分析结论）

本地 `frontend/public/live2d/haru/` 只有**运行时文件**，没有可编辑源文件：

| 文件 | 作用 |
|---|---|
| `haru_greeter_t03.moc3` | 编译后的模型（不可逆向编辑） |
| `texture_00/01.png` | 2×2048 贴图集 |
| `physics3.json` | 4 组摆锤物理（前发/侧发/后发/围巾，全部由 AngleX/Z + BodyAngle 驱动） |
| `pose3.json` / `cdi3.json` | 姿势/显示信息 |
| `expressions/F01-F08.exp3.json` | 8 个表情差分 |
| `motions/` | Idle + Tap×2 动作 |
| Groups | EyeBlink（ParamEyeLOpen/ROpen）、LipSync（ParamMouthOpenY） |

**关键结论**：官方在 [Haru 示例页](https://www.live2d.com/zh-CHS/learn/sample/haru/) **免费发放 .cmo3 工程源文件**（含物理/姿势/表情/动作/换装；一般用户与小规模企业可商用）。[Haru receptionist 版](https://www.live2d.com/zh-CHS/learn/sample/haru-receptionist/) 额外附**「划分素材前后」教学 PSD**——专门示范 Live2D 部件拆层的 PSD 结构。

### 完整制作链条

```
分层 PSD（部件拆解 + 遮挡补画） → Cubism 绑定（网格/变形器/参数/物理） → 导出 moc3 → 前端渲染
```

我们卡的是前两步；末端管线（pixi-live2d-display）已通，换 model3.json 文件族即可。

### Cubism Editor 版本约束

- **FREE 版**：可打开 PRO 级文件（如 Haru）查看学习、部分编辑，但**不能保存/导出**
- **PRO 版**：42 天全功能试用；试用期内可用官方素材分割 PS 插件
- 官方 6 课基础教程（[docs.live2d.com/cubism-editor-tutorials](https://docs.live2d.com/zh-CHS/cubism-editor-tutorials/)）：插图处理（PSD 拆件规范）→ 准备运动 → 表情 → 变形器 → XY 头部 → 动画；教程用 Hiyori Momose 素材免费下载

## 二、GitHub 调研到的关键工具

| 工具 | 作用 | 对本项目的价值 |
|---|---|---|
| [see-through](https://github.com/shitagaki-lab/see-through)（SIGGRAPH 2026） | **单张动漫图 → 自动拆成 23 层带补画的分层 PSD**（LayerDiff 3D + Marigold 深度 + SAM 身体解析） | 直接解决「拆件」这个最脏的活；**README 明确支持 8GB 显存 NF4 量化管线**（`inference_psd_quantized.py`，~8GB peak VRAM @1280）；另有 [ComfyUI 节点版](https://github.com/jtydhr88/ComfyUI-See-through)（本机已装 ComfyUI）；国内可用 [ModelScope 免费在线 demo](https://modelscope.cn/studios/ljsabc/See-Through)（分辨率更高） |
| [PSD2Live](https://github.com/tsunehimatoi/psd2live)（GPL-3.0/MIT） | **分层 PSD → 自动绑定**：识别中/英/日/韩图层名，自动生成网格、变形器链、五官参数、待机/眨眼/点头动作、头发物理与布料模拟，**一键导出 moc3/cmo3**（Cubism 3.0–5.3）、VTube Studio、网页、游戏引擎 | 解决「绑定」这个学习曲线最陡的活；Windows 便携版免安装；**内置 MCP 服务（180+ 操作）——助手可直接通过 MCP 读写工程**；支持命令行 `--input xxx.psd --output`；导出的 cmo3 可回官方编辑器精修；PSD 命名规范见其 `docs/zh/spec/PSD_LAYER_SPEC.md` |
| [官方素材分割 PS 插件](https://www.live2d.com/zh-CHS/cubism/download/material-separation-ps-plugin/) | 官方半自动拆件（AI 裁剪/填充/扩展，非扩散模型） | 需 Photoshop 2024/2025 + PRO 许可（42 天试用期内可用），质量上限最高的人工路线 |
| [Anime2.5DRig](https://852wa.github.io/Anime2.5DRig/) | 浏览器把分层 PSD 直接变成会眨眼/口型/头发物理的 2.5D 形象 | 免安装快速预览拆件质量；图层命名兼容 see-through 输出 |
| [PNGAL](https://github.com/1mm-module/PNGAL) | Windows 一键：PNG → see-through 拆 PSD → 眨眼/口型/摇摆 → 导出 PSD/WebM/GIF/精灵表 | 自带便携 Python + ComfyUI + 模型全家桶，参考其工程化做法 |
| [Eikanya/Live2d-model](https://github.com/Eikanya/Live2d-model) | 3400+ 游戏提取的 Live2d-model 模型库 | 参考商业模型的参数/物理结构（注意 LICENSE，勿商用） |

> see-through 官方自评：**不是完整 Image-to-Live2D**（绑定/艺术意图未覆盖），但作为「拆件+补画」起点可省掉最繁琐的人工部分——与 PSD2Live 组合正好补全链条。

## 三、推荐路线（混合方案，成本最低）

1. **学习期（立即可做，全免费）**：下载官方 Haru cmo3 源 + receptionist 教学 PSD，用 FREE 版 Editor 打开研究结构；跟官方 6 课教程（Hiyori 素材）
2. **素材底图（进行中）**：v10 批次迭代到三视图定稿（批次 5 的 [sia_3v10_apron_00018_.png](file:///e:/self_project/Sia-ai/sia_out/sia_3v10_apron_00018_.png) 接近合格；批次 6 动 IPAdapter end_at 治发长）
3. **拆件**：定稿图喂 see-through（本地 NF4 量化 / ModelScope 在线）→ 23 层分层 PSD → 层名对齐 PSD2Live 命名规范（含遮挡补画是自动的）
4. **绑定**：PSD2Live 一键生成初版（含眨眼/口型/点头/头发物理——对标 Haru 的四组发物理）→ 助手通过其 MCP 直接精修 → 导出 moc3/cmo3
5. **接入**：导出的 model3.json 文件族替换前端 haru 目录——pixi-live2d-display 管线已通，换文件即完事
6. **精修兜底**：质量不满意时，PSD2Live 导出的 cmo3 在 Cubism Editor PRO（42 天试用）手工精修，两条路互通

## 四、待办（按顺序）

- [x] 下载官方 Haru cmo3 源文件 + receptionist 教学 PSD（学习素材）——已存 live2d_study/haru*（含 41.9MB 部件拆分教学 PSD）
- [x] 安装 PSD2Live（Windows 便携版）+ 通读其 PSD 命名规范——v3.4.4 已解压 live2d_study/tools/psd2live（CLI 可用，中文乱码但参数齐全）
- [ ] 三视图定稿（v10 批次继续，见 docs/13 批次记录）
- [ ] see-through 拆件实测（先拿 00018 这类接近合格的图试跑，ModelScope 在线版零安装先行验证）
- [ ] PSD2Live 自动绑定 → 导出 → **隔离预览自检通过后** → 前端替换 haru 目录

## 五、初步尝试实录（2026-10-14）

### ✅ 验证通过的环节
- PSD2Live CLI 一次跑通官方教学 PSD（haru_受付スーツ_素材分け_t07.psd，41.9MB）：
  产出 13 文件 = moc3(945KB) + cmo3(43MB，可回官方编辑器精修) + cdi3/physics3 + 4 组动作（idle/blink/nod/shake）+ atlas 8192×2 页
- model3.json 结构标准（EyeBlink/LipSync 组齐全），pixi-live2d-display 兼容性理论无问题

### ❌ 渲染"鬼图"问题（用户实机发现，已回滚）
- 现象：切 MODEL_URL 热更新到前端后渲染崩坏成鬼图
- 直接原因：教学 PSD 是给人看层结构的参考件，层名日文+非规范结构——PSD2Live 已警告"缺 face 图层/检测到同名图层/MOC3 隐藏层被省略"，对非 see-through 命名规范的 PSD 自动绑定质量不可用
- 根因：跳过了"三视图定稿 → see-through 拆件（规范命名 23 层）"这两步前置，直接拿教学 PSD 试绑定
- 处置：MODEL_URL 已回滚 Haru、public 下的测试模型已删除

### 🔬 鬼图根因实锤（2026-10-14 深夜自检页闭环复测，用户零暴露）
1. **重跑绑定产出 → 自检页截图**：loaded 成功但渲染确认崩坏——头部黑色团块缺失、
   双臂重影（多只手臂）、裙摆腿部错位（问题样本存 live2d_study/ghost_sample.png，
   仅留档不外显）
2. **根因链 = 喂错料，不是工具坏**：
   - 教学 PSD 的层结构（日文层名/同名影子层组/缺 face 层）不符合 PSD2Live 的
     PSD_LAYER_SPEC 规范 → 同名"影"层被当成独立部件重复绑定 → **肢体重影**
   - 面部层与头发层范围交叠 + 隐藏 Drawable 被 MOC3 导出省略（绑定日志两条警告）
     → **头部 mesh 缺失成黑块**
   - 三个警告在绑定日志里全部出现过，当时未足够重视——**绑定日志的警告=鬼图前兆，
     以后绑定完先审日志再截图**
3. **自检工具链踩坑三连修**（selfcheck.html 最终可用版）：
   - ① 库版本必须与前端一致：`@jannchie/pixi-live2d-display` + pixi.js 8
     （CDN 上的 pixi-live2d-display@0.4.0 是老版配 pixi 7，不通用）；
     lib 副本已存 live2d_study/lib/
   - ② 只能用 `cubism4.min.js` 子包——主入口 index.min.js 强制依赖 Cubism 2
     runtime，纯浏览器加载后 PIXI.live2d 是空壳（前端 Live2dStage.vue 注释早有提醒）
   - ③ **UMD 里引用 `process.env.NODE_ENV`，纯浏览器无 process 直接 ReferenceError
     崩掉整库**——必须在加载前垫 `window.process = { env: { NODE_ENV: 'production' } }`
     （vite 项目里 npm import 时被 define 替换所以从没暴露过）
   - 初始化写法 pixi 8：`new Application()` + `await init()` + `app.canvas`
4. **自检闭环验证有效**：本轮鬼图完全被隔离在自检页内，未触达用户页面——固化规则
   第一条的价值已实证

### 📌 固化规则（用户指示，每次生成模型后必须执行）
0. **先审绑定日志**：绑定日志里出现"缺 face 图层/同名图层/MOC3 隐藏层省略"类警告 = 鬼图前兆，直接判不合格重做上游（拆件质量），不进截图环节
1. **生成后必检**：新模型渲染结果必须先在隔离预环境（selfcheck.html）确认是正常图——**判定标准：完整人物、无头部黑块、无肢体/部件重影、无结构错位**；确认正常前绝不展现给用户，也绝不改前端 MODEL_URL
2. **不正常 → 查问题 → 留档到本节 → 删掉产出 → 重新生成**，与 docs/13 生图批次规则同构
3. **隔离预览**：selfcheck.html（live2d_study 下，`python -m http.server 8899` 后访问 `?v=N&dir=模型目录`）——**禁止直接改主配置 MODEL_URL**（热更新会让崩坏模型直接出现在用户页面上，已实证两次）
4. 自检通过才允许替换前端模型目录

### 预览页
- [x] live2d_study/preview.html 已建（pixi-live2d-display CDN + 目录选择 + Blob URL 相对引用改写）。用法：`npx serve live2d_study` 起静态服务 → 浏览器打开 preview.html → 选择待检模型目录 → 自检眨眼/点头/拖拽。**注意 file:// 下 fetch 受限，必须经 HTTP 打开**
