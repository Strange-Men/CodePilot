param(
    [string]$EnvName = "codepilot",
    [int]$ApiPort = 8010,
    [int]$GitPort = 8123
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$env:USE_MOCK_LLM = "true"
. (Join-Path $PSScriptRoot "conda.ps1")

$Conda = Find-CodePilotConda
Invoke-CodePilotConda -Conda $Conda -Arguments @(
    "run", "-n", $EnvName, "python", "-m", "compileall",
    "backend\api",
    "backend\core",
    "backend\llm",
    "backend\models",
    "backend\parsers",
    "backend\reviewers",
    "backend\services",
    "backend\storage",
    "backend\tasks",
    "backend\main.py"
)

$SmokeRoot = Join-Path $Root ("backend\data\smoke-git-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $SmokeRoot | Out-Null

$Source = Join-Path $SmokeRoot "source"
$Bare = Join-Path $SmokeRoot "sample.git"
New-Item -ItemType Directory -Force -Path $Source | Out-Null
Push-Location $Source
try {
    git init | Out-Null
    @'
"""Smoke test repository for CodePilot."""

class Reviewer:
    def summarize(self, path: str) -> str:
        return f"summary for {path}"


def run_review() -> Reviewer:
    return Reviewer()
'@ | Set-Content -Encoding UTF8 app.py
    git -c user.email="codepilot@example.com" -c user.name="CodePilot Smoke" add app.py
    git -c user.email="codepilot@example.com" -c user.name="CodePilot Smoke" commit -m "initial smoke repo" | Out-Null
    git clone --bare $Source $Bare | Out-Null
    git --git-dir=$Bare update-server-info
}
finally {
    Pop-Location
}

$RunId = [guid]::NewGuid().ToString("N")
$ApiOut = Join-Path $Root "backend\data\smoke-api-$RunId.out.log"
$ApiErr = Join-Path $Root "backend\data\smoke-api-$RunId.err.log"
$GitOut = Join-Path $Root "backend\data\smoke-git-$RunId.out.log"
$GitErr = Join-Path $Root "backend\data\smoke-git-$RunId.err.log"

$GitProc = Start-Process powershell -ArgumentList @(
    "-NoProfile",
    "-Command",
    "Set-Location '$SmokeRoot'; & '$Conda' run -n $EnvName python -m http.server $GitPort --bind 127.0.0.1"
) -WindowStyle Hidden -PassThru -RedirectStandardOutput $GitOut -RedirectStandardError $GitErr

$ApiProc = Start-Process powershell -ArgumentList @(
    "-NoProfile",
    "-Command",
    "Set-Location '$Root'; `$env:USE_MOCK_LLM='true'; & '$Conda' run -n $EnvName python -m uvicorn backend.main:app --host 127.0.0.1 --port $ApiPort"
) -WindowStyle Hidden -PassThru -RedirectStandardOutput $ApiOut -RedirectStandardError $ApiErr

try {
    $Ready = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $Health = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/health" -TimeoutSec 2
            if ($Health.status -eq "ok") {
                $Ready = $true
                break
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }
    if (-not $Ready) {
        throw "API did not become healthy on port $ApiPort."
    }

    $RepoUrl = "http://github.com@127.0.0.1:$GitPort/sample.git"
    $Created = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:$ApiPort/api/reviews" -ContentType "application/json" -Body (@{ repo_url = $RepoUrl } | ConvertTo-Json)
    $TaskId = $Created.task_id
    $Final = $null

    for ($i = 0; $i -lt 60; $i++) {
        $Status = Invoke-RestMethod -Uri "http://127.0.0.1:$ApiPort/api/reviews/$TaskId" -TimeoutSec 5
        if ($Status.status -in @("completed", "failed")) {
            $Final = $Status
            break
        }
        Start-Sleep -Seconds 1
    }

    if (-not $Final) {
        throw "Review did not finish in time."
    }
    if ($Final.status -ne "completed") {
        throw "Review failed: $($Final.error)"
    }

    $Export = (& curl.exe -s "http://127.0.0.1:$ApiPort/api/reviews/$TaskId/export") -join "`n"
    foreach ($Section in @("# Architecture Summary", "# Code Smells", "# Maintainability Issues", "# Refactoring Suggestions")) {
        if ($Export.IndexOf($Section) -lt 0) {
            throw "Export missing $Section"
        }
    }

    [pscustomobject]@{
        task_id = $TaskId
        status = $Final.status
        export_chars = $Export.Length
        export_path = $Final.export_path
    }
}
finally {
    if ($ApiProc -and -not $ApiProc.HasExited) {
        taskkill.exe /PID $ApiProc.Id /T /F 2>$null | Out-Null
    }
    if ($GitProc -and -not $GitProc.HasExited) {
        taskkill.exe /PID $GitProc.Id /T /F 2>$null | Out-Null
    }
    Remove-Item -Recurse -Force $SmokeRoot -ErrorAction SilentlyContinue
    Remove-Item -Force $ApiOut, $ApiErr, $GitOut, $GitErr -ErrorAction SilentlyContinue
}
