@echo off
chcp 65001 >nul
title Hardware Snapshot Agent
echo ================================================
echo   Hardware Snapshot Agent
echo   Starting local server...
echo ================================================
powershell.exe -ExecutionPolicy Bypass -NoProfile -File "%~dp0agent.ps1"
pause