@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Run.ps1" %*
if errorlevel 1 (
    echo.
    echo Universal DLSS 5 Loader could not start. See the error above.
    pause
    exit /b 1
)
exit /b 0
