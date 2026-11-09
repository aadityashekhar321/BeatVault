@echo off
title Push BeatVault to GitHub
cd /d "%~dp0"

echo ========================================================
echo           Pushing BeatVault to GitHub...
echo ========================================================
echo.

set "PATH=C:\Users\aadit\AppData\Local\Programs\Git\cmd;C:\Users\aadit\AppData\Local\Programs\Git\ucrt64\bin;%PATH%"

git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo      Successfully pushed BeatVault to GitHub!
    echo ========================================================
) else (
    echo.
    echo Push failed or was cancelled. Check output above.
)
echo.
pause
