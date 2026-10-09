# 希亚 AI 女友项目重构计划（ai小助理开发计划 → workspace 规范化改造）

## Context（背景）

- **源项目**：`D:\pythonpro\pythonpro3.13\ai小助理开发计划` —— 即「希亚 - 我的AI女友」项目（`xia-ai\manifest.json` 中 PWA 名称坐实同一项目）。
- **历史脉络**：本地 ChatGLM3-6B 跑通（local_glm.py/glm.py，路径硬编码 `D:\pythonpro\ChatGLM3-6B`）→ 切阿里云 qwen-plus API（AI核心逻辑_v1）→ chromadb 长期记忆 → 希亚人设定稿（V3-V5）→ 语音朗读/夜间模式（V6-V7）→ Streamlit 单体 + PWA（xia-ai\AI女友_V9.py）→ 角色档案/用户画像/主动目标/动态 prompt/情绪引擎（立绘化与pwa支持\AI女友_V13.py）。
- **问题**：无 git、无测试、无日志、单文件巨石脚本、UI 与业务强耦合、API key 硬编码、历史版本靠复制文件夹管理。
- **用户决策**：
  1. 功能基线 = **V13 全功能**（对话+记忆+人设画像+主动目标+情绪/夜间模式+语音+生日彩蛋+PWA+立绘）
  2. LLM = **双通道**：本地 Ollama（qwen3.5:4b，主力）+ 在线 qwen-plus API（备用），统一 Provider 接口，本地优先、故障自动切换
  3. 存储 = **SQLite（结构化）+ 内嵌向量库（记忆检索）**
  4. ChatGLM3-6B **暂不动**：重构完成后评估价值，无用再安全移除（含模型目录 11.6GB）
- **交付标准**：源代码、详细设计文档、API 文档、测试报告、部署说明；单元+集成测试覆盖率 ≥ 80%；代码规范、注释完善。

## 目标目录（迁移到 d:\workspace\xia-ai）

```
d:\workspace\xia-ai\
├── backend\
│   ├── app\
│   │   ├── main.py               # FastAPI 入口 + CORS + 统一异常处理
│   │   ├── core\
│   │   │   ├── config.py         # pydantic-settings 读 .env（密钥不进 git）
│   │   │   └── logging.py        # 结构化日志（ RotatingFileHandler）
│   │   ├── providers\
│   │   │   └── llm.py            # LLM 双通道：OllamaProvider / QwenApiProvider，统一 chat() 接口，本地优先+超时降级
│   │   ├── services\
│   │   │   ├── chat.py           # 对话编排：动态 system prompt、情绪引擎、生日彩蛋、上下文组装
│   │   │   ├── memory.py         # 长期记忆：写入/向量检索/注入
│   │   │   ├── persona.py        # 角色档案 + 用户画像 + 主动目标系统
│   │   │   └── tts.py            # 语音朗读（按 V13 原实现移植）
│   │   ├── db\
│   │   │   ├── models.py         # SQLAlchemy ORM：conversations / messages / persona_profile / user_profile / goals / memories
│   │   │   └── vector.py         # 向量记忆库（sqlite-vec 优先；不可用则 chromadb 嵌入式）
│   │   └── api\
│   │       └── routes\           # chat / memories / persona / tts / health（RESTful）
│   ├── tests\                    # pytest：unit + integration，--cov-fail-under=80
│   ├── requirements.txt
│   └── .env.example
├── frontend\
│   ├── src\
│   │   ├── api\                  # axios 封装 + 拦截器（错误统一提示）
│   │   ├── components\           # ChatBubble / CharacterSprite(立绘) / MemoryPanel / EmotionBadge / InputBar / TypingIndicator
│   │   ├── composables\          # useChat / useTTS / useTheme(夜间模式)
│   │   ├── stores\               # Pinia：chat / persona / settings
│   │   └── views\                # ChatView / SettingsView(档案与目标管理)
│   ├── package.json              # Vue3 + Vite + Pinia + vue-router + vite-plugin-pwa
│   └── .eslintrc / .prettierrc
├── docs\
│   ├── 01_项目现状评估.md         # Phase 0 产出：时间线+技术债务+重构必要性
│   ├── 02_详细设计.md             # 架构图、模块职责、数据模型、LLM 双通道切换策略
│   ├── 03_API文档.md             # 端点、请求响应示例、错误码
│   ├── 04_测试报告.md             # 覆盖率、冒烟结果、性能基线、安全检查项
│   └── 05_部署说明.md             # 本机部署步骤（对应 Phase 验证命令）
├── _legacy\                      # 源项目原样留档（历史文件/xia-ai/立绘化与pwa支持），gitignore 排除
└── .gitignore                    # .venv / node_modules / dist / .env / _legacy / db文件
```

## 里程碑（按序推进，每步可验证）

### Phase 0：立档迁移 + 现状评估
1. `git init d:\workspace\xia-ai`；整目录拷贝源项目 → `_legacy\`（只读留档，永不改动）
2. 通读 `AI女友_V13.py`（重构功能对照的**唯一基线**），逐项列出功能清单写入评估报告
3. 产出 `docs\01_项目现状评估.md`：版本时间线、技术栈盘点、技术债务清单

### Phase 1：后端骨架 + 数据迁移
1. venv（Python 3.11）+ fastapi/uvicorn/sqlalchemy/pydantic-settings/ollama/openai/httpx/pytest
2. 实现 config / logging / db models → providers/llm.py 双通道（含 mock 实现供测试）→ services 四件套（逻辑从 V13 **逐段对照移植**，不凭记忆重写）
3. RESTful 端点：`POST /api/chat`、`GET/POST /api/memories`、`GET/PUT /api/persona`、`POST /api/tts`、`GET /api/health`
4. 编写 `tools\import_legacy.py`：从旧 chromadb/旧对话数据导入 SQLite（旧数据可直接导出则导出，无数据则建空库）

### Phase 2：前端 Vue 3
1. Vite 脚手架 + Pinia + router + PWA 插件（沿用「希亚 - 我的AI女友」名称与旧 manifest 图标）
2. 组件按上表落地；响应式布局（桌面双栏/移动单栏）；夜间模式；立绘展示
3. ESLint + Prettier 收口

### Phase 3：测试 + 文档
1. pytest 单测（chat 编排/记忆检索/双通道切换/情绪引擎，LLM 全部 mock）+ 集成测试（TestClient 全链路）；覆盖率 ≥80% 硬门槛
2. 四份文档按上表产出；性能基线（chat 接口延迟）与安全清单（密钥环境变量化、输入校验、SQL 注入防护走 ORM）

### Phase 4：验收收尾
1. 对照交付标准逐项自查 + 代码审查清单
2. ChatGLM3-6B 评估备忘录（预期结论：Ollama qwen3.5:4b 已覆盖本地通道，GLM 无必要保留 → 出移除清单待用户确认）

## 验证方式（Verification）

```powershell
# 后端测试（覆盖率≥80%为通过）
cd d:\workspace\xia-ai\backend
.venv\Scripts\python -m pytest --cov=app --cov-report=term --cov-fail-under=80

# 冒烟：双服务起跑
.venv\Scripts\python -m uvicorn app.main:app --port 8900
cd ..\frontend; npm run dev
# 浏览器对话一轮：验证流式回复、记忆写入检索、情绪/夜间模式切换、TTS 朗读、PWA 安装提示
```

## 风险与备注

- V13 源码细节以 Phase 0 通读为准，本计划功能清单如有出入以「V13 全功能」原则补全
- qwen-plus 的 API key 需要用户提供后写入 `.env`（历史文件中的旧 key 已失效风险高）
- 向量库优先 sqlite-vec（单文件零服务）；pip 不可用时降级 chromadb 嵌入式
- 旧 chromadb 数据若存在格式不兼容，以「新建空库 + 可选导入脚本」兜底，不阻塞重构
