@echo off
title BeatVault - Music & Lyrics Studio
cd /d "%~dp0"

echo ========================================================
echo             Starting BeatVault Music Studio...
echo ========================================================
echo.

python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with an error code %ERRORLEVEL%.
    pause
)
