#!/bin/bash
# Custom startup script that properly handles shutdown signals
# so Anki can save its preferences before exiting

# Start virtual X server
Xvfb :99 -screen 0 1920x1080x24 &
XVFB_PID=$!
sleep 1

# Start window manager
openbox &
sleep 1

# Start VNC server
x11vnc -display :99 -forever -nopw -rfbport 5900 &
sleep 1

# Track Anki PID
ANKI_PID=""

# Signal handler - forward signals to Anki for graceful shutdown
cleanup() {
    echo "Received shutdown signal, stopping Anki gracefully..."
    if [ -n "$ANKI_PID" ] && kill -0 $ANKI_PID 2>/dev/null; then
        # Send SIGTERM to Anki and wait for it to save
        kill -TERM $ANKI_PID
        # Wait up to 25 seconds for Anki to exit
        for i in $(seq 1 25); do
            if ! kill -0 $ANKI_PID 2>/dev/null; then
                echo "Anki exited cleanly after ${i}s"
                break
            fi
            sleep 1
        done
        # Force kill if still running
        if kill -0 $ANKI_PID 2>/dev/null; then
            echo "Force killing Anki..."
            kill -9 $ANKI_PID
        fi
    fi
    exit 0
}

# Trap SIGTERM and SIGINT
trap cleanup SIGTERM SIGINT

# Start Anki and track its PID
echo "Starting Anki..."
anki -b /data &
ANKI_PID=$!

# Wait for Anki - if it exits, restart it (unless we're shutting down)
while true; do
    wait $ANKI_PID
    EXIT_CODE=$?
    
    # Check if we're shutting down (trap was triggered)
    if [ ! -d /proc/$$ ]; then
        break
    fi
    
    echo "Anki exited with code $EXIT_CODE, restarting in 2s..."
    sleep 2
    
    anki -b /data &
    ANKI_PID=$!
done
