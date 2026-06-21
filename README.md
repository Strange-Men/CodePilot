# CodePilot｜AI 代码审查与仓库理解 Agent 系统

English version: [README.en.md](README.en.md)

CodePilot 是一个面向 GitHub 开源仓库的 **AI 代码审查与仓库理解系统**。输入仓库 URL，自动完成仓库拉取、代码解析、多 Agent 审查、证据追踪和结构化报告生成。项目验证了从「仓库解析 → 结构化上下文 → 多 Agent 协作 → 证据绑定 → 报告导出 → 前端展示」的完整工程链路。

---

## 在线演示

| 模块 | 地址 |
|------|------|
| 前端 Demo | [https://code-pilot-red.vercel.app](https://code-pilot-red.vercel.app) |
| 后端 API | `https://codepilot-i189.onrender.com` |
| 健康检查 | [https://codepilot-i189.onrender.com/health](https://codepilot-i189.onrender.com/health) |

> **演示建议：** 推荐使用 Mock 模式（默认），无需 API Key，输出稳定，支持中英文切换。真实 LLM / MiMo 模式为可选能力，受模型服务和网络影响。  
> **注意：** Render 免费环境为临时存储，历史审查记录可能因容器重启丢失，这在演示部署中属于预期行为。

---

## 项目定位

- 这是一个**仓库级代码审查 Agent 原型**，不是商业产品的替代品
- 重点验证「仓库解析 → 结构化上下文 → 多 Agent 审查 → 证据追踪 → 报告生成」的完整工程链路
- 适合用于快速理解陌生仓库、定位潜在工程问题、生成结构化审查报告
- 项目面向校招 / 实习 Portfolio 展示，强调工程完整性和技术深度，不夸大功能边界

---

## 核心功能

- **仓库智能解析** — 基于 Tree-sitter 和 AST 的代码结构解析，支持 Python、JavaScript、TypeScript
- **结构化上下文构建** — 不向 LLM 发送原始源码，而是构建包含符号摘要、依赖关系和文件结构的 RepositoryContext
- **多 Agent 审查** — Architecture、CodeQuality、Maintainability、Refactor 四个专项 Agent 并行审查
- **证据追踪系统** — 每条审查结论绑定 evidence_id（如 `[E1]`/`[E2]`），关联文件路径、行号和代码片段，降低 LLM 幻觉风险
- **中英文切换** — 全局 zh/en 语言切换，报告、发现、UI 标签和错误信息均跟随语言设置
- **Markdown 报告导出** — 一键导出完整审查报告，含证据附录
- **Mock / 真实 LLM 双模式** — Mock 模式确定性输出、无需凭据；真实 LLM 模式支持 OpenAI 兼容接口和 MiMo

---

## 系统架构

```
GitHub URL
  → 仓库拉取
  → 文件过滤（大小 / 类型 / 敏感信息）
  → Tree-sitter / AST 代码解析
  → 结构化仓库上下文（RepositoryContext）
  → 多 Agent 并行审查
       ├── Architecture Agent（架构分析）
       ├── CodeSmell Agent（代码质量）
       ├── Maintainability Agent（可维护性）
       └── Refactor Agent（重构建议）
  → Evidence Store（证据绑定）
  → Report Composer（报告合成）
  → 前端展示 / Markdown 导出
```

**部署架构：**

```
┌──────────────────────────┐         ┌──────────────────────────┐
│   Vercel（前端）           │         │   Render（后端）           │
│   Next.js 15 + React 19   │────────▶│   FastAPI + SQLite       │
│   TypeScript + Tailwind    │  HTTPS  │   Tree-sitter 解析器      │
│   code-pilot-red.vercel.app│        │   codepilot-*.onrender.com│
└──────────────────────────┘         └──────────────────────────┘
```

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Next.js 15.5、React 19、TypeScript 5.7、Tailwind CSS 3.4 | Vercel 部署，支持中英文切换 |
| 后端 | FastAPI、Python 3.11、SQLite（WAL 模式）、ThreadPoolExecutor | Render Docker 部署 |
| 代码解析 | Tree-sitter + AST fallback | Python 深度解析，JS/TS 基础解析 |
| 数据校验 | Pydantic | 全链路结构化数据校验 |
| LLM 接入 | MockLLMClient + OpenAI 兼容接口 / MiMo 可选 | Mock 模式默认，真实 LLM 可选 |
| 部署 | Vercel（前端）+ Render（后端） | 免费层部署 |
| 工程化 | GitHub Actions、pytest、ruff、npm test、npm run build | CI 全流程覆盖 |

---

## 关键设计说明

### 1. 多 Agent 审查流程

不同 Agent 负责不同审查维度（架构、质量、可维护性、重构）。Agent 之间不是自由对话，而是由统一的 Orchestrator 调度：共享 RepositoryContext 和 EvidenceStore，各自独立产出结构化 findings，最后由 ReportComposer 合成四段式报告（总览 + 发现 + 行动计划 + 证据附录）。

### 2. Evidence-grounded 报告

每条 finding 绑定 `evidence_id`，用户在报告中看到 `[E1]`/`[E2]` 标记。Evidence Appendix 展示对应的文件路径、行号和代码片段。这种设计让审查结论可溯源、可验证，降低 LLM 幻觉对报告可信度的影响。

### 3. 结构化仓库上下文（非完整向量 RAG）

本项目**没有**采用 embedding + 向量数据库的完整 RAG 路径。当前方案是通过 Tree-sitter / AST / 依赖图 / 符号摘要构建结构化仓库上下文（RepositoryContext），保留文件路径、符号关系、行号和依赖结构。这种方式更适合代码审查场景——审查需要精确的文件位置和结构信息，而不是语义相似度检索。

### 4. Mock / 真实 LLM 双模式

- **Mock 模式**：`MockLLMClient` 返回预构建的双语 findings，确定性输出，无需 API Key，用于稳定演示和 CI 测试
- **真实 LLM 模式**：支持 OpenAI 兼容接口（如 GPT-4o-mini）和 MiMo，验证真实模型接入能力
- 两种模式走同一套报告生成、前端展示和导出链路

### 5. 中文展示与容错

支持 zh/en 全局切换，localStorage 持久化语言偏好。对真实 LLM 的中文输出做了字段级校验和 fallback 处理，确保即使模型输出格式异常也能正常展示。MiMo 中文输出可能仍有少量不自然表达，Mock 模式的中文是确定性且稳定的。

---

## 本地运行

```powershell
git clone https://github.com/Strange-Men/CodePilot.git
cd CodePilot
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start-demo.ps1
```

打开浏览器访问 [http://localhost:3000](http://localhost:3000)。

如果 conda 不在 PATH 中，需在运行 setup 前设置：

```powershell
$env:CODEPILOT_CONDA = "path\to\your\conda.exe"
.\scripts\setup.ps1
```

---

## 在线部署配置

### Vercel（前端）

| 配置项 | 值 |
|--------|-----|
| Framework Preset | Next.js |
| Root Directory | `frontend` |
| Build Command | `npm run build` |
| 环境变量 | `NEXT_PUBLIC_API_BASE=https://codepilot-i189.onrender.com` |

`NEXT_PUBLIC_API_BASE` 必须在构建前设置，修改后需重新部署。

### Render（后端）

| 配置项 | 值 |
|--------|-----|
| Runtime | Docker |
| Dockerfile | `./Dockerfile.backend` |
| Instance Type | Free |

所需环境变量：

```text
USE_MOCK_LLM=true
DATABASE_PATH=/app/backend/data/codepilot.db
WORKSPACE_PATH=/app/backend/workspace
REPORTS_PATH=/app/reports
CORS_ALLOW_ORIGINS=https://code-pilot-red.vercel.app
MAX_FILES=300
MAX_FILE_SIZE_BYTES=204800
```

### 真实 LLM 模式配置（可选）

使用 OpenAI 兼容接口：

```text
USE_MOCK_LLM=false
ENABLE_REAL_LLM=true
OPENAI_API_KEY=your-key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

使用 MiMo：

```text
MIMO_API_KEY=your-key
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL_NAME=mimo-v2.5-pro
```

---

## 测试与质量保障

```powershell
# 后端测试
pytest                    # 995 tests passed, 1 skipped
ruff check .              # All checks passed

# 前端测试
cd frontend
npm test                  # 104 tests passed
npm run build             # Production build succeeds

# 集成冒烟测试
.\scripts\smoke-backend.ps1
```

CI 使用 GitHub Actions，运行环境为 `windows-latest`，覆盖 ruff、pytest、npm install 和前端 build。

---

## 已知限制

- **一次性审查，非持续 PR Review Bot** — 当前版本是输入仓库 URL 后的一次性审查，还没有 GitHub OAuth / GitHub App / PR 自动评论能力
- **无长期仓库记忆** — 每次审查独立，没有跨次审查的持久化记忆
- **非完整向量 RAG** — 没有 embedding + 向量数据库的语义检索，采用结构化上下文方案
- **临时存储** — Render 免费环境的 SQLite 历史记录可能因容器重启丢失
- **语言支持差异** — Python 分析最深入，JavaScript / TypeScript 支持可用但分析深度较弱
- **静态分析** — 不执行仓库代码，仅做静态分析和 LLM 审查
- **文件数量限制** — 最多分析 300 个支持的源文件，跳过超过 200KB 的文件
- **真实 LLM 输出质量** — 依赖模型服务可用性和 API Key，MiMo 中文可能有少量不自然表达

---

## 文档入口

| 文档 | 说明 |
|------|------|
| [文档总览](docs/README.md) | 项目全部文档索引 |
| [本地安装指南](docs/setup/SETUP.md) | 环境配置与本地运行 |
| [部署指南](docs/setup/DEPLOYMENT.md) | Render + Vercel 部署说明 |
| [Vercel 部署指南](docs/setup/VERCEL_DEPLOYMENT.md) | 前端 Vercel 部署 |
| [系统架构](docs/architecture/ARCHITECTURE.md) | 设计决策、模块地图、数据流 |
| [V3.7 Release Notes](docs/releases/v3.7/V3.7_RELEASE_NOTES.md) | 版本亮点、修复、测试结果 |
| [V3.7 项目收尾报告](docs/releases/v3.7/V3.7_PROJECT_CLOSURE.md) | 完整验证与收尾 |
| [Tag 审计记录](docs/releases/TAG_AUDIT.md) | Release tag 审计 |

---

## License

本项目用于学习和 Portfolio 展示目的。
