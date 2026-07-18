# ============================================
# Cycle Master — 一键启动 & 一键关闭
# ============================================
# 用法: .\scripts\start.ps1
# 关闭: 按 Q 键 → 自动停止所有服务并退出
# ============================================

$projectRoot = Split-Path -Parent $PSScriptRoot
$host.UI.RawUI.WindowTitle = "Cycle Master — 荔湾·四日轮回"

# ---------- 全局进程追踪 ----------
$script:backendProcess = $null
$script:frontendProcess = $null
$script:stopping = $false

function Stop-All {
    if ($script:stopping) { return }
    $script:stopping = $true

    Write-Host ""
    Write-Host "正在停止服务..." -ForegroundColor Yellow

    if ($script:backendProcess -and !$script:backendProcess.HasExited) {
        $script:backendProcess.Kill()
        Write-Host "  [OK] 后端已停止" -ForegroundColor Green
    }
    if ($script:frontendProcess -and !$script:frontendProcess.HasExited) {
        $script:frontendProcess.Kill()
        Write-Host "  [OK] 前端已停止" -ForegroundColor Green
    }

    # 确保端口释放
    Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

    Write-Host "所有服务已停止。再见。" -ForegroundColor Cyan
    [Environment]::Exit(0)
}

# 注册退出钩子
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Stop-All } -SupportEvent

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Cycle Master — 荔湾·四日轮回" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ---------- 检查依赖 ----------
$backendVenv = Join-Path $projectRoot "backend\venv\Scripts\python.exe"
if (-not (Test-Path $backendVenv)) {
    Write-Host "[ERROR] 后端虚拟环境不存在" -ForegroundColor Red
    Write-Host "请先运行: cd backend; python -m venv venv; .\venv\Scripts\Activate.ps1; pip install -r requirements.txt" -ForegroundColor Yellow
    Read-Host "按回车退出"
    exit 1
}

$frontendNodeModules = Join-Path $projectRoot "frontend\node_modules"
if (-not (Test-Path $frontendNodeModules)) {
    Write-Host "[...] 前端依赖未安装，正在安装..." -ForegroundColor Yellow
    Push-Location (Join-Path $projectRoot "frontend")
    npm install
    Pop-Location
}

# ---------- 检查数据库 ----------
$dbFile = Join-Path $projectRoot "backend\cycle_master.db"
if (-not (Test-Path $dbFile)) {
    Write-Host "[...] 数据库不存在，正在导入..." -ForegroundColor Yellow
    Push-Location (Join-Path $projectRoot "backend")
    & $backendVenv -c "from app.database import init_db; init_db()" 2>$null
    & $backendVenv import_story.py 2>$null
    Pop-Location
}

# ---------- 清理旧进程 ----------
Write-Host "[...] 清理旧进程..." -ForegroundColor DarkGray
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1

# ---------- 启动后端 ----------
Write-Host "[1/2] 启动后端 (FastAPI :8000)..." -ForegroundColor Green
$backendDir = Join-Path $projectRoot "backend"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "$backendDir\venv\Scripts\python.exe"
$psi.Arguments = "-m uvicorn app.main:app --port 8000"
$psi.WorkingDirectory = $backendDir
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.CreateNoWindow = $true

$script:backendProcess = [System.Diagnostics.Process]::Start($psi)

# 等待后端就绪
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/api/health" -UseBasicParsing -TimeoutSec 1
        if ($r.StatusCode -eq 200) { $ready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if ($ready) {
    Write-Host "  [OK] 后端就绪" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] 后端启动失败" -ForegroundColor Red
    Stop-All
}

# ---------- 启动前端 ----------
Write-Host "[2/2] 启动前端 (Vite :5173)..." -ForegroundColor Green
$frontendDir = Join-Path $projectRoot "frontend"
$fpsi = New-Object System.Diagnostics.ProcessStartInfo
$fpsi.FileName = "npx"
$fpsi.Arguments = "vite --port 5173"
$fpsi.WorkingDirectory = $frontendDir
$fpsi.UseShellExecute = $false
$fpsi.RedirectStandardOutput = $true
$fpsi.RedirectStandardError = $true
$fpsi.CreateNoWindow = $true

$script:frontendProcess = [System.Diagnostics.Process]::Start($fpsi)

# 等待前端就绪
$fready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 1
        if ($r.StatusCode -eq 200) { $fready = $true; break }
    } catch { Start-Sleep -Milliseconds 500 }
}
if ($fready) {
    Write-Host "  [OK] 前端就绪" -ForegroundColor Green
} else {
    Write-Host "  [FAIL] 前端启动失败" -ForegroundColor Red
    Stop-All
}

# ---------- 启动完成 ----------
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  启动完成！" -ForegroundColor Green
Write-Host ""
Write-Host "  游戏:     http://localhost:5173/play" -ForegroundColor Yellow
Write-Host "  后端API:  http://localhost:8000" -ForegroundColor DarkGray
Write-Host "  API文档:  http://localhost:8000/docs" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  按 Q 键 → 停止所有服务并关闭" -ForegroundColor Magenta
Write-Host "  (或直接关闭本窗口)" -ForegroundColor DarkGray
Write-Host "========================================" -ForegroundColor Cyan

# ---------- 等待退出 ----------
while (!$script:stopping) {
    if ([Console]::KeyAvailable) {
        $key = [Console]::ReadKey($true)
        if ($key.Key -eq 'Q') {
            Stop-All
        }
    }
    # 检查进程是否仍在运行
    if ($script:backendProcess.HasExited) {
        Write-Host ""
        Write-Host "[WARN] 后端意外退出！" -ForegroundColor Red
        Stop-All
    }
    if ($script:frontendProcess.HasExited) {
        Write-Host ""
        Write-Host "[WARN] 前端意外退出！" -ForegroundColor Red
        Stop-All
    }
    Start-Sleep -Milliseconds 200
}
