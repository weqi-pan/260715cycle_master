# ============================================
# Cycle Master — 一键启动 & 一键关闭
# 用法: .\scripts\start.ps1  或双击 start.bat
# 关闭: 按 Ctrl+C 或直接关闭窗口
# ============================================
$ErrorActionPreference = "Stop"
$projectRoot = $PSScriptRoot | Split-Path -Parent
$host.UI.RawUI.WindowTitle = "Cycle Master"

# ---------- 清理旧进程 ----------
Write-Host "[...] 清理旧端口..." -ForegroundColor DarkGray
Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000 -EA SilentlyContinue).OwningProcess -Force -EA SilentlyContinue
Stop-Process -Id (Get-NetTCPConnection -LocalPort 5173 -EA SilentlyContinue).OwningProcess -Force -EA SilentlyContinue
Start-Sleep 1

# ---------- 检查依赖 ----------
$py = "$projectRoot\backend\venv\Scripts\python.exe"
if (!(Test-Path $py)) { Write-Host "[ERROR] venv 不存在" -F Red; Read-Host; exit 1 }
if (!(Test-Path "$projectRoot\frontend\node_modules")) {
    Write-Host "[...] 安装前端依赖..." -F Yellow
    Push-Location "$projectRoot\frontend"; npm install; Pop-Location
}

# ---------- 检查数据库 ----------
if (!(Test-Path "$projectRoot\backend\cycle_master.db")) {
    Write-Host "[...] 初始化数据库..." -F Yellow
    Push-Location "$projectRoot\backend"
    & $py -c "from app.database import init_db; init_db()" 2>$null
    & $py import_story.py 2>$null
    Pop-Location
}

Write-Host ""
Write-Host "========================================" -F Cyan
Write-Host "  Cycle Master - 启动中..." -F Yellow
Write-Host "========================================" -F Cyan

# ---------- 启动后端 ----------
Write-Host "[1/2] 后端..." -F Green -NoNewline
$backend = Start-Process -FilePath $py `
    -ArgumentList "-m uvicorn app.main:app --port 8000" `
    -WorkingDirectory "$projectRoot\backend" `
    -WindowStyle Hidden -PassThru

for ($i=0; $i -lt 20; $i++) {
    try { if ((Invoke-WebRequest "http://localhost:8000/api/health" -TimeoutSec 1 -UseBasicParsing).StatusCode -eq 200) { break } } catch {}
    Start-Sleep -Milliseconds 500
}
if ($backend.HasExited) { Write-Host " FAIL" -F Red; Read-Host; exit 1 }
Write-Host " OK :8000" -F Green

# ---------- 启动前端 ----------
Write-Host "[2/2] 前端..." -F Green -NoNewline
$frontend = Start-Process -FilePath "npx" `
    -ArgumentList "vite --port 5173" `
    -WorkingDirectory "$projectRoot\frontend" `
    -WindowStyle Hidden -PassThru

for ($i=0; $i -lt 20; $i++) {
    try { if ((Invoke-WebRequest "http://localhost:5173" -TimeoutSec 1 -UseBasicParsing).StatusCode -eq 200) { break } } catch {}
    Start-Sleep -Milliseconds 500
}
if ($frontend.HasExited) { Write-Host " FAIL" -F Red; Read-Host; exit 1 }
Write-Host " OK :5173" -F Green

# ---------- 完成 ----------
Write-Host ""
Write-Host "========================================" -F Cyan
Write-Host "  游戏:     http://localhost:5173/play" -F Yellow
Write-Host "  后端API:  http://localhost:8000" -F DarkGray
Write-Host "  按 Ctrl+C 停止所有服务" -F Magenta
Write-Host "========================================" -F Cyan
Write-Host ""

# ---------- 等待 Ctrl+C ----------
try {
    while ($true) {
        if ($backend.HasExited) { Write-Host "[WARN] 后端意外退出" -F Red; break }
        if ($frontend.HasExited) { Write-Host "[WARN] 前端意外退出" -F Red; break }
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host "`n停止服务..." -F Yellow
    if (!$backend.HasExited) { $backend.Kill() }
    if (!$frontend.HasExited) { $frontend.Kill() }
    Stop-Process -Id (Get-NetTCPConnection -LocalPort 8000 -EA SilentlyContinue).OwningProcess -Force -EA SilentlyContinue
    Stop-Process -Id (Get-NetTCPConnection -LocalPort 5173 -EA SilentlyContinue).OwningProcess -Force -EA SilentlyContinue
    Write-Host "已停止。" -F Green
}
