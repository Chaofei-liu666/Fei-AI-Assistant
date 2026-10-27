param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('api', 'langgraph', 'web')]
    [string]$Service
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Initialize-WindowsEnvironment.ps1')
$projectRoot = Split-Path $PSScriptRoot -Parent
Set-Location $projectRoot

switch ($Service) {
    'api' {
        & .\.venv\Scripts\fei-api.exe
    }
    'langgraph' {
        & .\.venv\Scripts\langgraph.exe dev --host 127.0.0.1 --port 2024 --no-browser --no-reload
    }
    'web' {
        Set-Location (Join-Path $projectRoot 'web')
        npm run dev
    }
}
