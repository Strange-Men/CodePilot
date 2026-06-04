# CodePilot Deployment

CodePilot V1.1 keeps the V1.0 modular monolith intact: a Next.js frontend, a FastAPI backend, SQLite persistence, Git clone workspace cleanup, and markdown report export.

## Frontend

Deploy `frontend/` to Vercel.

Recommended Vercel settings:

- Framework Preset: Next.js
- Root Directory: `frontend`
- Build Command: `npm run build`
- Output: Next.js default

Set `NEXT_PUBLIC_API_BASE` to the public backend URL, for example:

```powershell
NEXT_PUBLIC_API_BASE=https://codepilot-api.example.com
```

## Backend

Deploy the repository root to Railway using `Dockerfile.backend`, or configure a Python service from `backend/requirements.txt`.

Recommended Railway settings:

- Builder: Dockerfile
- Dockerfile Path: `Dockerfile.backend`
- Start Command: use the Dockerfile `CMD`
- Public Port: `8000`

The backend requires Git at runtime because repositories are cloned with the Git CLI. `Dockerfile.backend` installs Git.

## Environment Variables

Backend:

```powershell
USE_MOCK_LLM=true
DATABASE_PATH=/app/backend/data/codepilot.db
WORKSPACE_PATH=/app/backend/workspace
REPORTS_PATH=/app/reports
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

Frontend:

```powershell
NEXT_PUBLIC_API_BASE=https://your-backend-url
```

For a production LLM-backed deployment, set:

```powershell
USE_MOCK_LLM=false
OPENAI_API_KEY=your_api_key
```

## Production Startup

Backend:

```powershell
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
npm run build
npm run start
```

Docker Compose:

```powershell
docker compose up --build
```

Exposed ports:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

## Troubleshooting

Backend health check fails:

- Confirm the backend service exposes port `8000`.
- Confirm `DATABASE_PATH`, `WORKSPACE_PATH`, and `REPORTS_PATH` point to writable locations.
- Confirm Git is installed in the runtime image or host.

Frontend cannot reach backend:

- Confirm `NEXT_PUBLIC_API_BASE` is set to the public backend URL before building the frontend.
- Confirm backend CORS allows the frontend origin.

Clone failures:

- Confirm the repository URL is public and hosted on GitHub.
- Retry if the backend logs show transient network failures such as connection resets or timeouts.

LLM failures:

- Use `USE_MOCK_LLM=true` for demos without an API key.
- For real API mode, confirm `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL`.

SQLite write errors:

- Confirm the database directory is writable and persistent.
- CodePilot enables WAL mode and a busy timeout on SQLite connections.
