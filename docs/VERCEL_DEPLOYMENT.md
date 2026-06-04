# CodePilot Frontend Deployment on Vercel

This guide deploys the CodePilot V1.1 frontend to Vercel Free and connects it to the deployed Render backend:

```text
https://codepilot-i189.onrender.com
```

No backend, API, database, or architecture changes are required.

## Repository

Use the GitHub repository:

```text
https://github.com/Strange-Men/CodePilot
```

## Vercel Project Settings

Create a new Vercel project from the GitHub repository and use these settings:

| Setting | Value |
| --- | --- |
| Framework Preset | Next.js |
| Root Directory | `frontend` |
| Install Command | `npm ci` |
| Build Command | `npm run build` |
| Output Directory | leave empty / Vercel default |
| Development Command | leave default |
| Node.js Version | Vercel default Node 20+ |

The frontend is a standard Next.js app. Vercel automatically detects the `.next` output for the Next.js framework when the root directory is set to `frontend`.

## Environment Variables

Add this variable in Vercel Project Settings:

```text
NEXT_PUBLIC_API_BASE=https://codepilot-i189.onrender.com
```

Apply it to:

- Production
- Preview
- Development

Important: `NEXT_PUBLIC_API_BASE` is read by the browser bundle, so it must be present before the Vercel build runs. Redeploy after adding or changing it.

## Backend CORS

After Vercel creates the public frontend URL, update the Render backend environment:

```text
CORS_ALLOW_ORIGINS=https://your-vercel-project.vercel.app
```

If you also want preview deployments to work, either add specific preview origins separated by commas or configure an allowed regex on the backend:

```text
CORS_ALLOW_ORIGIN_REGEX=https://.*\.vercel\.app
```

Redeploy or restart the Render backend after changing CORS settings.

## Deploy

1. Open Vercel.
2. Click **Add New Project**.
3. Import `Strange-Men/CodePilot`.
4. Set **Root Directory** to `frontend`.
5. Confirm **Framework Preset** is `Next.js`.
6. Set **Install Command** to `npm ci`.
7. Set **Build Command** to `npm run build`.
8. Leave **Output Directory** empty.
9. Add `NEXT_PUBLIC_API_BASE=https://codepilot-i189.onrender.com`.
10. Click **Deploy**.
11. Copy the generated Vercel URL.
12. Add that URL to Render `CORS_ALLOW_ORIGINS`.
13. Redeploy or restart the Render backend.

## Validation Checklist

Open the Vercel URL and verify:

- Homepage loads and shows `CodePilot`.
- Repository input is visible.
- `Start Review` creates a task.
- Status polling advances through the review lifecycle.
- Final status reaches `Completed`.
- The report renders exactly these sections:
  - `Architecture Summary`
  - `Code Smells`
  - `Maintainability Issues`
  - `Refactoring Suggestions`
- `Export Markdown` downloads or opens markdown content.

## Public URL Verification

Use these URLs after deployment:

```text
Frontend: https://your-vercel-project.vercel.app
Backend health: https://codepilot-i189.onrender.com/health
```

Expected backend health response:

```json
{"status":"ok"}
```

If the UI loads but review creation fails, check:

- `NEXT_PUBLIC_API_BASE` is set in Vercel and the frontend was redeployed after setting it.
- `CORS_ALLOW_ORIGINS` on Render includes the exact Vercel frontend origin.
- Render backend health is still `{"status":"ok"}`.
