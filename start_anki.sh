#!/bin/bash
# Start Anki for agent integration
#
# Priority order:
# 1. Docker container (preferred) - works on all platforms
# 2. Native Anki app (fallback) - if Docker unavailable
#
# Set FORCE_NATIVE_APP=1 to skip Docker and use native app directly

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect platform
ARCH=$(uname -m)
OS=$(uname -s)

# Native app fallback disabled by default
# Set ANKI_APP_FALLBACK_ENABLED=1 to re-enable
ANKI_APP_FALLBACK_ENABLED="${ANKI_APP_FALLBACK_ENABLED:-0}"

# =============================================================================
# FUNCTION: Start native Anki app (macOS only)
# =============================================================================
start_native_anki_macos() {
    echo -e "${BLUE}Using native Anki app${NC}"
    echo ""
    
    # Check if Anki is installed
    if [ ! -d "/Applications/Anki.app" ]; then
        echo -e "${RED}Error: Anki is not installed.${NC}"
        echo ""
        echo "Please install Anki from: https://apps.ankiweb.net/"
        echo "Then install the AnkiConnect add-on:"
        echo "  1. Open Anki"
        echo "  2. Go to Tools → Add-ons → Get Add-ons"
        echo "  3. Enter code: 2055492159"
        echo "  4. Restart Anki"
        return 1
    fi
    
    # Check if AnkiConnect is installed
    ANKICONNECT_PATH="$HOME/Library/Application Support/Anki2/addons21/2055492159"
    if [ ! -d "$ANKICONNECT_PATH" ]; then
        echo -e "${YELLOW}AnkiConnect add-on not found.${NC}"
        echo ""
        echo "Please install AnkiConnect:"
        echo "  1. Open Anki"
        echo "  2. Go to Tools → Add-ons → Get Add-ons"
        echo "  3. Enter code: 2055492159"
        echo "  4. Restart Anki"
        echo ""
        echo "Opening Anki now..."
        open -a Anki
        return 1
    fi
    
    # Check if Anki is running
    if ! pgrep -x "Anki" > /dev/null; then
        echo "Starting Anki..."
        open -a Anki
        sleep 3
    fi
    
    # Wait for AnkiConnect to be ready
    echo "Waiting for AnkiConnect API..."
    MAX_WAIT=30
    WAITED=0
    until curl -s http://localhost:8765 > /dev/null 2>&1; do
        sleep 1
        WAITED=$((WAITED + 1))
        if [ $WAITED -ge $MAX_WAIT ]; then
            echo -e "${RED}Error: AnkiConnect is not responding.${NC}"
            echo ""
            echo "Please ensure:"
            echo "  1. Anki is running"
            echo "  2. AnkiConnect add-on is installed (code: 2055492159)"
            echo "  3. You've restarted Anki after installing the add-on"
            return 1
        fi
    done
    
    echo -e "${GREEN}✓ AnkiConnect API is ready at http://localhost:8765${NC}"
    echo ""
    echo "========================================"
    echo -e "${GREEN}Anki is ready!${NC}"
    echo "========================================"
    echo ""
    echo "Keep Anki running in the background."
    echo "The agent can now create flashcards and read statistics."
    echo ""
    echo "To sync cards to your phone:"
    echo "  1. Click the Sync button in Anki (or press Y)"
    echo "  2. Login to AnkiWeb if prompted"
    echo ""
    return 0
}

# =============================================================================
# FUNCTION: Show native app instructions for Linux/Windows
# =============================================================================
show_native_app_instructions() {
    echo ""
    echo -e "${YELLOW}========================================"
    echo "MANUAL SETUP REQUIRED"
    echo "========================================${NC}"
    echo ""
    echo "Docker is not available. Please install Anki manually:"
    echo ""
    echo "  1. Download Anki from: https://apps.ankiweb.net/"
    echo "  2. Install and open Anki"
    echo "  3. Go to Tools → Add-ons → Get Add-ons"
    echo "  4. Enter code: 2055492159 (AnkiConnect)"
    echo "  5. Restart Anki"
    echo "  6. Keep Anki running in the background"
    echo ""
    echo "Once Anki is running with AnkiConnect, the agent will"
    echo "automatically connect to http://localhost:8765"
    echo ""
    
    # Check if AnkiConnect is already responding
    if curl -s http://localhost:8765 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ AnkiConnect is already running!${NC}"
        echo "The agent can now create flashcards and read statistics."
        return 0
    else
        echo "AnkiConnect is not currently responding."
        echo "Start Anki and try again."
        return 1
    fi
}

# =============================================================================
# FUNCTION: Fallback to native app
# =============================================================================
fallback_to_native_app() {
    echo ""
    echo -e "${YELLOW}Falling back to native Anki app...${NC}"
    echo ""
    
    if [[ "$OS" == "Darwin" ]]; then
        # macOS - try to start native app
        start_native_anki_macos
        return $?
    else
        # Linux/Windows - show instructions
        show_native_app_instructions
        return $?
    fi
}

# =============================================================================
# FUNCTION: Try fallback or show error (respects ANKI_APP_FALLBACK_ENABLED)
# =============================================================================
try_fallback_or_error() {
    if [[ "$ANKI_APP_FALLBACK_ENABLED" == "1" ]]; then
        fallback_to_native_app
        return $?
    else
        echo -e "${RED}Docker is required. Native app fallback is disabled.${NC}"
        echo "Set ANKI_APP_FALLBACK_ENABLED=1 to enable native app fallback."
        return 1
    fi
}

# =============================================================================
# MAIN SCRIPT
# =============================================================================

echo "========================================"
echo "Anki Agent Integration Setup"
echo "========================================"
echo "Detected: $OS ($ARCH)"
echo ""

# -----------------------------------------------------------------------------
# Check for forced native app mode
# -----------------------------------------------------------------------------
if [[ "${FORCE_NATIVE_APP:-0}" == "1" ]]; then
    echo -e "${BLUE}FORCE_NATIVE_APP=1 set, skipping Docker${NC}"
    if [[ "$OS" == "Darwin" ]]; then
        start_native_anki_macos
        exit $?
    else
        show_native_app_instructions
        exit $?
    fi
fi

# -----------------------------------------------------------------------------
# Try Docker first (preferred method)
# -----------------------------------------------------------------------------
echo -e "${BLUE}Trying Docker container (preferred method)...${NC}"

# Check Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker is not installed.${NC}"
    try_fallback_or_error
    exit $?
fi

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${YELLOW}Docker is not running.${NC}"
    echo "You can start Docker Desktop, or use the native app fallback."
    try_fallback_or_error
    exit $?
fi

echo -e "${GREEN}✓ Docker is running${NC}"

# Start the Anki container (builds from ankimcp/headless-anki on first run)
echo "Starting Anki container..."
echo "(First run will build the image - this may take several minutes)"

if ! docker compose up -d --build 2>&1; then
    echo -e "${YELLOW}Failed to start Docker container.${NC}"
    try_fallback_or_error
    exit $?
fi

# Wait for AnkiConnect to be ready
echo "Waiting for AnkiConnect API..."
MAX_WAIT=120
WAITED=0
until curl -s http://localhost:8765 > /dev/null 2>&1; do
    sleep 2
    WAITED=$((WAITED + 2))
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo -e "${YELLOW}AnkiConnect did not start within ${MAX_WAIT} seconds${NC}"
        echo "Check container logs with: docker logs anki-agent"
        echo ""
        try_fallback_or_error
        exit $?
    fi
    echo "  Still waiting... (${WAITED}s / ${MAX_WAIT}s)"
done

echo -e "${GREEN}✓ AnkiConnect API is ready at http://localhost:8765${NC}"

echo ""
echo "========================================"
echo -e "${GREEN}Anki is ready!${NC}"
echo "========================================"
echo ""
echo "Container is running in the background."
echo ""
echo "To sync with AnkiWeb:"
echo "  1. Start the backend and frontend"
echo "  2. Open the app at http://localhost:3000"
echo "  3. Go to Settings → AnkiWeb Connection"
echo "  4. Enter your AnkiWeb credentials"
echo ""
echo "Useful commands:"
echo "  docker compose logs -f  # View container logs"
echo "  docker compose down     # Stop container"
echo ""
