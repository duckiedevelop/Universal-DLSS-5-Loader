@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" %*
if errorlevel 1 (
    echo.
    echo Build failed. See the error above.
    pause
    exit /b 1
)
echo.
echo Ready. Double-click Launch.cmd to open Universal DLSS 5 Loader.
pause
exit /b 0
