#!/bin/bash
# Claude Usage Tracker - Uninstallation Script
# Version: 1.0.0

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Installation paths
INSTALL_DIR="$HOME/.local/bin"
LIB_DIR="$HOME/.local/lib/claudeusagetracker"
DATA_DIR="$HOME/.claudeusagetracker"
SERVICE_DIR="$HOME/.config/systemd/user"
COMMAND_NAME="claude-usage-tracker"

# Parse arguments
KEEP_DATA=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-data)
            KEEP_DATA=true
            shift
            ;;
        -h|--help)
            echo "Claude Usage Tracker - Uninstall Script"
            echo
            echo "Usage: ./uninstall.sh [OPTIONS]"
            echo
            echo "Options:"
            echo "  --keep-data    Keep historical usage data in ~/.claudeusagetracker/"
            echo "  -h, --help     Show this help message"
            echo
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo
echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}║         Claude Usage Tracker v1.0.0                    ║${NC}"
echo -e "${CYAN}║         Uninstallation                                 ║${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
echo

if [ "$KEEP_DATA" = true ]; then
    echo -e "${BLUE}Mode:${NC} Uninstall (keeping data)"
else
    echo -e "${BLUE}Mode:${NC} Complete uninstall"
fi
echo

# Confirm uninstallation
echo -e "${YELLOW}This will remove:${NC}"
echo "  - Command: $INSTALL_DIR/$COMMAND_NAME"
echo "  - Application: $LIB_DIR/"
echo "  - Systemd service"
if [ "$KEEP_DATA" = false ]; then
    echo -e "  - ${RED}All usage data in $DATA_DIR${NC}"
else
    echo -e "  - ${GREEN}Data will be preserved in $DATA_DIR${NC}"
fi
echo
read -p "Continue with uninstallation? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Uninstallation cancelled"
    exit 0
fi

echo

# ============================================================================
# STEP 1: Stop Daemon
# ============================================================================
echo -e "${BLUE}[1/5]${NC} Stopping daemon..."
echo

if command -v systemctl &> /dev/null; then
    if systemctl --user is-active --quiet claude-usage-daemon.service 2>/dev/null; then
        systemctl --user stop claude-usage-daemon.service
        echo -e "${GREEN}✓${NC} Daemon stopped"
    else
        echo -e "${YELLOW}→${NC} Daemon was not running"
    fi
else
    echo -e "${YELLOW}→${NC} systemd not available, skipping"
fi
echo

# ============================================================================
# STEP 2: Disable and Remove Service
# ============================================================================
echo -e "${BLUE}[2/5]${NC} Removing systemd service..."
echo

if command -v systemctl &> /dev/null; then
    SERVICE_FILE="$SERVICE_DIR/claude-usage-daemon.service"

    if [ -f "$SERVICE_FILE" ]; then
        systemctl --user disable claude-usage-daemon.service 2>/dev/null || true
        rm -f "$SERVICE_FILE"
        systemctl --user daemon-reload
        echo -e "${GREEN}✓${NC} Service removed"
    else
        echo -e "${YELLOW}→${NC} Service file not found"
    fi
else
    echo -e "${YELLOW}→${NC} systemd not available, skipping"
fi
echo

# ============================================================================
# STEP 3: Remove Command
# ============================================================================
echo -e "${BLUE}[3/5]${NC} Removing command..."
echo

COMMAND_PATH="$INSTALL_DIR/$COMMAND_NAME"
if [ -f "$COMMAND_PATH" ]; then
    rm -f "$COMMAND_PATH"
    echo -e "${GREEN}✓${NC} Removed: $COMMAND_PATH"
else
    echo -e "${YELLOW}→${NC} Command not found at $COMMAND_PATH"
fi
echo

# ============================================================================
# STEP 4: Remove Application Directory
# ============================================================================
echo -e "${BLUE}[4/5]${NC} Removing application files..."
echo

if [ -d "$LIB_DIR" ]; then
    rm -rf "$LIB_DIR"
    echo -e "${GREEN}✓${NC} Removed: $LIB_DIR"
else
    echo -e "${YELLOW}→${NC} Application directory not found"
fi
echo

# ============================================================================
# STEP 5: Remove Data Directory (Optional)
# ============================================================================
echo -e "${BLUE}[5/5]${NC} Handling data directory..."
echo

if [ "$KEEP_DATA" = true ]; then
    if [ -d "$DATA_DIR" ]; then
        echo -e "${GREEN}✓${NC} Preserving data: $DATA_DIR"
        echo -e "  ${CYAN}Files preserved:${NC}"
        if [ "$(ls -A $DATA_DIR)" ]; then
            ls -lh "$DATA_DIR" | tail -n +2 | awk '{printf "    %s %s\n", $9, $5}'
        else
            echo -e "    ${YELLOW}(directory is empty)${NC}"
        fi
    else
        echo -e "${YELLOW}→${NC} Data directory does not exist"
    fi
else
    if [ -d "$DATA_DIR" ]; then
        rm -rf "$DATA_DIR"
        echo -e "${GREEN}✓${NC} Removed data directory: $DATA_DIR"
    else
        echo -e "${YELLOW}→${NC} Data directory does not exist"
    fi
fi
echo

# ============================================================================
# UNINSTALLATION COMPLETE
# ============================================================================
echo
echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}║  ${GREEN}✓${CYAN} Uninstallation Complete!                          ║${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
echo

if [ "$KEEP_DATA" = true ]; then
    echo -e "${BLUE}Your usage data has been preserved at:${NC}"
    echo -e "  $DATA_DIR"
    echo
    echo -e "To reinstall and reuse this data:"
    echo -e "  ${CYAN}./install.sh${NC}"
    echo
    echo -e "To completely remove data:"
    echo -e "  ${CYAN}rm -rf $DATA_DIR${NC}"
else
    echo -e "${GREEN}All files and data have been removed.${NC}"
fi

echo
echo -e "To reinstall: ${CYAN}./install.sh${NC}"
echo
