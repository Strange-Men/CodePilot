# CodePilot Docker Local Run

CodePilot includes a local Docker Compose setup for demos and development. It starts the FastAPI backend, the Next.js frontend, and SQLite-backed local persistence without requiring a real LLM key.

## Quick Start

```bash
docker compose up --build
```

Open:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Health check: http://localhost:8000/health

Stop containers:

```bash
docker compose down
```

Remove local Docker volumes:

```bash
docker compose down -v
```

## Mock Mode

Mock mode is the default:

```text
USE_MOCK_LLM=true
ENABLE_REAL_LLM=false
```

This path needs no API key and is the recommended Docker smoke path.

## Real LLM Mode

Create a local `.env` from `.env.example`, then set:

```text
USE_MOCK_LLM=false
ENABLE_REAL_LLM=true
REAL_LLM_PROVIDER=mimo
```

MiMo:

```text
MIMO_API_KEY=your-key
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL_NAME=mimo-v2.5-pro
```

Doubao / Volcengine Ark:

```text
REAL_LLM_PROVIDER=doubao
DOUBAO_API_KEY=your-key
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL_NAME=your-volcengine-endpoint-id
```

DeepSeek:

```text
REAL_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL_NAME=deepseek-chat
```

API keys stay in local environment variables or `.env`; `.dockerignore` prevents `.env`, caches, database files, `.git`, `.claude`, and dependency folders from being sent to the Docker build context.

## Persistence

The compose file uses named volumes:

- `backend-data`: SQLite database at `/app/backend/data/codepilot.db`
- `backend-workspace`: cloned repository workspace
- `reports`: generated reports

These volumes persist until removed with `docker compose down -v`.

## Notes

- Docker does not change the non-Docker startup scripts.
- The frontend receives `NEXT_PUBLIC_API_BASE`, defaulting to `http://localhost:8000`.
- The backend installs Git in the image because repository cloning uses the Git CLI.
