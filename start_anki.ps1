# Start Anki for agent integration
# PowerShell version of start_anki.sh
#
# Priority order:
# 1. Docker container (preferred) - works on all platforms
# 2. Native Anki app (fallback) - if Docker unavailable
#
# Set $env:FORCE_NATIVE_APP=1 to skip Docker and use native app directly

$ErrorActionPreference = "Stop"

# Colors for output
function Write-ColorOutput($ForegroundColor, $Message) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    Write-Output $Message
    $host.UI.RawUI.ForegroundColor = $fc
}

# Detect platform
$OS = if ($IsWindows) { "Windows" } elseif ($IsMacOS) { "Darwin" } elseif ($IsLinux) { "Linux" } else { "Unknown" }
$ARCH = if ([Environment]::Is64BitOperatingSystem) { "x86_64" } else { "x86" }

# Native app fallback disabled by default
# Set $env:ANKI_APP_FALLBACK_ENABLED=1 to re-enable
$ANKI_APP_FALLBACK_ENABLED = if ($env:ANKI_APP_FALLBACK_ENABLED -eq "1") { $true } else { $false }

# =============================================================================
# FUNCTION: Start native Anki app (Windows)
# =============================================================================
function Start-NativeAnkiWindows {
    Write-ColorOutput "Cyan" "Using native Anki app"
    Write-Output ""
    
    # Check if Anki is installed (common locations)
    $ankiPaths = @(
        "$env:ProgramFiles\Anki\anki.exe",
        "$env:ProgramFiles(x86)\Anki\anki.exe",
        "$env:LOCALAPPDATA\Programs\Anki\anki.exe",
        "$env:USERPROFILE\AppData\Local\Programs\Anki\anki.exe"
    )
    
    $ankiPath = $null
    foreach ($path in $ankiPaths) {
        if (Test-Path $path) {
            $ankiPath = $path
            break
        }
    }
    
    if (-not $ankiPath) {
        Write-ColorOutput "Red" "Error: Anki is not installed."
        Write-Output ""
        Write-Output "Please install Anki from: https://apps.ankiweb.net/"
        Write-Output "Then install the AnkiConnect add-on:"
        Write-Output "  1. Open Anki"
        Write-Output "  2. Go to Tools > Add-ons > Get Add-ons"
        Write-Output "  3. Enter code: 2055492159"
        Write-Output "  4. Restart Anki"
        return $false
    }
    
    # Check if AnkiConnect is installed
    $ankiconnectPath = "$env:APPDATA\Anki2\addons21\2055492159"
    if (-not (Test-Path $ankiconnectPath)) {
        Write-ColorOutput "Yellow" "AnkiConnect add-on not found."
        Write-Output ""
        Write-Output "Please install AnkiConnect:"
        Write-Output "  1. Open Anki"
        Write-Output "  2. Go to Tools > Add-ons > Get Add-ons"
        Write-Output "  3. Enter code: 2055492159"
        Write-Output "  4. Restart Anki"
        Write-Output ""
        Write-Output "Opening Anki now..."
        Start-Process $ankiPath
        return $false
    }
    
    # Check if Anki is running
    $ankiProcess = Get-Process -Name "anki" -ErrorAction SilentlyContinue
    if (-not $ankiProcess) {
        Write-Output "Starting Anki..."
        Start-Process $ankiPath
        Start-Sleep -Seconds 3
    }
    
    # Wait for AnkiConnect to be ready
    Write-Output "Waiting for AnkiConnect API..."
    $maxWait = 30
    $waited = 0
    $ready = $false
    
    while ($waited -lt $maxWait) {
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:8765" -Method GET -TimeoutSec 1 -ErrorAction SilentlyContinue -UseBasicParsing
            $ready = $true
            break
        } catch {
            Start-Sleep -Seconds 1
            $waited++
        }
    }
    
    if (-not $ready) {
        Write-ColorOutput "Red" "Error: AnkiConnect is not responding."
        Write-Output ""
        Write-Output "Please ensure:"
        Write-Output "  1. Anki is running"
        Write-Output "  2. AnkiConnect add-on is installed (code: 2055492159)"
        Write-Output "  3. You've restarted Anki after installing the add-on"
        return $false
    }
    
    Write-ColorOutput "Green" "[OK] AnkiConnect API is ready at http://localhost:8765"
    Write-Output ""
    Write-Output "========================================"
    Write-ColorOutput "Green" "Anki is ready!"
    Write-Output "========================================"
    Write-Output ""
    Write-Output "Keep Anki running in the background."
    Write-Output "The agent can now create flashcards and read statistics."
    Write-Output ""
    Write-Output "To sync cards to your phone:"
    Write-Output "  1. Click the Sync button in Anki (or press Y)"
    Write-Output "  2. Login to AnkiWeb if prompted"
    Write-Output ""
    return $true
}

# =============================================================================
# FUNCTION: Show native app instructions
# =============================================================================
function Show-NativeAppInstructions {
    Write-Output ""
    Write-ColorOutput "Yellow" "========================================"
    Write-Output "MANUAL SETUP REQUIRED"
    Write-Output "========================================"
    Write-Output ""
    Write-Output "Docker is not available. Please install Anki manually:"
    Write-Output ""
    Write-Output "  1. Download Anki from: https://apps.ankiweb.net/"
    Write-Output "  2. Install and open Anki"
        Write-Output "  3. Go to Tools > Add-ons > Get Add-ons"
    Write-Output "  4. Enter code: 2055492159 (AnkiConnect)"
    Write-Output "  5. Restart Anki"
    Write-Output "  6. Keep Anki running in the background"
    Write-Output ""
    Write-Output "Once Anki is running with AnkiConnect, the agent will"
    Write-Output "automatically connect to http://localhost:8765"
    Write-Output ""
    
    # Check if AnkiConnect is already responding
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8765" -Method GET -TimeoutSec 1 -ErrorAction SilentlyContinue -UseBasicParsing
        Write-ColorOutput "Green" "[OK] AnkiConnect is already running!"
        Write-Output "The agent can now create flashcards and read statistics."
        return $true
    } catch {
        Write-Output "AnkiConnect is not currently responding."
        Write-Output "Start Anki and try again."
        return $false
    }
}

# =============================================================================
# FUNCTION: Fallback to native app
# =============================================================================
function Fallback-ToNativeApp {
    Write-Output ""
    Write-ColorOutput "Yellow" "Falling back to native Anki app..."
    Write-Output ""
    
    if ($OS -eq "Windows") {
        $result = Start-NativeAnkiWindows
        return $result
    } else {
        $result = Show-NativeAppInstructions
        return $result
    }
}

# =============================================================================
# FUNCTION: Try fallback or show error
# =============================================================================
function Try-FallbackOrError {
    if ($ANKI_APP_FALLBACK_ENABLED) {
        $result = Fallback-ToNativeApp
        return $result
    } else {
        Write-ColorOutput "Red" "Docker is required. Native app fallback is disabled."
        Write-Output "Set `$env:ANKI_APP_FALLBACK_ENABLED=1 to enable native app fallback."
        return $false
    }
}

# =============================================================================
# MAIN SCRIPT
# =============================================================================

Write-Output "========================================"
Write-Output "Anki Agent Integration Setup"
Write-Output "========================================"
Write-Output "Detected: $OS ($ARCH)"
Write-Output ""

# -----------------------------------------------------------------------------
# Check for forced native app mode
# -----------------------------------------------------------------------------
if ($env:FORCE_NATIVE_APP -eq "1") {
    Write-ColorOutput "Cyan" "FORCE_NATIVE_APP=1 set, skipping Docker"
    if ($OS -eq "Windows") {
        $result = Start-NativeAnkiWindows
        exit $(if ($result) { 0 } else { 1 })
    } else {
        $result = Show-NativeAppInstructions
        exit $(if ($result) { 0 } else { 1 })
    }
}

# -----------------------------------------------------------------------------
# Try Docker first (preferred method)
# -----------------------------------------------------------------------------
Write-ColorOutput "Cyan" "Trying Docker container (preferred method)..."

# Check Docker is installed
try {
    $null = Get-Command docker -ErrorAction Stop
} catch {
    Write-ColorOutput "Yellow" "Docker is not installed."
    $result = Try-FallbackOrError
    exit $(if ($result) { 0 } else { 1 })
}

# Check Docker is running
try {
    docker info | Out-Null
} catch {
    Write-ColorOutput "Yellow" "Docker is not running."
    Write-Output "You can start Docker Desktop, or use the native app fallback."
    $result = Try-FallbackOrError
    exit $(if ($result) { 0 } else { 1 })
}

Write-ColorOutput "Green" "[OK] Docker is running"

# Check if container is already running
$existingContainer = docker ps -a --filter "name=anki-agent" --format "{{.Names}}" 2>&1
if ($existingContainer -eq "anki-agent") {
    $running = docker ps --filter "name=anki-agent" --format "{{.Names}}" 2>&1
    if ($running -eq "anki-agent") {
        Write-ColorOutput "Green" "[OK] Anki container is already running"
    } else {
        Write-Output "Anki container exists but is not running. Starting it..."
        docker start anki-agent 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "Green" "[OK] Container started"
        }
    }
} else {
    # Start the Anki container
    Write-Output "Starting Anki container..."
    Write-Output "(First run will build the image - this may take several minutes)"

    try {
        $dockerOutput = docker compose up -d --build 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-ColorOutput "Red" "Docker compose failed with exit code: $LASTEXITCODE"
            Write-Output ""
            Write-Output "Docker output:"
            Write-Output $dockerOutput
            Write-Output ""
            throw "Docker compose failed"
        } else {
            Write-Output $dockerOutput
        }
    } catch {
        Write-ColorOutput "Yellow" "Failed to start Docker container."
        Write-Output ""
        Write-Output "Common issues:"
        Write-Output "  - Docker Desktop might not be running"
        Write-Output "  - Port 8765 might already be in use"
        Write-Output "  - Insufficient disk space or memory"
        Write-Output "  - Check logs with: docker compose logs"
        Write-Output ""
        $result = Try-FallbackOrError
        exit $(if ($result) { 0 } else { 1 })
    }
}

# Wait for AnkiConnect to be ready
Write-Output "Waiting for AnkiConnect API..."
$maxWait = 120
$waited = 0
$ready = $false

while ($waited -lt $maxWait) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8765" -Method GET -TimeoutSec 1 -ErrorAction SilentlyContinue -UseBasicParsing
        $ready = $true
        break
    } catch {
        Start-Sleep -Seconds 2
        $waited += 2
        Write-Output "  Still waiting... $waited seconds / $maxWait seconds"
    }
}

if (-not $ready) {
    Write-ColorOutput "Yellow" "AnkiConnect did not start within $maxWait seconds"
    Write-Output "Check container logs with: docker logs anki-agent"
    Write-Output ""
    $result = Try-FallbackOrError
    exit $(if ($result) { 0 } else { 1 })
}

Write-ColorOutput "Green" "✓ AnkiConnect API is ready at http://localhost:8765"

Write-Output ""
Write-Output "========================================"
Write-ColorOutput "Green" "Anki is ready!"
Write-Output "========================================"
Write-Output ""
Write-Output "Container is running in the background."
Write-Output ""
Write-Output "To sync with AnkiWeb:"
Write-Output "  1. Start the backend and frontend"
Write-Output "  2. Open the app at http://localhost:3000"
Write-Output "  3. Go to Settings > AnkiWeb Connection"
Write-Output "  4. Enter your AnkiWeb credentials"
Write-Output ""
Write-Output "Useful commands:"
Write-Output "  docker compose logs -f  # View container logs"
Write-Output "  docker compose down     # Stop container"
Write-Output ""
