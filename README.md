# CodePilot | AI 代码审查与仓库理解系统

English version: [README.en.md](README.en.md)

前置静态解析 + 结构化上下文 + 证据绑定，让大模型生成可复查的仓库审查报告。

![Python](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi)
![Pydantic](https://img.shields.io/badge/Pydantic-Data%20Validation-E92063?logo=pydantic)
![SQLite](https://img.shields.io/badge/SQLite-Persistence-003B57?logo=sqlite)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)
![TypeScript](https://img.shields.io/badge/TypeScript-Strict-3178C6?logo=typescript)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-UI-06B6D4?logo=tailwindcss)
![Mock](https://img.shields.io/badge/Mock-Default-orange)
![Docker](https://img.shields.io/badge/Docker-Local%20Run-2496ED?logo=docker)
![Render](https://img.shields.io/badge/Render-Backend-46E3B7?logo=render)
![Vercel](https://img.shields.io/badge/Vercel-Frontend-000000?logo=vercel)

## 🎯 项目背景：为什么做？（Situation）

中小型 GitHub 仓库的理解和审查经常卡在三个现实问题上：

- 人工阅读仓库耗时长、依赖经验，输出稳定性受审查者经验和上下文掌握程度影响。
- 通用大模型直接问答缺少完整仓库上下文，容易给出泛化建议，难以复查依据。
- 传统静态分析工具偏语法、规范和安全检查，通常不生成架构级理解报告。

CodePilot 面向中小型 Python 仓库，用“静态解析提取事实 + LLM 生成解释”的方式，先把仓库文件、符号、依赖和规模指标整理成结构化上下文，再输出带证据的代码理解与审查报告。

## ✨ 项目定位与核心能力（Task）

CodePilot 是一个面向中小型 GitHub 仓库的 AI 代码审查 MVP，当前优先支持 Python 仓库。输入公开仓库 URL 后，系统静态读取仓库并输出四区块报告：

- 架构概览
- 代码坏味道
- 可维护性分析
- 重构建议

核心能力：

- 前置静态解析降噪，降低大模型输入规模。
- 结构化证据绑定，让建议可追溯到文件、函数、类、依赖和指标。
- `ReportContract` 统一报告结构契约，隔离 LLM 输出波动。
- Mock / Real LLM 双模式解耦，开发、测试和 CI 稳定可复现。
- Provider 接口让模型层可插拔，当前支持 Mock Provider 与 OpenAI-compatible Real LLM Provider。
- SQLite 保存任务状态和历史报告，支持前端轮询展示。

非当前目标：

- 大型 monorepo 不在当前范围内。
- 不做所有语言全覆盖。
- 不执行用户仓库代码，只做静态分析。
- 不做自动修复。
- 不包装成完整商业化代码审查平台。

## 🏗️ 架构与核心实现（Action）

整体链路：

```text
GitHub URL
→ 仓库克隆（静态读取）
→ 文件过滤 / 静态解析
→ 结构化上下文构建
→ Mock / Real LLM 生成报告
→ ReportContract 校验
→ SQLite 持久化
→ 前端展示
```

### 1. 前置工程降噪

CodePilot 不把仓库原始代码直接全部喂给模型，而是在 LLM 之前先做工程降噪：

- 过滤 `.git`、`__pycache__`、`.venv`、`dist`、`build` 等低价值内容。
- 保留源码、配置文件和 README，保证模型仍能理解仓库结构。
- 使用 Python AST，并保留 tree-sitter extension-ready 的解析路径，提取函数、类、导入依赖和文件规模。
- 用结构化上下文替代原始代码直喂，减少噪声并保留可定位的工程事实。

### 2. 报告质量控制

报告生成不是自由散文，而是受结构契约约束：

- 固定四区块报告结构：架构概览、代码坏味道、可维护性分析、重构建议。
- `ReportContract` 统一报告结构，约束 LLM 输出格式，降低模型输出波动对前端和历史记录的影响。
- 证据字段让 finding 绑定文件路径、函数、类、依赖和指标。
- 目标是让报告可复查，而不是生成一大段难以追踪依据的主观评价。

### 3. 工程稳定性保障

系统把真实模型调用和本地工程验证解耦：

- Mock LLM 用于开发、测试和 CI，输出稳定可复现。
- Real LLM 用于真实报告生成验证。
- Provider 接口隔离模型调用层，便于替换 MiMo、Doubao、DeepSeek 等 OpenAI-compatible Provider。
- 任务分阶段记录，失败后可定位到克隆、解析、LLM 或报告合成阶段。
- `pytest` / `ruff` / `audit_harness` 覆盖测试、静态检查和全链路校验。

## 🛠️ 技术栈

| 层级 | 技术栈 | 说明 |
|---|---|---|
| Backend | FastAPI 0.115.6 + Pydantic 2.10.4 + Uvicorn 0.34.0 | 结构化 API、参数校验、异步服务入口 |
| Frontend | Next.js 15.5.19 + React 19.0.0 + TypeScript 5.7.2 + Tailwind CSS 3.4.17 | 报告工作台、任务状态、证据展示和 Markdown 渲染 |
| Persistence | SQLite（Python stdlib，WAL 模式） | 任务状态和历史报告持久化 |
| Parsing | Python AST + tree-sitter 0.24.0 / tree-sitter-language-pack 0.7.0 | Python 优先，保留多语言扩展路径 |
| Token Counting | tiktoken 0.13.0 | 统一 Token 估算方法 |
| LLM | Mock Provider + OpenAI-compatible Real LLM Provider | Mock 默认；Real LLM 支持 MiMo / Doubao / DeepSeek 配置 |
| Deployment | Docker Compose 本地运行；Render 后端、Vercel 前端部署文档 | 见 `docker-compose.yml`、`Dockerfile.*` 和 `docs/setup/` |
| Quality | pytest + ruff + audit_harness + GitHub Actions | 测试、静态检查、全链路审计和 CI |

## 📊 量化效果（Result）

### 工程降噪

- 基准仓库：3 个公开 Python 仓库。
- 仓库规模：60-79 个 Python 源码文件，接近或超出早期 50 文件边界。
- 平均文件降噪率：49.1%。
  - 口径：以 `git ls-files` 统计的 Git 跟踪原生业务文件为基线，排除 `.git`、依赖目录、虚拟环境等非业务内容。
- 结构化上下文平均 Token 压缩率：96.8%。
  - 口径：对比同范围有效源码的原始代码 Token 与结构化上下文 Token，统一使用 tiktoken 估算。

### 真实 LLM 单仓验证

- 验证仓库：httpx 单仓。
- 对照组输入 Token：137417。
- CodePilot 输入 Token：15212。
- 输入规模降低：约 8.85 倍，约等于近 9 倍。
- 真实 LLM 调用输入 Token 压缩率：88.7%。
- CodePilot 证据绑定率：100%。
- 通用大模型直出对照组证据绑定率：0%。
- 证据绑定率提升：100 个百分点。

说明：

- 这是 httpx 单仓定性验证，不代表大规模统计结论。
- 这里只统计输入 Token，不包含输出 Token，不能表述为总成本降低。
- 证据绑定率是 v1.0 规则下的统计结果，不等于报告绝对正确。

### 工程质量

- `pytest`：1000 passed, 1 skipped。
- `ruff`：0 问题。
- `audit_harness`：全链路校验通过。
- Mock 模式仓库审查成功率：100%。

| 验证维度 | 结果 | 口径 |
|---|---:|---|
| 平均文件降噪率 | 49.1% | 3 个基准仓库，`git ls-files` 业务文件基线 |
| 结构化上下文 Token 压缩率 | 96.8% | 同范围有效源码 vs 结构化上下文 |
| httpx 真实 LLM 输入 Token 压缩率 | 88.7% | 单仓真实调用，只统计输入 Token |
| 证据绑定率 | 100% vs 0% | httpx 单仓，CodePilot vs 原始代码直喂 |
| pytest | 1000 passed, 1 skipped | 测试工具原生输出 |
| ruff | 0 issues | 静态检查 |
| audit_harness | passed | 全链路审计校验 |

## 🚀 快速开始

### Windows PowerShell 脚本启动

仓库提供了 Windows PowerShell 脚本，会创建 `codepilot` conda 环境、安装依赖并启动前后端：

```powershell
git clone https://github.com/Strange-Men/CodePilot.git
cd CodePilot
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
.\scripts\start-demo.ps1
```

启动后访问：

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend: [http://localhost:8000](http://localhost:8000)
- Health Check: [http://localhost:8000/health](http://localhost:8000/health)

如果 `conda.exe` 不在 PATH 中：

```powershell
$env:CODEPILOT_CONDA = "path\to\your\conda.exe"
.\scripts\setup.ps1
```

### 手动启动

```bash
# 后端
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000

# 前端（新终端）
cd frontend
npm install
npm run dev -- --port 3000
```

Windows PowerShell 手动启动前端时可显式设置后端地址：

```powershell
$env:NEXT_PUBLIC_API_BASE = "http://localhost:8000"
npm run dev -- --port 3000
```

### Docker 本地运行

```powershell
cp .env.example .env
docker compose up --build
```

启动后访问：

- Frontend: http://localhost:3000
- Backend: http://localhost:8000
- Health: http://localhost:8000/health

默认使用 Mock LLM 模式，不需要真实 API Key。使用真实模型需在 `.env` 中配置对应 provider 的 API Key，详见 [Docker 本地运行文档](docs/DOCKER.md)。

停止与清理：

```bash
docker compose down        # 停止容器
docker compose down -v     # 停止并删除 SQLite/workspace/reports volume
```

### 测试与质量校验

```bash
# 后端测试与检查
python -m pytest tests/ -q
ruff check .
python scripts/audit_harness.py

# 前端测试与构建
cd frontend
npm test
npm run build
```

## 📁 目录结构

```text
CodePilot/
├── backend/          # FastAPI backend, parsers, LLM providers, review pipeline
├── frontend/         # Next.js / React / TypeScript frontend
├── contracts/        # Report section contract files
├── docs/             # Architecture, setup, evaluation and deployment docs
├── evaluation/       # Evaluation datasets, metrics and comparison scripts
├── reports/          # Generated metric and validation outputs
├── scripts/          # Setup, startup, audit and metric scripts
├── tests/            # Unit, integration, regression and metric tests
├── Dockerfile.backend
├── Dockerfile.frontend
├── docker-compose.yml
├── README.md
└── README.en.md
```

## 🛣️ 后续规划

- 增强报告证据链：绑定代码片段、影响范围、重构优先级。
- 增强真实 LLM 稳定性：schema 校验、自动重试、fallback。
- 加固外部仓库安全沙箱：目录隔离、文件数量 / 大小限制、超时控制。
- 扩展多语言支持：优先 JavaScript / TypeScript，基于 tree-sitter。
- 产品化评估体系：evaluation dashboard。

## ⚠️ 当前局限

- 当前优先支持 Python 仓库。
- 不执行用户仓库代码，只做静态分析。
- 真实 LLM 仅完成 httpx 单仓端到端验证。
- Baseline 对照是单仓定性验证，不代表大规模统计结论。
- 当前是 MVP，不是完整商业化代码审查平台。
- JavaScript / TypeScript 已有解析入口和测试覆盖，但当前分析深度弱于 Python。
- SQLite 历史记录取决于实际存储配置；Render Free 等临时存储环境重启后可能丢失历史。

## 📄 License

MIT License
