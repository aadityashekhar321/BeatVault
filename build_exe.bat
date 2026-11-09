@echo off
title Build Standalone BeatVault Executable (.exe)
cd /d "%~dp0"

echo ========================================================
echo           Building Standalone BeatVault.exe...
echo ========================================================
echo.

python build_exe.py

echo.
pause
