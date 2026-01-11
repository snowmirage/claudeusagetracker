# Claude Usage Tracker

A btop-style terminal UI for monitoring your Claude AI usage in real-time.

![Claude Usage Tracker TUI](https://img.shields.io/badge/platform-Linux-blue)

## Features

### Real-Time Monitoring
- **Session Limits**: Current session percentage and token usage (5-hour rolling window)
- **Extra Usage**: Tracks paid usage beyond Pro plan limits ($0-$50)
- **Auto-Refresh**: Data updates every 15 seconds automatically
- **Background Daemon**: Collects usage data every 30 seconds without manual intervention

### Interactive Visualization
- **Dot-Matrix Chart**: btop-inspired horizontal bar visualization using Braille characters
- **Dual Display Modes**: Toggle between token counts and cost view (press `d`)
- **Dynamic Scaling**: Each dot represents 10K tokens or $0.01
- **Scrollable History**: Navigate through 30 days of historical data
- **Adjustable View**: Show 1-5 days at once (default: 2 days)

### Detailed Metrics
- Token breakdown by type (Input, Output, Cache Creation, Cache Reads)
- Per-day costs and token counts
- Color-coded visualization matching token types
- Properly aligned columns with dynamic width calculation
- Reset time indicators for session and extra usage

## Requirements

Before installation, ensure you have:
- **Linux system** (tested on WSL2, Ubuntu)
- **Python 3.8+**
- **Claude CLI** installed and configured ([Installation Guide](https://github.com/anthropics/claude-code))
- **systemd** (for daemon auto-start)

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/snowmirage/claudeusagetracker.git
cd claudeusagetracker

# 2. Run the installation script
./install.sh
```

That's it! The installer will:
- Create a virtual environment and install dependencies
- Install the `claude-usage-tracker` command to `~/.local/bin/`
- Set up the background daemon as a systemd service
- Configure auto-start on boot
- Start the daemon immediately

### Post-Installation

If `~/.local/bin` is not in your PATH, add this to your `~/.bashrc` or `~/.zshrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Then restart your shell or run: `source ~/.bashrc`

## Quick Start

After installation, simply run:

```bash
claude-usage-tracker
```

## Usage

### Keyboard Controls

| Key | Action |
|-----|--------|
| `q` | Quit the application |
| `d` | Toggle between token and cost display modes |
| `↑` | Scroll to newer dates |
| `↓` | Scroll to older dates |
| `+` / `=` | Increase visible days (max 5) |
| `-` | Decrease visible days (min 1) |

### Display Modes

**Token Mode** (default):
- Each subdot = 10K tokens
- Each full Braille character (⣿) = 80K tokens
- Shows token counts for all usage types

**Cost Mode** (press `d`):
- Each subdot = $0.01
- Each full Braille character (⣿) = $0.08
- Shows dollar amounts for all usage types

## How It Works

### Background Daemon

The tracker uses a background daemon to collect usage data continuously. Here's why:

**Why a daemon?**
- There's **no API** to programmatically access session/extra usage data
- The `/usage` command must be run interactively in Claude CLI
- Historical data is only available while the daemon is running

**What it does:**
- Polls `/usage` command every 30 seconds using pexpect
- Captures session percentage, extra usage dollars, and reset times
- Stores complete data in `~/.claudeusagetracker/`
- Runs as systemd service, auto-starts on boot

**Does `/usage` affect my quota?**
No! Investigation showed that `/usage` uses a separate OAuth monitoring endpoint and does NOT trigger new session windows or consume quota. See [SESSION_WINDOW_TEST.md](SESSION_WINDOW_TEST.md) for details.

### Single-System, Single-User Tracking

**Important:** This tracker only monitors Claude usage on **THIS system**.

- Reads from your local `~/.claude/` directory
- Stores data in your `~/.claudeusagetracker/` directory
- Does **not** track usage from:
  - Other computers or devices
  - claude.ai web interface
  - Mobile apps
  - Other user accounts on the same system

If you use Claude on multiple devices, each would need its own tracker installation.

### Data Storage

- **Location**: `~/.claudeusagetracker/`
- **Files**:
  - `raw_usage_log.jsonl` - Raw data from daemon polls
  - `daily_summary.json` - Aggregated daily statistics
  - `daemon.log` - Daemon activity log

### Components

1. **claude_tui.py** - Main TUI application
   - Interactive terminal UI
   - Real-time usage display
   - Keyboard navigation

2. **claude_usage_daemon.py** - Background collector
   - Systemd service
   - Continuous data collection
   - Auto-start on boot

3. **Data parsers** - Extract and process usage data
   - JSONL file parser (local conversation data)
   - `/usage` command parser (session limits)

## Pricing (Sonnet 4.5)

The tracker uses these rates for cost calculations:
- Input tokens: $3.00 per 1M tokens
- Output tokens: $15.00 per 1M tokens
- Cache creation: $3.75 per 1M tokens
- Cache reads: $0.30 per 1M tokens

## Design Philosophy

This tool is inspired by `btop` and follows these principles:
- **Non-intrusive**: Daemon runs in background without consuming API credits
- **Real-time**: Updates automatically without manual intervention
- **Visual**: Dot-matrix charts provide at-a-glance insights
- **Interactive**: Full keyboard navigation and adjustable views
- **Accurate**: Uses actual Claude data files and `/usage` command output

## Managing the Daemon

The daemon runs as a systemd user service and starts automatically on boot.

### Service Commands

```bash
# Check daemon status
systemctl --user status claude-usage-daemon

# Start daemon
systemctl --user start claude-usage-daemon

# Stop daemon
systemctl --user stop claude-usage-daemon

# Restart daemon
systemctl --user restart claude-usage-daemon

# View daemon logs
journalctl --user -u claude-usage-daemon -f
```

### Daemon Logs

Check logs if you experience issues:

```bash
# Real-time logs
journalctl --user -u claude-usage-daemon -f

# Last 50 lines
journalctl --user -u claude-usage-daemon -n 50

# Or check the log file directly
tail -f ~/.claudeusagetracker/daemon.log
```

## Troubleshooting

**Daemon not running:**
```bash
# Check status
systemctl --user status claude-usage-daemon

# Check logs for errors
journalctl --user -u claude-usage-daemon -n 50

# Restart daemon
systemctl --user restart claude-usage-daemon
```

**No data showing in TUI:**
- Daemon needs to run for at least 30-60 seconds to collect first data point
- Check data directory: `ls -la ~/.claudeusagetracker/`
- Verify Claude CLI is installed: `which claude`

**No historical JSONL data:**
- Verify Claude CLI has been used: `ls -la ~/.claude/projects/`
- Check that conversation files exist with token usage data
- Data only shows for conversations created on this system

**Display issues:**
- Ensure terminal supports Unicode (Braille characters)
- Try resizing terminal window if layout appears broken
- Use a modern terminal emulator (e.g., gnome-terminal, alacritty, kitty)

**Command not found:**
- Ensure `~/.local/bin` is in your PATH
- Add to `~/.bashrc`: `export PATH="$HOME/.local/bin:$PATH"`
- Restart your shell or run: `source ~/.bashrc`

## Uninstalling

To remove the tracker:

```bash
# Uninstall and remove all data
./uninstall.sh

# Uninstall but keep historical data
./uninstall.sh --keep-data
```

The uninstaller removes:
- The `claude-usage-tracker` command
- Systemd service
- Virtual environment

With `--keep-data`, your usage history in `~/.claudeusagetracker/` is preserved for future reinstallation.

## Future Enhancements

- Configurable refresh intervals
- Export usage data to CSV/JSON
- Alert notifications for usage thresholds
- Support for multiple Claude accounts
- Web dashboard for remote monitoring
- Session vs extra usage breakdown in charts

## Contributing

See `DESIGN_DECISIONS.md` and `IMPLEMENTATION.md` for detailed technical documentation.

## License

MIT License - see LICENSE file for details
