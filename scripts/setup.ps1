param(
    [string]$PyPIIndexUrl = $(if ($env:FEI_PYPI_INDEX_URL) { $env:FEI_PYPI_INDEX_URL } else { 'https://mirrors.aliyun.com/pypi/simple/' }),
    [string]$NpmRegistry = $(if ($env:FEI_NPM_REGISTRY) { $env:FEI_NPM_REGISTRY } else { 'https://registry.npmmirror.com' })
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Initialize-WindowsEnvironment.ps1')
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot

if (-not (Test-Path '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
if (-not (Test-Path 'web\.env.local')) {
    Copy-Item -LiteralPath 'web\.env.example' -Destination 'web\.env.local'
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --index-url $PyPIIndexUrl --upgrade pip
& .\.venv\Scripts\python.exe -m pip install --index-url $PyPIIndexUrl -e '.[dev]'

Push-Location web
try {
    npm install --registry=$NpmRegistry
}
finally {
    Pop-Location
}

Push-Location desktop
try {
    npm install --registry=$NpmRegistry
}
finally {
    Pop-Location
}

Write-Host 'Fei dependencies are ready.' -ForegroundColor Green
