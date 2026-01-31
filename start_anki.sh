#!/bin/bash
# Start Anki for agent integration
# Automatically detects platform and uses appropriate method:
# - Apple Silicon (M1/M2/M3): Opens native macOS Anki app
# - Intel Mac/Linux/Windows: Uses Docker container

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "========================================"
echo "Anki Agent Integration Setup"
echo "========================================"

# Detect platform
ARCH=$(uname -m)
OS=$(uname -s)

echo "Detected: $OS ($ARCH)"

# =============================================================================
# Apple Silicon Mac - Use native Anki app
# =============================================================================
if [[ "$OS" == "Darwin" && "$ARCH" == "arm64" ]]; then
    echo -e "${BLUE}Apple Silicon detected - using native Anki app${NC}"
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
        exit 1
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
        exit 1
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
            exit 1
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
    exit 0
fi

# =============================================================================
# Intel Mac / Linux / Windows - Use Docker container
# =============================================================================
echo -e "${BLUE}Using Docker container for headless Anki${NC}"

# Check Docker is installed
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed.${NC}"
    echo "Please install Docker Desktop from https://www.docker.com/products/docker-desktop/"
    exit 1
fi

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running.${NC}"
    echo "Please start Docker Desktop and try again."
    exit 1
fi

echo -e "${GREEN}✓ Docker is running${NC}"

# Start the Anki container
echo "Starting Anki container..."
docker compose up -d

# Wait for AnkiConnect to be ready (longer timeout for emulation)
echo "Waiting for AnkiConnect API (this may take a minute on first run)..."
MAX_WAIT=120
WAITED=0
until curl -s http://localhost:8765 > /dev/null 2>&1; do
    sleep 2
    WAITED=$((WAITED + 2))
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo -e "${RED}Error: AnkiConnect did not start within ${MAX_WAIT} seconds${NC}"
        echo "Check container logs with: docker logs anki-agent"
        echo ""
        echo "If you're on Apple Silicon, the Docker approach may not work."
        echo "Install the native Anki app instead: https://apps.ankiweb.net/"
        exit 1
    fi
    echo "  Still waiting... (${WAITED}s / ${MAX_WAIT}s)"
done

echo -e "${GREEN}✓ AnkiConnect API is ready at http://localhost:8765${NC}"

# Check if first run (no profile exists)
if [ ! -f "./anki-data/User 1/collection.anki2" ]; then
    echo ""
    echo -e "${YELLOW}========================================"
    echo "FIRST-TIME SETUP REQUIRED"
    echo "========================================${NC}"
    echo ""
    echo "To sync cards to your phone, you need to login to AnkiWeb:"
    echo ""
    echo "1. Opening VNC viewer..."
    
    # Try to open VNC viewer (Mac)
    if [[ "$OS" == "Darwin" ]]; then
        open vnc://localhost:5900 2>/dev/null || echo "   Run: open vnc://localhost:5900"
    else
        echo "   Connect VNC viewer to localhost:5900"
    fi
    
    echo ""
    echo "2. In the Anki window, click 'Sync' button"
    echo "3. Enter your AnkiWeb email and password"
    echo "4. Close the VNC window"
    echo ""
    read -p "Press Enter when done with AnkiWeb login..."
    
    # Verify sync works
    echo "Testing sync..."
    SYNC_RESULT=$(curl -s -X POST http://localhost:8765 -d '{"action":"sync","version":6}' | grep -o '"error":[^,}]*')
    
    if [[ "$SYNC_RESULT" == *"null"* ]]; then
        echo -e "${GREEN}✓ AnkiWeb sync configured successfully!${NC}"
    else
        echo -e "${YELLOW}Warning: Sync may not be configured properly.${NC}"
        echo "You can try logging in again via VNC at localhost:5900"
    fi
else
    echo -e "${GREEN}✓ Anki profile found${NC}"
fi

echo ""
echo "========================================"
echo -e "${GREEN}Anki is ready!${NC}"
echo "========================================"
echo ""
echo "Container is running in the background."
echo "The agent can now create flashcards and read statistics."
echo ""
echo "Useful commands:"
echo "  docker compose logs -f    # View container logs"
echo "  docker compose down       # Stop container"
echo "  open vnc://localhost:5900 # Access Anki GUI (if needed)"
echo ""
