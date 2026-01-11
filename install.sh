#!/bin/bash
# Claude Usage Tracker - Installation Script
# Version: 1.0.0
# Installs like btop: creates command, systemd service, auto-starts daemon

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Script directory (where install.sh lives - the git clone)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Installation paths (standard Linux user install locations)
INSTALL_DIR="$HOME/.local/bin"
LIB_DIR="$HOME/.local/lib/claudeusagetracker"
DATA_DIR="$HOME/.claudeusagetracker"
SERVICE_DIR="$HOME/.config/systemd/user"
VENV_DIR="$LIB_DIR/venv"

echo
echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}║         Claude Usage Tracker v1.0.0                    ║${NC}"
echo -e "${CYAN}║         Installation                                   ║${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
echo

# ============================================================================
# ERROR HANDLER
# ============================================================================
error_exit() {
    echo
    echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  Installation Failed                                   ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
    echo
    echo -e "${YELLOW}To clean up and try again, run:${NC}"
    echo -e "  ${CYAN}./uninstall.sh${NC}"
    echo
    exit 1
}

trap error_exit ERR

# ============================================================================
# STEP 1: Check ALL Requirements (Before Making Changes)
# ============================================================================
echo -e "${BLUE}[1/9]${NC} Checking requirements..."
echo

REQUIREMENTS_MET=true

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Error: python3 not found${NC}"
    echo "  Please install Python 3.8 or higher"
    REQUIREMENTS_MET=false
else
    PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
        echo -e "${RED}✗ Error: Python $PYTHON_VERSION found, but 3.8+ required${NC}"
        REQUIREMENTS_MET=false
    else
        echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"
    fi
fi

# Check Claude CLI
if ! command -v claude &> /dev/null; then
    echo -e "${RED}✗ Error: Claude CLI not found${NC}"
    echo "  The tracker requires Claude CLI to collect usage data."
    echo "  Install from: https://github.com/anthropics/claude-code"
    REQUIREMENTS_MET=false
else
    echo -e "${GREEN}✓${NC} Claude CLI installed"
fi

# Check systemd (required for v1.0.0)
if ! command -v systemctl &> /dev/null; then
    echo -e "${RED}✗ Error: systemd not found${NC}"
    echo "  systemd is required for daemon auto-start"
    echo "  This tool requires systemd for v1.0.0"
    REQUIREMENTS_MET=false
else
    echo -e "${GREEN}✓${NC} systemd available"
fi

# Check if we can create user services
if ! systemctl --user show-environment &> /dev/null; then
    echo -e "${RED}✗ Error: systemd user services not available${NC}"
    echo "  Cannot create user services"
    REQUIREMENTS_MET=false
fi

# Exit if requirements not met
if [ "$REQUIREMENTS_MET" = false ]; then
    echo
    echo -e "${RED}Installation cannot proceed - requirements not met${NC}"
    exit 1
fi

echo

# ============================================================================
# STEP 2: Stop Existing Daemon (If Running)
# ============================================================================
echo -e "${BLUE}[2/9]${NC} Checking for existing installation..."
echo

if systemctl --user is-active --quiet claude-usage-daemon.service 2>/dev/null; then
    echo -e "${YELLOW}→${NC} Stopping existing daemon..."
    systemctl --user stop claude-usage-daemon.service
    echo -e "${GREEN}✓${NC} Existing daemon stopped"
else
    echo -e "${GREEN}✓${NC} No existing daemon running"
fi

echo

# ============================================================================
# STEP 3: Create Installation Directory
# ============================================================================
echo -e "${BLUE}[3/9]${NC} Creating installation directory..."
echo

if [ -d "$LIB_DIR" ]; then
    echo -e "${YELLOW}→${NC} Removing old installation at $LIB_DIR"
    rm -rf "$LIB_DIR"
fi

mkdir -p "$LIB_DIR"
echo -e "${GREEN}✓${NC} Created: $LIB_DIR"
echo

# ============================================================================
# STEP 4: Copy Application Files
# ============================================================================
echo -e "${BLUE}[4/9]${NC} Copying application files..."
echo

# Copy all Python files and requirements
cp "$SCRIPT_DIR/claude_tui.py" "$LIB_DIR/"
cp "$SCRIPT_DIR/claude_usage_daemon.py" "$LIB_DIR/"
cp "$SCRIPT_DIR/session_window_test.py" "$LIB_DIR/"
cp "$SCRIPT_DIR/claude_data_parser.py" "$LIB_DIR/"
cp "$SCRIPT_DIR/usage_limits_parser.py" "$LIB_DIR/"
cp "$SCRIPT_DIR/usage_tracker.py" "$LIB_DIR/"
cp "$SCRIPT_DIR/version.py" "$LIB_DIR/"
cp "$SCRIPT_DIR/requirements.txt" "$LIB_DIR/"

# Set executable permissions
chmod +x "$LIB_DIR/claude_tui.py"
chmod +x "$LIB_DIR/claude_usage_daemon.py"
chmod +x "$LIB_DIR/session_window_test.py"

echo -e "${GREEN}✓${NC} Application files copied"
echo

# ============================================================================
# STEP 5: Create Virtual Environment
# ============================================================================
echo -e "${BLUE}[5/9]${NC} Creating virtual environment..."
echo

python3 -m venv "$VENV_DIR"
echo -e "${GREEN}✓${NC} Virtual environment created"

# Upgrade pip and install dependencies
echo -e "${YELLOW}→${NC} Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$LIB_DIR/requirements.txt" -q
echo -e "${GREEN}✓${NC} Dependencies installed"
echo

# ============================================================================
# STEP 6: Create Data Directory
# ============================================================================
echo -e "${BLUE}[6/9]${NC} Setting up data directory..."
echo

if [ -d "$DATA_DIR" ]; then
    echo -e "${YELLOW}→${NC} Data directory already exists: $DATA_DIR"
    echo -e "${GREEN}✓${NC} Will reuse existing data"
else
    mkdir -p "$DATA_DIR"
    echo -e "${GREEN}✓${NC} Created data directory: $DATA_DIR"
fi
echo

# ============================================================================
# STEP 7: Install Command
# ============================================================================
echo -e "${BLUE}[7/9]${NC} Installing command..."
echo

# Create ~/.local/bin if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Create wrapper script
WRAPPER_SCRIPT="$INSTALL_DIR/claude-usage-tracker"
cat > "$WRAPPER_SCRIPT" << EOF
#!/bin/bash
# Claude Usage Tracker - Command wrapper
exec "$VENV_DIR/bin/python3" "$LIB_DIR/claude_tui.py" "\$@"
EOF

chmod +x "$WRAPPER_SCRIPT"
echo -e "${GREEN}✓${NC} Installed command: $WRAPPER_SCRIPT"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo
    echo -e "${YELLOW}⚠ Warning: $INSTALL_DIR is not in your PATH${NC}"
    echo "  Add this line to your ~/.bashrc or ~/.zshrc:"
    echo
    echo -e "  ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
    echo
    echo "  Then run: source ~/.bashrc (or restart your shell)"
fi
echo

# ============================================================================
# STEP 8: Install Systemd Service
# ============================================================================
echo -e "${BLUE}[8/9]${NC} Installing systemd service..."
echo

mkdir -p "$SERVICE_DIR"

SERVICE_FILE="$SERVICE_DIR/claude-usage-daemon.service"
cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Claude Usage Tracker Daemon
After=network.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/python3 $LIB_DIR/claude_usage_daemon.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=claude-usage-daemon

[Install]
WantedBy=default.target
EOF

# Reload systemd and enable service
systemctl --user daemon-reload
systemctl --user enable claude-usage-daemon.service 2>/dev/null || true
echo -e "${GREEN}✓${NC} Systemd service installed"
echo -e "${GREEN}✓${NC} Service enabled for auto-start on boot"
echo

# ============================================================================
# STEP 9: Start Daemon
# ============================================================================
echo -e "${BLUE}[9/9]${NC} Starting daemon..."
echo

# Start the service
systemctl --user start claude-usage-daemon.service

# Check if started successfully
sleep 2
if systemctl --user is-active --quiet claude-usage-daemon.service; then
    echo -e "${GREEN}✓${NC} Daemon started successfully"
else
    echo -e "${RED}✗ Failed to start daemon${NC}"
    echo "  Check logs: journalctl --user -u claude-usage-daemon -n 50"
    error_exit
fi
echo

# ============================================================================
# INSTALLATION COMPLETE
# ============================================================================
echo
echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}║  ${GREEN}✓${CYAN} Installation Complete!                            ║${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
echo
echo -e "${BLUE}Quick Start:${NC}"
echo
echo -e "  ${GREEN}claude-usage-tracker${NC}"
echo
echo -e "${BLUE}Installed Locations:${NC}"
echo -e "  Command:  $INSTALL_DIR/claude-usage-tracker"
echo -e "  App:      $LIB_DIR/"
echo -e "  Data:     $DATA_DIR/"
echo -e "  Service:  $SERVICE_DIR/claude-usage-daemon.service"
echo
echo -e "${BLUE}Service Commands:${NC}"
echo -e "  Start:   ${CYAN}systemctl --user start claude-usage-daemon${NC}"
echo -e "  Stop:    ${CYAN}systemctl --user stop claude-usage-daemon${NC}"
echo -e "  Status:  ${CYAN}systemctl --user status claude-usage-daemon${NC}"
echo -e "  Logs:    ${CYAN}journalctl --user -u claude-usage-daemon -f${NC}"
echo
echo -e "${BLUE}Documentation:${NC}"
echo -e "  In source directory: $SCRIPT_DIR"
echo -e "  - README.md"
echo -e "  - SESSION_WINDOW_TEST.md"
echo -e "  - DESIGN_DECISIONS.md"
echo
echo -e "${BLUE}Uninstall:${NC}"
echo -e "  ${CYAN}$SCRIPT_DIR/uninstall.sh${NC}"
echo -e "  ${CYAN}$SCRIPT_DIR/uninstall.sh --keep-data${NC}  (preserve usage history)"
echo
echo -e "${GREEN}Enjoy monitoring your Claude usage!${NC} 🚀"
echo
echo -e "${YELLOW}Note:${NC} You can now delete the source directory if desired."
echo -e "      All necessary files are in $LIB_DIR"
echo
