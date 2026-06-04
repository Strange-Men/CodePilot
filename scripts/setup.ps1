param(
    [string]$EnvName = "codepilot"
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
. (Join-Path $PSScriptRoot "conda.ps1")

$Conda = Find-CodePilotConda
$envList = & $Conda env list
if ($LASTEXITCODE -ne 0) {
    throw "Conda command failed: $Conda env list"
}
if ($envList -notmatch "^\s*$EnvName\s") {
    Invoke-CodePilotConda -Conda $Conda -Arguments @("create", "-n", $EnvName, "python=3.11", "-y")
}

Invoke-CodePilotConda -Conda $Conda -Arguments @("run", "-n", $EnvName, "python", "-m", "pip", "install", "--upgrade", "pip")
Invoke-CodePilotConda -Conda $Conda -Arguments @("run", "-n", $EnvName, "python", "-m", "pip", "install", "-r", (Join-Path $Root "backend\requirements.txt"))

Push-Location (Join-Path $Root "frontend")
try {
    Invoke-CodePilotNative -Command "npm" -Arguments @("install")
}
finally {
    Pop-Location
}

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Copy-Item (Join-Path $Root ".env.example") (Join-Path $Root ".env")
}

Write-Host "CodePilot setup complete. Use scripts\start-backend.ps1 and scripts\start-frontend.ps1."
