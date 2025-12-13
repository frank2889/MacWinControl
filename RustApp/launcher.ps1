# MacWinControl Auto-Update Launcher for Windows
# Run this instead of the app directly

$ErrorActionPreference = "Stop"
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath

Write-Host "🔄 MacWinControl Launcher" -ForegroundColor Cyan
Write-Host "=========================" -ForegroundColor Cyan

function Check-AndUpdate {
    Write-Host "`n📥 Checking for updates..." -ForegroundColor Yellow
    
    # Fetch latest
    git fetch origin main 2>$null
    
    # Check if we're behind
    $local = git rev-parse HEAD
    $remote = git rev-parse origin/main
    
    if ($local -ne $remote) {
        Write-Host "🆕 Update available! Pulling..." -ForegroundColor Green
        git pull origin main
        return $true
    } else {
        Write-Host "✅ Already up to date" -ForegroundColor Green
        return $false
    }
}

function Build-App {
    Write-Host "`n🔨 Building app..." -ForegroundColor Yellow
    
    # Check if executable exists
    $exePath = "src-tauri\target\release\macwincontrol.exe"
    
    # Get last commit time
    $lastCommit = git log -1 --format="%ct"
    
    # Check if rebuild needed
    $needsBuild = $true
    if (Test-Path $exePath) {
        $exeTime = (Get-Item $exePath).LastWriteTime
        $commitTime = [DateTimeOffset]::FromUnixTimeSeconds($lastCommit).LocalDateTime
        if ($exeTime -gt $commitTime) {
            Write-Host "✅ Build is current" -ForegroundColor Green
            $needsBuild = $false
        }
    }
    
    if ($needsBuild) {
        Write-Host "🔧 Compiling (this may take a minute)..." -ForegroundColor Yellow
        cargo build --release 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) {
            Write-Host "❌ Build failed!" -ForegroundColor Red
            return $false
        }
        Write-Host "✅ Build complete!" -ForegroundColor Green
    }
    
    return $true
}

function Start-App {
    Write-Host "`n🚀 Starting MacWinControl..." -ForegroundColor Cyan
    
    $exePath = "src-tauri\target\release\macwincontrol.exe"
    if (Test-Path $exePath) {
        Start-Process $exePath
        return $true
    } else {
        Write-Host "❌ Executable not found!" -ForegroundColor Red
        return $false
    }
}

function Watch-ForUpdates {
    param($appProcess)
    
    Write-Host "`n👀 Watching for updates (check every 30 seconds)..." -ForegroundColor Gray
    
    while ($true) {
        Start-Sleep -Seconds 30
        
        # Check if app is still running
        $running = Get-Process -Name "macwincontrol" -ErrorAction SilentlyContinue
        if (-not $running) {
            Write-Host "📱 App closed, exiting launcher" -ForegroundColor Yellow
            break
        }
        
        # Check for updates
        git fetch origin main 2>$null
        $local = git rev-parse HEAD
        $remote = git rev-parse origin/main
        
        if ($local -ne $remote) {
            Write-Host "`n🆕 Update detected! Restarting app..." -ForegroundColor Green
            
            # Kill current app
            Stop-Process -Name "macwincontrol" -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            
            # Update and rebuild
            git pull origin main
            Build-App
            Start-App
            
            Write-Host "✅ App restarted with updates!" -ForegroundColor Green
        }
    }
}

# Main flow
try {
    # Initial update check
    $updated = Check-AndUpdate
    
    # Build if needed
    $buildOk = Build-App
    if (-not $buildOk) {
        Write-Host "Press any key to exit..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
    
    # Start app
    $started = Start-App
    if (-not $started) {
        Write-Host "Press any key to exit..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
    
    # Watch for updates in background
    Watch-ForUpdates
    
} catch {
    Write-Host "❌ Error: $_" -ForegroundColor Red
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}
