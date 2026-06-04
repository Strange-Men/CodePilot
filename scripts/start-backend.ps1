param(
    [string]$EnvName = "codepilot",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
. (Join-Path $PSScriptRoot "conda.ps1")

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

$portProcess = Get-PortProcess -Port $Port
if ($portProcess) {
    Write-Host "Port $Port already in use."
    Write-Host "PID: $($portProcess.PID)"
    Write-Host "Process: $($portProcess.ProcessName)"

    if ($portProcess.ProcessName -match "^(python|uvicorn)$" -and $portProcess.CommandLine -match "uvicorn|backend\.main:app") {
        Write-Host ""
        Write-Host "Backend already running at:"
        Write-Host "http://localhost:$Port"
        exit 0
    }

    Write-Host ""
    Write-Host "Port conflict detected."
    Write-Host "Stop the process using port $Port or run this script with another -Port value."
    exit 1
}

$Conda = Find-CodePilotConda
Set-Location $Root
Invoke-CodePilotConda -Conda $Conda -Arguments @("run", "-n", $EnvName, "python", "-m", "uvicorn", "backend.main:app", "--reload", "--host", "127.0.0.1", "--port", "$Port")
