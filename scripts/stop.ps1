param([switch]$Infrastructure)

$ErrorActionPreference = 'Continue'
. (Join-Path $PSScriptRoot 'Initialize-WindowsEnvironment.ps1')
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeDir = Join-Path $projectRoot '.runtime'
Set-Location $projectRoot

foreach ($name in @('desktop', 'api', 'langgraph', 'web')) {
    $pidFile = Join-Path $runtimeDir ($name + '.pid')
    if (Test-Path $pidFile) {
        $savedPid = [int](Get-Content $pidFile -Raw)
        taskkill.exe /PID $savedPid /T /F 2>$null | Out-Null
        Remove-Item -LiteralPath $pidFile -Force
    }
}

if ($Infrastructure) {
    docker-compose down
}

Write-Host 'Fei application processes stopped.' -ForegroundColor Green
