# 06 ChatGLM3-6B 评估备忘录（重构后处置建议）

> 评估时间：2026-10-09 · 结论：**建议删除，可安全移除**（执行前待用户确认）

## 1. 评估背景

原始要求：「关于 ChatGLM3-6B 这个本地模型，暂不纳入当前重构范围；项目重构后是否还需要，不需要的话到时再删除。」

重构（Phase 0~3）已全部完成，本文档是对该模型的正式评估。

## 2. 新架构对 ChatGLM3-6B 的依赖情况

**零依赖。** 新后端 LLM 双通道设计（见 docs/02_详细设计.md §4）：

| 通道 | 实现 | 角色 |
|------|------|------|
| 本地主力 | Ollama + `qwen3.5:4b`（约 2.4 GB） | 日常对话、情绪判定、记忆改写 |
| 在线备用 | dashscope HTTP 直调 qwen 系列 | 本地不可用时自动回退 |

- 全部 142 个测试在 MockProvider 下通过，代码库中无任何 ChatGLM/GLM 引用（可全局搜索验证）。
- Ollama 方案对比 ChatGLM3-6B 本地部署的优势：模型体积小 5 倍、自带并发服务进程、换模型只需 `ollama pull`，无需 Python 推理脚本。

## 3. 磁盘残留现状

| 位置 | 内容 | 大小 | 状态 |
|------|------|------|------|
| `D:\pythonpro\ChatGLM3-6B\` | 模型权重（safetensors 等） | **11.6 GB** | 无任何代码引用 |
| `_legacy\历史文件\local_glm.py` / `glm.py` / `download_local_model.py` | 历史调用脚本 | < 10 KB | 已随项目留档进 Git，无需保留模型即可追溯 |

模型来源：`download_local_model.py` 通过 ModelScope `snapshot_download` 下载至 `cache_dir=D:\pythonpro`。

## 4. 处置建议

**删除 `D:\pythonpro\ChatGLM3-6B\`（释放 11.6 GB）。**

- 如日后需要：ModelScope（`ZhipuAI/chatglm3-6b`）或 HuggingFace（`THUDM/chatglm3-6b`）可随时重新下载，无不可恢复风险。
- 简历技能关键词不受影响——该经历由 `_legacy` 中的脚本与文档佐证，与模型权重文件无关。

## 5. 移除操作清单（待确认后执行）

```powershell
# 1. 删除模型目录（约 11.6 GB）
Remove-Item "D:\pythonpro\ChatGLM3-6B" -Recurse -Force
```

无需清理注册表/环境变量（模型目录为纯文件，无安装项）。
