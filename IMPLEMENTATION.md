# Claude Usage Tracker - Implementation Documentation

## Overview

This tool tracks Claude Code usage by parsing local JSONL files stored by Claude Code. No web scraping or API calls needed - all data is already on your machine!

## How It Works

### Data Source

Claude Code stores detailed usage logs locally at:
```
~/.claude/projects/<project-name>/<conversation-id>.jsonl
```

Each message contains:
- Token counts (input, output, cache creation, cache reads)
- Model used (Sonnet, Opus, Haiku)
- Timestamp
- Request ID

### Components

1. **`claude_data_parser.py`** - Parses JSONL files
   - Scans all project directories
   - Extracts token usage per message
   - Aggregates by model, date, project
   - Calculates costs using official Anthropic pricing

2. **`usage_limits_parser.py`** - Parses `/usage` output
   - Extracts current session percentage
   - Extracts extra usage spend
   - Gets reset times

3. **`usage_tracker.py`** - Combined tracker
   - Brings everything together
   - Provides summary reports
   - Will be the backend for the TUI

## Usage Data Available

### Detailed Metrics (from JSONL)
- ✅ Token breakdown by type (input, output, cache creation, cache read)
- ✅ Per-model usage (Sonnet 4.5, Opus 4.5, Haiku)
- ✅ Historical data (daily, weekly, monthly aggregations)
- ✅ Cost calculations (actual USD based on token usage)
- ✅ Cache efficiency metrics
- ✅ Per-project tracking

### Overall Limits (from /usage)
- Session usage percentage (5-hour rolling window)
- Extra usage amount ($X / $50.00)
- Reset times

## Current Capabilities

Run the tracker:
```bash
source venv/bin/activate
python3 usage_tracker.py
```

Output includes:
- Total token usage across all projects
- Cost breakdown by model
- Cache efficiency ratio
- Usage by project
- Last 7 days of activity
- Total cost

## Example Output

```
📊 Fetching detailed usage data from local files...
✅ Analyzed 3,015 messages
   From 2026-01-05 to 2026-01-09

📈 Total Token Usage:
   Input:               122,705
   Output:              255,509
   Cache creation:   15,227,764
   Cache reads:     202,905,702
   ────────────────────────────────────────
   Total:           218,511,680

💾 Cache Efficiency:
   Cache hit ratio: 13.3x
   (Reading 13.3 tokens for every 1 token created)

💰 Cost Breakdown by Model:
   claude-sonnet-4-5-20250929               $  119.13 ( 98.6%)
   claude-haiku-4-5-20251001                $    1.02 (  1.4%)
   ────────────────────────────────────────────────────────────
   TOTAL                                    $  120.14

📁 Usage by Project:
   -home-dev-projects-hacktheplanet          199,133,947 ( 91.1%)
   -home-dev-projects-claudeusagetracker      15,189,674 (  7.0%)
   -home-dev                                   4,150,352 (  1.9%)

📅 Last 7 Days:
   2026-01-05:    4,188,059 tokens (~$24.03)
   2026-01-06:   85,077,910 tokens (~$24.03)
   2026-01-07:   24,987,863 tokens (~$24.03)
   2026-01-08:   55,521,507 tokens (~$24.03)
   2026-01-09:   48,736,341 tokens (~$24.03)
```

## Token Pricing

Prices as of January 2026:

**Claude Sonnet 4.5:**
- Input: $3.00 / MTok
- Output: $15.00 / MTok
- Cache write: $3.75 / MTok
- Cache read: $0.30 / MTok

**Claude Opus 4.5:**
- Input: $15.00 / MTok
- Output: $75.00 / MTok
- Cache write: $18.75 / MTok
- Cache read: $1.50 / MTok

**Claude Haiku 3.5:**
- Input: $1.00 / MTok
- Output: $5.00 / MTok
- Cache write: $1.25 / MTok
- Cache read: $0.10 / MTok

## Limitations

### What IS Tracked
- ✅ All Claude Code usage on this WSL instance
- ✅ All projects in ~/.claude/projects/
- ✅ Full token breakdown and costs

### What IS NOT Tracked
- ❌ claude.ai website usage
- ❌ Claude desktop app (Windows)
- ❌ Claude Code on other machines

Note: Overall session limits from `/usage` include ALL platforms, so you can see your total usage across everything.

## Next Steps (Issue #2)

Build the btop-style TUI with:
- Real-time monitoring
- Live graphs
- 7-day scrollable history
- Auto-refresh every few seconds
- Keyboard navigation

## Technical Details

### Performance
- Parses ~3,000 messages in <1 second
- 16MB total data size
- Negligible CPU/memory usage
- No network requests (all local data)

### Data Privacy
- All data stays local on your machine
- No external API calls
- No credentials needed
- Read-only access to JSONL files
