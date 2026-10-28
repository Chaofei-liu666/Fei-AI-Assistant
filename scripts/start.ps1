param(
    [switch]$NoBrowser,
    [int]$StartupTimeoutSeconds = 120
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Initialize-WindowsEnvironment.ps1')
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeDir = Join-Path $projectRoot '.runtime'
Set-Location $projectRoot

if (-not (Test-Path '.venv\Scripts\fei-api.exe') -or -not (Test-Path 'web\node_modules') -or -not (Test-Path 'desktop\node_modules')) {
    throw 'Dependencies are missing. Run scripts\setup.ps1 first.'
}

if (-not (Test-Path '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
if (-not (Test-Path 'web\.env.local')) {
    Copy-Item -LiteralPath 'web\.env.example' -Destination 'web\.env.local'
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $dockerDesktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path -LiteralPath $dockerDesktop)) { throw 'Docker Desktop is not installed.' }
    Start-Process -FilePath $dockerDesktop -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    do {
        Start-Sleep -Seconds 2
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { break }
    } while ((Get-Date) -lt $deadline)
    if ($LASTEXITCODE -ne 0) { throw 'Docker Desktop did not become ready in time.' }
}

docker-compose up -d

$deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
do {
    $postgresHealth = docker inspect --format='{{.State.Health.Status}}' new-postgres-1 2>$null
    if ($postgresHealth -eq 'healthy') { break }
    Start-Sleep -Seconds 2
} while ((Get-Date) -lt $deadline)
if ($postgresHealth -ne 'healthy') { throw 'PostgreSQL did not become healthy in time.' }

& .\.venv\Scripts\python.exe -m alembic upgrade head
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

$shell = if (Get-Command pwsh.exe -ErrorAction SilentlyContinue) { 'pwsh.exe' } else { 'powershell.exe' }
$runner = Join-Path $PSScriptRoot 'Run-Service.ps1'
$services = @(
    @{ Name = 'api'; Port = 8000 },
    @{ Name = 'langgraph'; Port = 2024 },
    @{ Name = 'web'; Port = 3000 }
)

foreach ($service in $services) {
    $pidFile = Join-Path $runtimeDir ($service.Name + '.pid')
    $alreadyRunning = $false
    if (Test-Path $pidFile) {
        $savedPid = [int](Get-Content $pidFile -Raw)
        $alreadyRunning = $null -ne (Get-Process -Id $savedPid -ErrorAction SilentlyContinue)
    }
    if (-not $alreadyRunning) {
        $stdout = Join-Path $runtimeDir ($service.Name + '.log')
        $stderr = Join-Path $runtimeDir ($service.Name + '.error.log')
        $process = Start-Process -FilePath $shell -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $runner, '-Service', $service.Name
        ) -WorkingDirectory $projectRoot -RedirectStandardOutput $stdout -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
        Set-Content -LiteralPath $pidFile -Value $process.Id
    }
}

function Test-LocalPort([int]$Port) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $task = $client.ConnectAsync('127.0.0.1', $Port)
        return $task.Wait(500) -and $client.Connected
    }
    catch { return $false }
    finally { $client.Dispose() }
}

$deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
do {
    $missing = @($services | Where-Object { -not (Test-LocalPort $_.Port) })
    if ($missing.Count -eq 0) { break }
    Start-Sleep -Seconds 1
} while ((Get-Date) -lt $deadline)

if ($missing.Count -gt 0) {
    $names = ($missing | ForEach-Object { $_.Name }) -join ', '
    throw "Services did not become ready: $names. See .runtime\*.error.log."
}

Write-Host 'Fei 智能助手已启动：' -ForegroundColor Green
Write-Host '  桌面应用:  Fei 智能助手'
Write-Host '  本地 Web:  http://127.0.0.1:3000'
Write-Host '  API 文档: http://127.0.0.1:8000/docs'
Write-Host '  LangGraph: http://127.0.0.1:2024'

if (-not $NoBrowser) {
    $desktopPidFile = Join-Path $runtimeDir 'desktop.pid'
    $desktopRunning = $false
    if (Test-Path $desktopPidFile) {
        $desktopPid = [int](Get-Content $desktopPidFile -Raw)
        $desktopRunning = $null -ne (Get-Process -Id $desktopPid -ErrorAction SilentlyContinue)
    }
    if (-not $desktopRunning) {
        $desktopOut = Join-Path $runtimeDir 'desktop.log'
        $desktopError = Join-Path $runtimeDir 'desktop.error.log'
        $desktopProcess = Start-Process -FilePath $shell -ArgumentList @(
            '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $runner, '-Service', 'desktop'
        ) -WorkingDirectory $projectRoot -RedirectStandardOutput $desktopOut -RedirectStandardError $desktopError -WindowStyle Hidden -PassThru
        Set-Content -LiteralPath $desktopPidFile -Value $desktopProcess.Id
    }
}
