# CodePilot Docker 本地运行

CodePilot 提供 Docker Compose 本地开发环境，一键启动 FastAPI 后端和 Next.js 前端，默认使用 Mock LLM 模式，无需真实 API Key。

## 前置条件

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) 已安装并启动
- 确认 Docker 可用：

```powershell
docker --version
docker compose version
```

## 快速启动

```powershell
# Windows
Copy-Item .env.example .env
docker compose up --build

# macOS / Linux
cp .env.example .env
docker compose up --build
```

启动后访问：

| 服务 | 地址 |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Health Check | http://localhost:8000/health |

## Mock 模式

Mock 模式是默认模式，不需要真实 LLM API Key。`.env.example` 中默认配置：

```text
USE_MOCK_LLM=true
ENABLE_REAL_LLM=false
```

Mock 模式下提交仓库 URL 会使用 Mock Provider 生成可复现的审查报告，适合本地开发和功能验证。

## Real LLM 模式

编辑 `.env`，切换到真实 LLM 模式：

```text
USE_MOCK_LLM=false
ENABLE_REAL_LLM=true
REAL_LLM_PROVIDER=mimo
```

然后配置所选 provider 的 API Key（只需填写选定 provider 的 key）：

### MiMo

```text
REAL_LLM_PROVIDER=mimo
MIMO_API_KEY=your-key
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL_NAME=mimo-v2.5-pro
```

### 豆包 / Doubao

```text
REAL_LLM_PROVIDER=doubao
DOUBAO_API_KEY=your-key
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL_NAME=your-volcengine-endpoint-id
```

### DeepSeek

```text
REAL_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_NAME=deepseek-chat
```

修改 `.env` 后重启容器：

```powershell
docker compose down
docker compose up --build
```

## 停止与清理

```powershell
docker compose down        # 停止容器
docker compose down -v     # 停止容器并删除 SQLite、workspace、reports volume
```

## Volume 持久化

Docker Compose 使用 named volumes 持久化数据：

| Volume | 容器内路径 | 说明 |
|---|---|---|
| `backend-data` | `/app/backend/data` | SQLite 数据库 |
| `backend-workspace` | `/app/backend/workspace` | 克隆的仓库 |
| `reports` | `/app/reports` | 生成的报告 |

数据在 `docker compose down -v` 之前一直保留。

## 故障排查

### Docker Desktop 未启动

```text
Cannot connect to the Docker daemon
```

打开 Docker Desktop，等待状态栏显示 "Docker Desktop is running" 后重试。

### 端口被占用

```text
Error: Bind for 0.0.0.0:8000 failed: port is already allocated
```

查找并关闭占用端口的进程：

```powershell
netstat -ano | findstr :8000
taskkill /PID <pid> /F
```

或修改 `docker-compose.yml` 中的端口映射，例如改为 `"8001:8000"`。

### Docker build 失败

```powershell
docker compose build --no-cache
```

常见原因：

- 网络问题导致 `pip install` 或 `npm ci` 超时：重试或配置镜像源。
- `contracts/` 目录缺失：确认项目根目录下存在 `contracts/report_sections.json`。
- `frontend/package-lock.json` 缺失：在本地 `frontend/` 目录执行 `npm install` 生成。

### 前端连不上后端

前端通过 `NEXT_PUBLIC_API_BASE` 环境变量连接后端，默认值为 `http://localhost:8000`。

排查步骤：

1. 确认后端容器运行中：`docker compose ps`，backend 状态应为 `healthy`。
2. 确认后端 health 可访问：`curl http://localhost:8000/health`。
3. 检查浏览器控制台是否有 CORS 错误。CORS 默认允许 `localhost:3000` 和 `127.0.0.1:3000`。
4. 如果修改了前端端口，需同步更新 `.env` 中的 `CORS_ALLOW_ORIGINS`。

### API Key 缺失

选择 Real LLM 且未配置 API Key 时，后端日志会显示 provider 不可用。

确认 `.env` 中已设置对应 provider 的 API Key：

```powershell
docker compose logs backend --tail=20
```

日志中 `startup_config` 行会显示当前 provider 和 model 配置。

## 安全说明

- `.env` 文件不进入 Docker 镜像（`.dockerignore` 排除 `.env`，保留 `.env.example`）。
- API Key 仅通过 `docker-compose.yml` 的 `environment` 传入容器，不写入镜像层。
- `.git`、`.claude`、`node_modules`、数据库缓存等均被 `.dockerignore` 排除。
