@echo off
title Push BeatVault to GitHub
cd /d "%~dp0"

echo ========================================================
echo           Pushing BeatVault to GitHub...
echo ========================================================
echo.

set "PATH=C:\Users\aadit\AppData\Local\Programs\Git\cmd;C:\Users\aadit\AppData\Local\Programs\Git\ucrt64\bin;%PATH%"

git push origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================================
    echo   [SUCCESS] BeatVault is now LIVE on your GitHub!
    echo   https://github.com/aadityashekhar321/BeatVault
    echo ========================================================
) else (
    echo.
    echo Push incomplete. If prompted, please complete GitHub authentication in browser.
)
echo.
pause
