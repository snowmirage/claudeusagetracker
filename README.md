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

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd claudeusagetracker
   ```

2. **Create virtual environment and install dependencies:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Start the background daemon** (collects usage data):
   ```bash
   ./venv/bin/python3 claude_usage_daemon.py &
   ```

4. **Run the TUI:**
   ```bash
   ./venv/bin/python3 claude_tui.py
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

## Architecture

### Components

1. **claude_tui.py** - Main TUI application
   - Built with Textual framework
   - Three panels: Session Limits, Token Breakdown, Daily Usage Chart
   - Interactive controls for navigation and display modes

2. **claude_usage_daemon.py** - Background data collector
   - Runs independently, polling every 30 seconds
   - Collects data from `/usage` command via pexpect
   - Stores data in `~/.claude_usage_db/`

3. **claude_data_parser.py** - JSONL data parser
   - Reads local Claude conversation files from `~/.claude/projects/`
   - Extracts token usage by type and date
   - Calculates costs based on API pricing

4. **usage_limits_parser.py** - Session limits parser
   - Parses `/usage` command output
   - Extracts session percentage and extra usage spending

5. **usage_tracker.py** - Unified tracker
   - Combines JSONL data with session limits
   - Provides consolidated usage statistics

### Data Storage

- **Location**: `~/.claude_usage_db/`
- **Files**:
  - `usage_raw.jsonl` - Raw data from daemon polls
  - `daily_summary.json` - Aggregated daily statistics

## Requirements

- Python 3.8+
- Linux (tested on WSL2)
- Claude CLI installed and configured
- Dependencies listed in `requirements.txt`:
  - textual>=0.47.0
  - rich>=13.7.0
  - pexpect>=4.9.0

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

## Troubleshooting

**No daemon data available:**
- Ensure the daemon is running: `ps aux | grep claude_usage_daemon`
- Check daemon data directory exists: `ls -la ~/.claude_usage_db/`
- Start the daemon: `./venv/bin/python3 claude_usage_daemon.py &`

**No JSONL data:**
- Verify Claude CLI has been used: `ls -la ~/.claude/projects/`
- Check that conversation files exist with token usage data

**Display issues:**
- Ensure terminal supports Unicode (Braille characters)
- Try resizing terminal window if layout appears broken

## Future Enhancements

- Installation script for system-wide availability
- Configurable refresh intervals
- Export usage data to CSV/JSON
- Alert notifications for usage thresholds
- Support for multiple Claude accounts

## Contributing

See `DESIGN_DECISIONS.md` and `IMPLEMENTATION.md` for detailed technical documentation.

## License

MIT License - see LICENSE file for details
