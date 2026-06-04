param(
    [int]$Port = 3000
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")

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

    if ($portProcess.ProcessName -ieq "node") {
        Write-Host ""
        Write-Host "Frontend already running at:"
        Write-Host "http://localhost:$Port"
        exit 0
    }

    Write-Host ""
    Write-Host "Port conflict detected."
    Write-Host "Stop the process using port $Port or run this script with another -Port value."
    exit 1
}

Set-Location (Join-Path $Root "frontend")
$env:NEXT_PUBLIC_API_BASE = "http://localhost:8000"
npm run dev -- --port $Port
