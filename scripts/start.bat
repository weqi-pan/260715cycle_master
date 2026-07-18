@echo off
REM ============================================
REM Cycle Master — 一键启动 (双击运行)
REM 关闭: 按 Q 键即可停止所有服务
REM ============================================
title Cycle Master
echo.
echo   按 Q 键可随时停止所有服务
echo.
powershell -NoProfile -ExecutionPolicy RemoteSigned -File "%~dp0start.ps1"
