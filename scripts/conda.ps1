$ErrorActionPreference = "Stop"

function Find-CodePilotConda {
    if ($env:CODEPILOT_CONDA -and (Test-Path $env:CODEPILOT_CONDA)) {
        return $env:CODEPILOT_CONDA
    }

    $candidates = @(
        "D:\miniconda3\Scripts\conda.exe",
        "D:\Miniconda3\Scripts\conda.exe",
        "D:\anaconda3\Scripts\conda.exe",
        "D:\Anaconda3\Scripts\conda.exe",
        "D:\Miniforge3\Scripts\conda.exe",
        "D:\mambaforge\Scripts\conda.exe",
        "C:\ProgramData\miniconda3\Scripts\conda.exe",
        "C:\ProgramData\anaconda3\Scripts\conda.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $dDriveMatches = Get-ChildItem -Path "D:\" -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match "conda|anaconda|miniconda|miniforge|mambaforge" } |
        ForEach-Object { Join-Path $_.FullName "Scripts\conda.exe" } |
        Where-Object { Test-Path $_ }

    if ($dDriveMatches) {
        return $dDriveMatches[0]
    }

    $cmd = Get-Command conda -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    throw "Conda was not found. Set CODEPILOT_CONDA to conda.exe or install Conda on D:."
}

function Invoke-CodePilotConda {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Conda,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Conda @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Conda command failed: $Conda $($Arguments -join ' ')"
    }
}

function Invoke-CodePilotNative {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Command $($Arguments -join ' ')"
    }
}
