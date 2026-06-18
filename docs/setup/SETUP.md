# Setup

CodePilot is Windows-first and expects Conda.

```powershell
git clone https://github.com/Strange-Men/CodePilot.git
cd CodePilot
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup.ps1
```

If Conda is not on PATH, set it before running setup:

```powershell
$env:CODEPILOT_CONDA = "path\to\your\conda.exe"
```

The setup script creates the required environment:

```powershell
conda create -n codepilot python=3.11 -y
```

Then it installs backend dependencies inside `codepilot` and frontend dependencies with `npm install`.

Run the backend and frontend:

```powershell
.\scripts\start-backend.ps1
.\scripts\start-frontend.ps1
```

Or start both in separate PowerShell windows:

```powershell
.\scripts\start-demo.ps1
```

Smoke test the backend workflow:

```powershell
.\scripts\smoke-backend.ps1
```
