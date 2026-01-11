# Changelog

All notable changes to Claude Usage Tracker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-01-10

### Added
- **btop-style Terminal UI** with real-time usage monitoring
  - Session limits display (5-hour rolling window)
  - Extra usage tracking ($0-$50 monthly limit)
  - Auto-refresh every 15 seconds
  - Keyboard controls for navigation and display modes

- **Interactive Visualization**
  - Dot-matrix chart using Braille characters inspired by btop
  - Dual display modes: toggle between token counts and cost view
  - Dynamic scaling: each dot represents 10K tokens or $0.01
  - Scrollable history through 30 days of data
  - Adjustable view: show 1-5 days at once (default: 2 days)

- **Background Daemon**
  - Runs independently collecting usage data every 30 seconds
  - Polls `/usage` command via pexpect
  - Stores complete usage history in `~/.claudeusagetracker/`
  - Systemd service for auto-start on boot
  - Graceful shutdown handling

- **Data Collection**
  - JSONL parser for local Claude conversation files
  - Token usage breakdown by type (Input, Output, Cache Creation, Cache Reads)
  - Cost calculations based on Sonnet 4.5 pricing
  - Daily aggregation and statistics

- **Installation & Setup**
  - One-command installation: `./install.sh`
  - Installs command to `~/.local/bin/claude-usage-tracker`
  - Automatic systemd service setup
  - Data directory management with reuse on reinstall
  - Uninstall script with `--keep-data` option

- **Documentation**
  - Comprehensive README with quick start guide
  - DESIGN_DECISIONS.md explaining architectural choices
  - SESSION_WINDOW_TEST.md with session window investigation
  - Inline help with `--help` flag
  - Version information with `--version` flag

### Technical Details
- Python 3.8+ required
- Dependencies: textual, rich, pexpect
- Data storage: `~/.claudeusagetracker/`
- Systemd user service for daemon management
- Single-system, single-user tracking

### Investigation
- Confirmed `/usage` command does NOT trigger session windows (Issue #5)
- Session window is a 5-hour rolling window from first request
- `/usage` uses separate OAuth API endpoint for monitoring

### Pricing (Sonnet 4.5)
- Input tokens: $3.00 per 1M tokens
- Output tokens: $15.00 per 1M tokens
- Cache creation: $3.75 per 1M tokens
- Cache reads: $0.30 per 1M tokens

### Known Limitations
- Linux only (tested on WSL2, Ubuntu)
- Requires Claude CLI installation
- Single-user per system
- No multi-account support
- Historical data only available after daemon starts collecting

### Contributors
- Built with [Claude Code](https://claude.com/claude-code)

[1.0.0]: https://github.com/snowmirage/claudeusagetracker/releases/tag/v1.0.0
