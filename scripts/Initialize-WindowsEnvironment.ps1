# Codex and some embedded terminals can start with a deliberately minimal
# environment. Windows networking and crypto providers still require these
# standard variables to resolve system DLL paths.
$userProfile = if ($env:USERPROFILE) { $env:USERPROFILE } else { [Environment]::GetFolderPath('UserProfile') }
$systemRoot = [Environment]::GetEnvironmentVariable('SystemRoot', 'Machine')
if (-not $systemRoot) { $systemRoot = 'C:\Windows' }

$env:SystemRoot = $systemRoot
$env:WINDIR = $systemRoot
$env:SystemDrive = [IO.Path]::GetPathRoot($systemRoot).TrimEnd('\')
$env:USERPROFILE = $userProfile

if (-not $env:LOCALAPPDATA) { $env:LOCALAPPDATA = Join-Path $userProfile 'AppData\Local' }
if (-not $env:APPDATA) { $env:APPDATA = Join-Path $userProfile 'AppData\Roaming' }
if (-not $env:ProgramData) { $env:ProgramData = 'C:\ProgramData' }
if (-not $env:ProgramFiles) { $env:ProgramFiles = 'C:\Program Files' }
if (-not (Test-Path 'Env:ProgramFiles(x86)')) {
    Set-Item -Path 'Env:ProgramFiles(x86)' -Value 'C:\Program Files (x86)'
}
if (-not $env:CommonProgramFiles) { $env:CommonProgramFiles = 'C:\Program Files\Common Files' }
if (-not (Test-Path 'Env:CommonProgramFiles(x86)')) {
    Set-Item -Path 'Env:CommonProgramFiles(x86)' -Value 'C:\Program Files (x86)\Common Files'
}
if (-not $env:HOMEDRIVE) { $env:HOMEDRIVE = [IO.Path]::GetPathRoot($userProfile).TrimEnd('\') }
if (-not $env:HOMEPATH) { $env:HOMEPATH = $userProfile.Substring($env:HOMEDRIVE.Length) }
if (-not $env:USERNAME) { $env:USERNAME = Split-Path $userProfile -Leaf }
if (-not $env:COMPUTERNAME) { $env:COMPUTERNAME = [Environment]::MachineName }

$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
