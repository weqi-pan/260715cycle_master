# ============================================
# Cycle Master — 一键启动脚本 (PowerShell)
# ============================================
# 用法: 右键此文件 → "使用 PowerShell 运行"
# 或在终端中: .\scripts\start.ps1
# 首次使用可能需要: Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
# ============================================

$projectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Cycle Master — 荔湾·四日轮回" -ForegroundColor Yellow
Write-Host "  启动开发服务器..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---------- 检查依赖 ----------
$backendVenv = Join-Path $projectRoot "backend\venv\Scripts\python.exe"
if (-not (Test-Path $backendVenv)) {
    Write-Host "[ERROR] 后端虚拟环境不存在，请先运行: cd backend; python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

$frontendNodeModules = Join-Path $projectRoot "frontend\node_modules"
if (-not (Test-Path $frontendNodeModules)) {
    Write-Host "[WARN] 前端依赖未安装，正在安装..." -ForegroundColor Yellow
    Push-Location (Join-Path $projectRoot "frontend")
    npm install
    Pop-Location
    Write-Host "[OK] 前端依赖安装完成" -ForegroundColor Green
}

# ---------- 检查数据库 ----------
$dbFile = Join-Path $projectRoot "backend\cycle_master.db"
if (-not (Test-Path $dbFile)) {
    Write-Host "[WARN] 数据库不存在，正在导入故事数据..." -ForegroundColor Yellow
    Push-Location (Join-Path $projectRoot "backend")
    & $backendVenv -c "from app.database import init_db; init_db()"
    & $backendVenv import_story.py
    Pop-Location
    Write-Host "[OK] 数据库初始化完成" -ForegroundColor Green
}

# ---------- 启动后端 ----------
Write-Host ""
Write-Host "[1/2] 启动后端 (FastAPI :8000)..." -ForegroundColor Green
$backendDir = Join-Path $projectRoot "backend"
Start-Process powershell -ArgumentList @"
-NoExit -Command `
  Write-Host '=== Cycle Master 后端 ===' -ForegroundColor Cyan; `
  Write-Host ''; `
  Set-Location '$backendDir'; `
  .\venv\Scripts\Activate.ps1; `
  Write-Host '启动 FastAPI 服务器...' -ForegroundColor Green; `
  python -m uvicorn app.main:app --reload --port 8000
"@

# 等后端先启动
Write-Host "  等待后端启动 (5秒)..." -ForegroundColor DarkGray
Start-Sleep -Seconds 5

# ---------- 启动前端 ----------
Write-Host "[2/2] 启动前端 (Vite :5173)..." -ForegroundColor Green
$frontendDir = Join-Path $projectRoot "frontend"
Start-Process powershell -ArgumentList @"
-NoExit -Command `
  Write-Host '=== Cycle Master 前端 ===' -ForegroundColor Cyan; `
  Write-Host ''; `
  Set-Location '$frontendDir'; `
  Write-Host '启动 Vite 开发服务器...' -ForegroundColor Green; `
  npx vite --port 5173
"@

# 等前端启动
Start-Sleep -Seconds 3

# ---------- 完成 ----------
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启动完成！" -ForegroundColor Green
Write-Host "  后端:  http://localhost:8000" -ForegroundColor Yellow
Write-Host "  前端:  http://localhost:5173" -ForegroundColor Yellow
Write-Host "  游戏:  http://localhost:5173/play" -ForegroundColor Yellow
Write-Host "  API文档: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "关闭两个弹窗即可停止所有服务。" -ForegroundColor DarkGray

Read-Host "按回车退出（不会关闭后端/前端窗口）"
