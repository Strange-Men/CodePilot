$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
. (Join-Path $PSScriptRoot "conda.ps1")

$Conda = Find-CodePilotConda
$env:CODEPILOT_CONDA = $Conda

function Get-PortProcess {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if (-not $connection) {
        return $null
    }

    $process = Get-Process -Id $connection.OwningProcess -ErrorAction SilentlyContinue
    [pscustomobject]@{
        Port = $Port
        PID = $connection.OwningProcess
        ProcessName = if ($process) { $process.ProcessName } else { "Unknown" }
        CommandLine = if ($process) { (Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)").CommandLine } else { "" }
    }
}

function Test-PortListening {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Port
    )

    return [bool](Get-PortProcess -Port $Port)
}

$backendProcess = Get-PortProcess -Port 8000
$frontendProcess = Get-PortProcess -Port 3000

if ($backendProcess) {
    Write-Host "Port 8000 already in use."
    Write-Host "PID: $($backendProcess.PID)"
    Write-Host "Process: $($backendProcess.ProcessName)"
    if ($backendProcess.ProcessName -match "^(python|uvicorn)$" -and $backendProcess.CommandLine -match "uvicorn|backend\.main:app") {
        Write-Host ""
        Write-Host "Backend already running at:"
        Write-Host "http://localhost:8000"
    }
    else {
        Write-Host ""
        Write-Host "Port conflict detected."
        Write-Host "Stop the process using port 8000 before starting the backend."
        exit 1
    }
}
else {
    Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$Root\scripts\start-backend.ps1`"" -WindowStyle Normal
    Start-Sleep -Seconds 2
}

if ($frontendProcess) {
    Write-Host "Port 3000 already in use."
    Write-Host "PID: $($frontendProcess.PID)"
    Write-Host "Process: $($frontendProcess.ProcessName)"
    if ($frontendProcess.ProcessName -ieq "node") {
        Write-Host ""
        Write-Host "Frontend already running at:"
        Write-Host "http://localhost:3000"
    }
    else {
        Write-Host ""
        Write-Host "Port conflict detected."
        Write-Host "Stop the process using port 3000 before starting the frontend."
        exit 1
    }
}
else {
    Start-Process powershell -ArgumentList "-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "`"$Root\scripts\start-frontend.ps1`"" -WindowStyle Normal
}

Write-Host "Conda:    $Conda"
Write-Host "Backend:  http://localhost:8000"
Write-Host "Frontend: http://localhost:3000"
