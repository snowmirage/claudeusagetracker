# Design Decisions: Claude Usage Tracker

## Problem: Multi-Color Bars for Session vs Extra Usage

### Initial Goal
Display daily usage bars with multiple colors to represent:
- **Cyan**: Tokens used within Pro plan session limits (included/free)
- **Yellow**: Tokens used as "extra usage" (paid, beyond session limits)

### The Challenge: Missing Data

#### What We Have Access To:
1. **From `/usage` command (live):**
   - Current session usage: `X% used` (e.g., 39%)
   - Current session reset time: `Resets 2pm (America/New_York)`
   - Extra usage percentage: `X% used` (e.g., 48%)
   - Extra usage dollars: `$26.86 / $50.00 spent`
   - Extra usage reset date: `Resets Feb 1 (America/New_York)`

   **KEY INSIGHT:** From the reset time, we can calculate when the current session STARTED:
   - Session duration: 5 hours (fixed)
   - Reset time: 2pm (from `/usage`)
   - Current time: 1pm (system clock)
   - Time until reset: 1 hour
   - Time elapsed in session: 5 hours - 1 hour = 4 hours
   - **Session started at: 1pm - 4 hours = 9am**

2. **From local JSONL files (`~/.claude/projects/`):**
   - Each message timestamp
   - Token counts per message (input, output, cache_creation, cache_read)
   - Model used
   - **BUT NOT:** Whether tokens were session vs extra usage

#### What We DON'T Have:
- **Historical session boundaries**: When past sessions started/reset
- **Token classification**: Which historical tokens were "session" vs "extra"
- **Session timing**: Sessions are 5-hour rolling windows that start when you first use Claude (not fixed times)
- **Server-side tracking**: Claude.ai tracks session/extra server-side but doesn't expose it in local logs

### Why Simple Approaches Don't Work

**Approach 1: Parse session reset times**
- ❌ `/usage` only shows CURRENT session reset time
- ❌ Can't determine when yesterday's sessions reset
- ❌ Can't reconstruct historical session boundaries

**Approach 2: Assume 44k tokens/day = session**
- ❌ Inaccurate: You can have multiple sessions per day
- ❌ Session resets aren't at midnight
- ❌ Would show wrong colors for multi-session days

**Approach 3: Calculate from timestamps**
- ❌ Sessions start on first use, not at fixed times
- ❌ Can't determine session start without historical `/usage` data
- ❌ 5-hour rolling window is complex to reconstruct

## Options Considered

### Option A: Track Extra Usage Changes (During TUI Runtime)
**Implementation:**
- Every 15 seconds when TUI refreshes, poll `/usage`
- Compare extra usage $ to previous value
- If changed, log: `{"timestamp": "...", "delta": 1.73, "cumulative": 26.86}`
- Store in `~/.claude_extra_usage_tracker.json`

**Pros:**
- ✅ Accurate for tracked data
- ✅ Uses existing 15s refresh
- ✅ No additional processes

**Cons:**
- ❌ Only works when TUI running
- ❌ Misses extra usage when TUI closed
- ❌ No historical data before tracking started

### Option B: Background Daemon (CHOSEN)
**Implementation:**
- Separate process runs continuously: `claude_usage_daemon.py`
- Polls `/usage` every 30-60 seconds (via pexpect)
- Logs all extra usage changes to persistent storage
- TUI reads from daemon's data store

**Pros:**
- ✅ Catches ALL extra usage (most accurate)
- ✅ Works even when TUI closed
- ✅ Complete historical tracking going forward
- ✅ Separation of concerns: daemon = collect, TUI = display

**Cons:**
- ❌ More complex (daemon lifecycle)
- ❌ Always running (minimal resource usage ~1-2MB)
- ❌ Requires setup (systemd/cron)

### Option C: Simple Threshold (Approximate)
**Implementation:**
- If day total > 44k tokens: color first 44k cyan, rest yellow
- Acknowledge as estimate

**Pros:**
- ✅ Simple
- ✅ Works for all historical data

**Cons:**
- ❌ Very inaccurate
- ❌ Misleading to users
- ❌ Doesn't reflect reality

## Final Decision: Option B (Daemon) with Simplified Tracking

### Architecture

```
┌─────────────────────────────────────┐
│  claude_usage_daemon.py             │
│  (Background Process)               │
│                                     │
│  1. Poll /usage every 30-60s       │
│  2. Track extra usage changes      │
│  3. Store daily aggregates         │
│  4. Write to ~/.claudeusagetracker/   │
└─────────────────────────────────────┘
              │
              │ Writes data
              ▼
┌─────────────────────────────────────┐
│  ~/.claudeusagetracker/                │
│  - daily_breakdown.json             │
│  - extra_usage_log.json             │
└─────────────────────────────────────┘
              │
              │ Reads data
              ▼
┌─────────────────────────────────────┐
│  claude_tui.py                      │
│  (Display Only)                     │
│                                     │
│  1. Read daemon's data store       │
│  2. Refresh display every 15s      │
│  3. Show multi-color bars          │
└─────────────────────────────────────┘
```

### Enhanced Tracking with Session Boundary Detection

**What the Daemon Will Capture (Every 30-60 seconds):**

1. **Session metadata:**
   - Current session % used
   - Session reset time (e.g., "2pm")
   - **Calculated session start time** (reset time - 5 hours)
   - Timezone

2. **Extra usage metadata:**
   - Extra usage $ spent
   - Extra usage % used
   - Extra usage limit ($50.00)
   - Extra usage reset date

3. **Session boundary events:**
   - Detect when session resets (reset time changes)
   - Log session start/end times
   - Track which JSONL messages fall within each session

**Storage format:**
```json
{
  "sessions": [
    {
      "session_id": "2026-01-10-09:00",
      "start_time": "2026-01-10T09:00:00-05:00",
      "reset_time": "2026-01-10T14:00:00-05:00",
      "tokens_used": 44000,
      "is_extra_usage": false
    },
    {
      "session_id": "2026-01-10-14:00",
      "start_time": "2026-01-10T14:00:00-05:00",
      "reset_time": "2026-01-10T19:00:00-05:00",
      "tokens_used": 12000,
      "is_extra_usage": false
    }
  ],
  "daily_summary": {
    "2026-01-10": {
      "session_tokens": 56000,
      "extra_tokens": 29000,
      "total_tokens": 85000,
      "extra_cost": 1.73,
      "sessions_count": 3
    }
  },
  "extra_usage_log": [
    {
      "timestamp": "2026-01-10T12:30:00-05:00",
      "cumulative": 26.86,
      "delta": 1.73
    }
  ]
}
```

**Bar rendering:**
```
┌─────────┐
│  01-10  │
│   ███   │  ← Yellow (extra usage)
│   ███   │  ← Yellow
│   ███   │  ← Cyan (session)
│   ███   │  ← Cyan
│  85K    │
└─────────┘
```

### Why This Approach Works

1. **Accurate going forward**: Daemon catches all extra usage changes
2. **Simple to implement**: Daily totals, not complex intra-day tracking
3. **Clear visualization**: Two-color bars show session vs extra
4. **Separation of concerns**:
   - Daemon = data collection (runs 24/7)
   - TUI = data display (run when needed)

### Limitations Accepted

1. **No historical data**: Days before daemon started won't have session/extra breakdown
   - Solution: Show single color for those dates

2. **Intra-day approximation**: We track daily totals, not exact session boundaries
   - Acceptable: User wants to see "how much extra usage per day", not exact timing

3. **Daemon dependency**: Requires background process
   - Acceptable: Standard for monitoring tools (like `btop`, `htop`)

## Implementation Plan

### Phase 1: Daemon Data Collection (Current Focus)

**Capture ALL `/usage` data every 30-60 seconds:**
1. Session percentage used
2. Session reset time
3. Session reset timezone
4. Extra usage dollars spent
5. Extra usage percentage
6. Extra usage limit
7. Extra usage reset date
8. Timestamp of collection

**Calculate and store:**
- Session start time (derived from reset time)
- Session boundaries (when reset time changes)
- Extra usage deltas (changes since last poll)

**Initial implementation (simple):**
- Use captured data to calculate **daily totals** (session vs extra)
- Store complete raw data for future enhancements

**Future enhancements (data already captured):**
- Session-by-session breakdown
- Intra-day session switching visualization
- More accurate token attribution

### Daemon Implementation Steps:
1. Create `claude_usage_daemon.py`
2. Implement `/usage` polling (via pexpect) - capture ALL fields
3. Parse and store complete `/usage` output
4. Calculate daily session vs extra totals
5. Store in `~/.claudeusagetracker/`
6. Add systemd service file for auto-start

### Phase 2: Data Storage
1. Create `~/.claudeusagetracker/` directory
2. Define JSON schema for daily breakdown
3. Implement append-only logging
4. Add data rotation (keep last 90 days)

### Phase 3: TUI Integration
1. Update `claude_tui.py` to read daemon data
2. Implement multi-color bar rendering
3. Add legend: `[Cyan]=Session | [Yellow]=Extra`
4. Handle missing data gracefully

### Phase 4: Installation & Documentation
1. Create install script
2. Add systemd integration
3. Update README with daemon setup
4. Document data formats

## Future Enhancements

1. **More accurate session tracking**: Parse JSONL timestamps and attempt to reconstruct session boundaries
2. **Cost breakdown**: Show $ cost per day (not just tokens)
3. **Alerts**: Notify when approaching limits
4. **Historical analysis**: Trends, predictions, recommendations

---

**Date**: 2026-01-10
**Status**: Design Approved, Ready for Implementation
