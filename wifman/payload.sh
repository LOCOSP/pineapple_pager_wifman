#!/bin/bash
# Title: WiFMan by LAB5
# Description: WiFi Network Manager - Easy switching between saved WiFi profiles
# Author: LOCOSP
# Version: 1.0
# Category: General

PAYLOAD_DIR="/root/payloads/user/general/wifman"

#
# Setup paths for Python and shared library
#
export PATH="/mmc/usr/bin:$PATH"
export PYTHONPATH="$PAYLOAD_DIR/lib:$PAYLOAD_DIR:$PYTHONPATH"
export LD_LIBRARY_PATH="/mmc/usr/lib:$PAYLOAD_DIR/lib:$PAYLOAD_DIR:$LD_LIBRARY_PATH"
export CRYPTOGRAPHY_OPENSSL_NO_LEGACY=1

#
# Check for Python3 + required modules
#
check_python() {
    NEED_PYTHON=false
    NEED_CTYPES=false

    if ! command -v python3 >/dev/null 2>&1; then
        NEED_PYTHON=true
        NEED_CTYPES=true
    elif ! python3 -c "import ctypes" 2>/dev/null; then
        NEED_CTYPES=true
    fi

    if [ "$NEED_PYTHON" = true ] || [ "$NEED_CTYPES" = true ]; then
        LOG ""
        LOG "red" "=== PYTHON3 REQUIRED ==="
        LOG ""
        if [ "$NEED_PYTHON" = true ]; then
            LOG "Python3 is not installed."
        else
            LOG "Python3-ctypes is not installed."
        fi
        LOG ""
        LOG "WiFMan requires Python3 + ctypes for pagerctl."
        LOG ""
        LOG "green" "GREEN = Install Python3 (requires internet)"
        LOG "red" "RED   = Exit"
        LOG ""

        while true; do
            BUTTON=$(WAIT_FOR_INPUT 2>/dev/null)
            case "$BUTTON" in
                "GREEN"|"A")
                    LOG ""
                    LOG "Updating package lists..."
                    opkg update 2>&1 | while IFS= read -r line; do LOG "  $line"; done
                    LOG ""
                    LOG "Installing Python3 + ctypes to MMC..."
                    opkg -d mmc install python3 python3-ctypes 2>&1 | while IFS= read -r line; do LOG "  $line"; done
                    LOG ""
                    if command -v python3 >/dev/null 2>&1 && python3 -c "import ctypes" 2>/dev/null; then
                        LOG "green" "Python3 installed successfully!"
                        sleep 1
                        return 0
                    else
                        LOG "red" "Failed to install Python3"
                        LOG "Check internet connection."
                        sleep 2
                        return 1
                    fi
                    ;;
                "RED"|"B")
                    LOG "Exiting."
                    exit 0
                    ;;
            esac
        done
    fi
    return 0
}

# ============================================================
# CLEANUP
# ============================================================

cleanup() {
    # Restart pager service if not running (background like pagergotchi)
    sleep 0.3
    if ! pgrep -x pineapplepager >/dev/null; then
        /etc/init.d/pineapplepager start 2>/dev/null &
    fi
}

# Ensure pager service restarts on exit
trap cleanup EXIT

# ============================================================
# 
# ============================================================

LOG ""
LOG "cyan" "====[ WiFMan ]================="
LOG "magenta" "by LAB5"
LOG ""
LOG "WiFi Profile Manager"
LOG ""
LOG ""
LOG ""
LOG ""
LOG "green" "GREEN = Run WiFMan"
LOG "red"   "RED   = Exit"
LOG ""


while true; do
    BUTTON=$(WAIT_FOR_INPUT 2>/dev/null)
    case "$BUTTON" in
        "GREEN"|"A") break ;;
        "RED"|"B") exit 0 ;;
    esac
done

# ============================================================
# MAIN
# ============================================================

# Check Python first (required)
check_python || exit 1

# Check if libpagerctl.so exists
if [ ! -f "$PAYLOAD_DIR/lib/libpagerctl.so" ]; then
    LOG ""
    LOG "red" "ERROR: libpagerctl.so not found!"
    LOG ""
    LOG "Please copy libpagerctl.so to $PAYLOAD_DIR/lib/"
    LOG ""
    LOG "Press any button to exit..."
    WAIT_FOR_INPUT >/dev/null 2>&1
    exit 1
fi

# Stop pager service before launching Python app to free framebuffer
# (following pagergotchi pattern for display control)
/etc/init.d/pineapplepager stop 2>/dev/null
sleep 0.5

# Run WiFMan
cd "$PAYLOAD_DIR"
python3 wifman.py

# Small delay to ensure framebuffer is fully released
sleep 0.3

# Restart pager service in background (like pagergotchi)
/etc/init.d/pineapplepager start 2>/dev/null &

exit 0

