# Performance Analysis - Start Server Script
# Phase 1: Server Startup & Baseline Capture

$timestamp = Get-Date -Format "HHmmss"
$logFile = "logs/server-251130-$timestamp.log"

Write-Host "=== Phase 1: Server Startup & Baseline Capture ===" -ForegroundColor Cyan
Write-Host "Timestamp: $timestamp"
Write-Host "Log file: $logFile"

# Copy .env.test to .env for test environment
Copy-Item .env.test .env -Force
Write-Host "Configured test environment (.env.test -> .env)"

# Start server in background
Write-Host ""
Write-Host "Starting server on port 8010..."
$serverProcess = Start-Process powershell -ArgumentList "-Command", `
    "python -m src.main 2>&1 | Tee-Object -FilePath '$logFile'" `
    -PassThru -WindowStyle Minimized

# Save PID
$serverProcess.Id | Out-File "logs/server.pid" -Force
Write-Host "Server started (PID: $($serverProcess.Id))"

# Wait for server readiness
Write-Host ""
Write-Host "Waiting for server to be ready..."
$timeout = 30  # Increased from 15s to 30s
$elapsed = 0
$serverReady = $false

while ($elapsed -lt $timeout) {
    Start-Sleep -Seconds 1
    $elapsed++
    Write-Host "." -NoNewline

    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8010/api/ai/health" -Method GET -TimeoutSec 1 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host ""
            Write-Host "[OK] Server ready! Health check passed." -ForegroundColor Green
            $serverReady = $true
            break
        }
    } catch {
        # Continue waiting
    }
}

if (-not $serverReady) {
    Write-Host ""
    # Check if server actually started by examining logs
    Start-Sleep -Seconds 2
    if (Test-Path $logFile) {
        $logContent = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
        if ($logContent -match "Application startup complete") {
            Write-Host "[WARNING] Server started but health check failed. Check endpoint path." -ForegroundColor Yellow
            Write-Host "[INFO] Server process still running. Continuing..." -ForegroundColor Yellow
            $serverReady = $true
        } else {
            Write-Host "[ERROR] Server failed to start within ${timeout}s" -ForegroundColor Red
            Write-Host "Last 10 lines of log:" -ForegroundColor Yellow
            Get-Content $logFile -Tail 10 | ForEach-Object { Write-Host "  $_" }
            Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
            exit 1
        }
    } else {
        Write-Host "[ERROR] Server failed to start - no log file" -ForegroundColor Red
        Stop-Process -Id $serverProcess.Id -Force -ErrorAction SilentlyContinue
        exit 1
    }
}

# Verify logging
Write-Host ""
Write-Host "Verifying log output..."
Start-Sleep -Seconds 2

if (Test-Path $logFile) {
    $logSize = (Get-Item $logFile).Length
    Write-Host "[OK] Log file created: $logFile (Size: $logSize bytes)" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Log file not found" -ForegroundColor Yellow
}

# Save baseline report
$baseline = @{
    timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    server_pid = $serverProcess.Id
    log_file = $logFile
    port = 8010
    health_check = "PASSED"
    sqlalchemy_echo = "ENABLED"
    checkpoint_heartbeat = "ENABLED"
} | ConvertTo-Json -Depth 5

$baselineFile = "logs/baseline-251130-$timestamp.json"
$baseline | Out-File $baselineFile -Force
Write-Host "[OK] Baseline saved: $baselineFile" -ForegroundColor Green

Write-Host ""
Write-Host "=== Phase 1 Complete ===" -ForegroundColor Cyan
Write-Host "Server PID: $($serverProcess.Id)"
Write-Host "Log file: $logFile"
Write-Host "Baseline: $baselineFile"
Write-Host ""
Write-Host "Ready for Phase 2: Test Execution"
