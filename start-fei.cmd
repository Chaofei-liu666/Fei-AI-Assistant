@echo off
setlocal
set "SystemRoot=C:\Windows"
set "WINDIR=C:\Windows"
set "SystemDrive=C:"
set "LOCALAPPDATA=%USERPROFILE%\AppData\Local"
set "APPDATA=%USERPROFILE%\AppData\Roaming"
set "ProgramData=C:\ProgramData"
set "ProgramFiles=C:\Program Files"
set "ProgramFiles(x86)=C:\Program Files (x86)"
where pwsh.exe >nul 2>&1
if %errorlevel% equ 0 (
  pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" %*
)
pause
