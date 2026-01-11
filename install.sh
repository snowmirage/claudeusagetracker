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

# Script directory (where install.sh lives)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Installation paths
INSTALL_DIR="$HOME/.local/bin"
DATA_DIR="$HOME/.claudeusagetracker"
SERVICE_DIR="$HOME/.config/systemd/user"
VENV_DIR="$SCRIPT_DIR/venv"

echo
echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}║         Claude Usage Tracker v1.0.0                    ║${NC}"
echo -e "${CYAN}║         Installation                                   ║${NC}"
echo -e "${CYAN}║                                                        ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${NC}"
echo

# ============================================================================
# STEP 1: Check Requirements
# ============================================================================
echo -e "${BLUE}[1/8]${NC} Checking requirements..."
echo

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Error: python3 not found${NC}"
    echo "  Please install Python 3.8 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"; then
    echo -e "${RED}✗ Error: Python $PYTHON_VERSION found, but 3.8+ required${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python $PYTHON_VERSION"

# Check Claude CLI
if ! command -v claude &> /dev/null; then
    echo -e "${YELLOW}⚠ Warning: 'claude' command not found${NC}"
    echo "  The tracker requires Claude CLI to collect usage data."
    echo "  Visit: https://github.com/anthropics/claude-code"
    echo
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
else
    echo -e "${GREEN}✓${NC} Claude CLI installed"
fi

# Check systemd
if ! command -v systemctl &> /dev/null; then
    echo -e "${YELLOW}⚠ Warning: systemd not found${NC}"
    echo "  Daemon auto-start will not be configured"
    SYSTEMD_AVAILABLE=false
else
    echo -e "${GREEN}✓${NC} systemd available"
    SYSTEMD_AVAILABLE=true
fi

echo

# ============================================================================
# STEP 2: Create Virtual Environment
# ============================================================================
echo -e "${BLUE}[2/8]${NC} Setting up Python virtual environment..."
echo

if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}→${NC} Virtual environment already exists, reusing"
else
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓${NC} Virtual environment created"
fi

# Upgrade pip and install dependencies
echo -e "${YELLOW}→${NC} Installing dependencies..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
echo -e "${GREEN}✓${NC} Dependencies installed"
echo

# ============================================================================
# STEP 3: Create Data Directory
# ============================================================================
echo -e "${BLUE}[3/8]${NC} Setting up data directory..."
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
# STEP 4: Install Command
# ============================================================================
echo -e "${BLUE}[4/8]${NC} Installing command..."
echo

# Create ~/.local/bin if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Create wrapper script
WRAPPER_SCRIPT="$INSTALL_DIR/claude-usage-tracker"
cat > "$WRAPPER_SCRIPT" << EOF
#!/bin/bash
# Claude Usage Tracker - Command wrapper
exec "$VENV_DIR/bin/python3" "$SCRIPT_DIR/claude_tui.py" "\$@"
EOF

chmod +x "$WRAPPER_SCRIPT"
echo -e "${GREEN}✓${NC} Installed command: $WRAPPER_SCRIPT"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo -e "${YELLOW}⚠ Warning: $INSTALL_DIR is not in your PATH${NC}"
    echo "  Add this line to your ~/.bashrc or ~/.zshrc:"
    echo
    echo -e "  ${CYAN}export PATH=\"\$HOME/.local/bin:\$PATH\"${NC}"
    echo
    echo "  Then run: source ~/.bashrc (or restart your shell)"
    echo
fi
echo

# ============================================================================
# STEP 5: Install Systemd Service
# ============================================================================
echo -e "${BLUE}[5/8]${NC} Installing systemd service..."
echo

if [ "$SYSTEMD_AVAILABLE" = true ]; then
    mkdir -p "$SERVICE_DIR"

    SERVICE_FILE="$SERVICE_DIR/claude-usage-daemon.service"
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Claude Usage Tracker Daemon
After=network.target

[Service]
Type=simple
ExecStart=$VENV_DIR/bin/python3 $SCRIPT_DIR/claude_usage_daemon.py
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
else
    echo -e "${YELLOW}→${NC} Skipped (systemd not available)"
fi
echo

# ============================================================================
# STEP 6: Start Daemon
# ============================================================================
echo -e "${BLUE}[6/8]${NC} Starting daemon..."
echo

if [ "$SYSTEMD_AVAILABLE" = true ]; then
    # Stop if already running
    systemctl --user stop claude-usage-daemon.service 2>/dev/null || true
    sleep 1

    # Start the service
    systemctl --user start claude-usage-daemon.service

    # Check if started successfully
    sleep 2
    if systemctl --user is-active --quiet claude-usage-daemon.service; then
        echo -e "${GREEN}✓${NC} Daemon started successfully"
    else
        echo -e "${RED}✗ Failed to start daemon${NC}"
        echo "  Check logs: journalctl --user -u claude-usage-daemon -n 50"
    fi
else
    echo -e "${YELLOW}→${NC} Manual start required (systemd not available)"
    echo "  Run: $VENV_DIR/bin/python3 $SCRIPT_DIR/claude_usage_daemon.py &"
fi
echo

# ============================================================================
# STEP 7: Set Permissions
# ============================================================================
echo -e "${BLUE}[7/8]${NC} Setting file permissions..."
echo

chmod +x "$SCRIPT_DIR/claude_tui.py"
chmod +x "$SCRIPT_DIR/claude_usage_daemon.py"
chmod +x "$SCRIPT_DIR/session_window_test.py"
echo -e "${GREEN}✓${NC} Permissions set"
echo

# ============================================================================
# STEP 8: Verification
# ============================================================================
echo -e "${BLUE}[8/8]${NC} Verifying installation..."
echo

# Check command exists
if command -v claude-usage-tracker &> /dev/null; then
    echo -e "${GREEN}✓${NC} Command 'claude-usage-tracker' is available"
else
    echo -e "${YELLOW}⚠${NC} Command 'claude-usage-tracker' not in PATH yet"
    echo "  You may need to restart your shell or add ~/.local/bin to PATH"
fi

# Check daemon status
if [ "$SYSTEMD_AVAILABLE" = true ]; then
    if systemctl --user is-active --quiet claude-usage-daemon.service; then
        echo -e "${GREEN}✓${NC} Daemon is running"
    else
        echo -e "${YELLOW}⚠${NC} Daemon is not running"
    fi
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
echo -e "${BLUE}Service Commands:${NC}"
if [ "$SYSTEMD_AVAILABLE" = true ]; then
    echo -e "  Start:   ${CYAN}systemctl --user start claude-usage-daemon${NC}"
    echo -e "  Stop:    ${CYAN}systemctl --user stop claude-usage-daemon${NC}"
    echo -e "  Status:  ${CYAN}systemctl --user status claude-usage-daemon${NC}"
    echo -e "  Logs:    ${CYAN}journalctl --user -u claude-usage-daemon -f${NC}"
else
    echo -e "  ${YELLOW}(systemd not available - manual daemon management required)${NC}"
fi
echo
echo -e "${BLUE}Data Location:${NC}"
echo -e "  $DATA_DIR"
echo
echo -e "${BLUE}Documentation:${NC}"
echo -e "  README.md              - Full user guide"
echo -e "  SESSION_WINDOW_TEST.md - Session window investigation"
echo -e "  DESIGN_DECISIONS.md    - Technical design docs"
echo
echo -e "${BLUE}Uninstall:${NC}"
echo -e "  $SCRIPT_DIR/uninstall.sh"
echo
echo -e "${GREEN}Enjoy monitoring your Claude usage!${NC} 🚀"
echo
