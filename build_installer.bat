@echo off
setlocal
title BeatVault - Setup Installer Builder
echo ====================================================
echo      BeatVault Windows Setup Installer Builder
echo ====================================================
echo.

python build_installer.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Setup builder encountered an error.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [DONE] BeatVault-Setup.exe is ready in the 'dist' folder!
pause
