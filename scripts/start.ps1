# Cycle Master — One-click launcher
# Usage: .\scripts\start.ps1  or double-click start.bat
# Stop:  Ctrl+C to kill all services
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot | Split-Path -Parent
$host.UI.RawUI.WindowTitle = "Cycle Master"

# Clean old ports — try multiple methods
Write-Host "[...] Cleaning old ports..." -F DarkGray

# Method 1: PowerShell cmdlet (needs admin on some Windows)
try {
    Get-NetTCPConnection -LocalPort 8000 -EA Stop | % { Stop-Process -Id $_.OwningProcess -Force -EA SilentlyContinue }
    Get-NetTCPConnection -LocalPort 5173 -EA Stop | % { Stop-Process -Id $_.OwningProcess -Force -EA SilentlyContinue }
} catch {
    # Method 2: netstat fallback (works without admin)
    $netstat = netstat -ano 2>$null
    foreach ($port in @(8000, 5173)) {
        $lines = $netstat | Select-String ":$port.*LISTENING"
        foreach ($line in $lines) {
            $pid = ($line -split '\s+')[-1]
            if ($pid -match '^\d+$') { Stop-Process -Id $pid -Force -EA SilentlyContinue }
        }
    }
}
Start-Sleep 2

# Check venv
$py = "$root\backend\venv\Scripts\python.exe"
if (!(Test-Path $py)) { Write-Host "[ERROR] venv not found at $py" -F Red; Read-Host; exit 1 }

# Check node_modules
if (!(Test-Path "$root\frontend\node_modules")) {
    Write-Host "[...] Installing frontend deps..." -F Yellow
    Push-Location "$root\frontend"; npm install; Pop-Location
}

# Init DB if missing
if (!(Test-Path "$root\backend\cycle_master.db")) {
    Write-Host "[...] Initializing database..." -F Yellow
    Push-Location "$root\backend"
    & $py -c "from app.database import init_db; init_db()"
    & $py import_story.py
    Pop-Location
}

Write-Host ""
Write-Host "========================================" -F Cyan
Write-Host "  Cycle Master - Starting..." -F Yellow
Write-Host "========================================" -F Cyan

# Start backend
Write-Host "[1/2] Backend..." -F Green -NoNewline
$backend = Start-Process -FilePath $py `
    -ArgumentList "-m uvicorn app.main:app --port 8000" `
    -WorkingDirectory "$root\backend" `
    -WindowStyle Hidden -PassThru

$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    try { if ((iwr "http://localhost:8000/api/health" -TimeoutSec 1 -UseBasicParsing).StatusCode -eq 200) { $ok = $true; break } } catch {}
    Start-Sleep -Milliseconds 500
}
if ($backend.HasExited -or !$ok) { Write-Host " FAIL" -F Red; Read-Host; exit 1 }
Write-Host " OK :8000" -F Green

# Start frontend
Write-Host "[2/2] Frontend..." -F Green -NoNewline
$frontend = Start-Process -FilePath "npx" `
    -ArgumentList "vite --port 5173" `
    -WorkingDirectory "$root\frontend" `
    -WindowStyle Hidden -PassThru

$ok = $false
for ($i = 0; $i -lt 20; $i++) {
    try { if ((iwr "http://localhost:5173" -TimeoutSec 1 -UseBasicParsing).StatusCode -eq 200) { $ok = $true; break } } catch {}
    Start-Sleep -Milliseconds 500
}
if ($frontend.HasExited -or !$ok) { Write-Host " FAIL" -F Red; Read-Host; exit 1 }
Write-Host " OK :5173" -F Green

Write-Host ""
Write-Host "========================================" -F Cyan
Write-Host "  Game:     http://localhost:5173/play" -F Yellow
Write-Host "  Backend:  http://localhost:8000" -F DarkGray
Write-Host "  API docs: http://localhost:8000/docs" -F DarkGray
Write-Host "  Press Ctrl+C to stop all services" -F Magenta
Write-Host "========================================" -F Cyan
Write-Host ""

# Wait and watch
try {
    while ($true) {
        if ($backend.HasExited) { Write-Host "[WARN] Backend stopped unexpectedly" -F Red; break }
        if ($frontend.HasExited) { Write-Host "[WARN] Frontend stopped unexpectedly" -F Red; break }
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host "`nStopping services..." -F Yellow
    if (!$backend.HasExited) { $backend.Kill() }
    if (!$frontend.HasExited) { $frontend.Kill() }
    # Extra port cleanup
    taskkill //F //IM python.exe 2>$null
    taskkill //F //IM node.exe 2>$null
    Write-Host "Stopped." -F Green
}
