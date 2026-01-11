# Session Window Test Documentation

## Purpose

This test script determines whether running the `/usage` command triggers or affects the 5-hour session window.

## Question Being Answered

**If the session window says it resets at 2pm, and we check `/usage` at 3pm, when does the next session window reset?**

Specifically: Does calling `/usage` count as the "first interaction" that starts a new 5-hour rolling window?

## Research Findings (Phase 1)

Before running empirical tests, we researched this question:

### What We Know About Session Windows:
- **5-hour rolling window**: Starts when you send your first request (not at fixed time)
- **Resets every 5 hours**: From the time of that first request
- **Pro Plan limits**: ~45 messages per 5-hour window (~216/day)

### Evidence About `/usage` Command:
- Uses separate OAuth endpoint: `api.anthropic.com/api/oauth/usage`
- Designed as monitoring/metadata query
- No community reports of it consuming session quota
- Would be counterproductive if checking usage consumed resources

### Conclusion from Research:
Strong indirect evidence suggests `/usage` is passive monitoring, but **no explicit official documentation** confirms this.

## Empirical Test (Phase 2)

Since we lack explicit confirmation, this script will test empirically by:

1. **Running overnight** (8-12 hours recommended)
2. **Polling `/usage`** at regular intervals (default: every 5 minutes)
3. **Recording all data**: timestamps, reset times, session percentages
4. **Detecting changes**: When does the reset time advance?

### Test Scenarios

#### Scenario 1: Baseline (Recommended First Test)
```bash
# Run for 12 hours, polling every 5 minutes
# DO NOT interact with Claude during this test
./venv/bin/python3 session_window_test.py --duration 12 --interval 5
```

**Expected Results if /usage is passive:**
- Reset time stays constant (e.g., always shows "2pm")
- Session percentage stays at 0% or doesn't increase
- No new 5-hour window triggered by `/usage` calls

**Expected Results if /usage triggers sessions:**
- Reset time advances by 5 hours after first `/usage` call
- May see session percentage increase
- Pattern of reset time changes correlating with `/usage` polls

#### Scenario 2: With Interaction
```bash
# Run for 6 hours
# After 2 hours, send one Claude message
# Continue monitoring
./venv/bin/python3 session_window_test.py --duration 6 --interval 5
```

This tests: Does an actual interaction trigger reset time change while `/usage` doesn't?

#### Scenario 3: Idle Test
```bash
# Run for 12 hours with longer interval
# Less frequent polling to minimize any potential impact
./venv/bin/python3 session_window_test.py --duration 12 --interval 30
```

## Usage

### Basic Usage

```bash
# Default: 12 hours, polling every 5 minutes
./venv/bin/python3 session_window_test.py
```

### Custom Duration and Interval

```bash
# Run for 8 hours, poll every 10 minutes
./venv/bin/python3 session_window_test.py --duration 8 --interval 10
```

### Arguments

- `--duration`: Hours to run the test (default: 12, range: 1-72)
- `--interval`: Minutes between polls (default: 5, range: 1-60)

### Example Output During Test

```
======================================================================
Poll 12/144 - 2026-01-10 15:30:00
======================================================================
Session: 0% used
  Reset time: 7pm (America/New_York)
Extra usage: 48% used
  Amount: $24.08 / $50.00
  Reset date: Feb 1 (America/New_York)

⏰ Next poll at: 15:35:00
Sleeping for 1 minute... sleeping 4.0 more minutes...
```

## Output Files

### Log File: `~/.claudeusagetracker/session_window_test.jsonl`
- Append-only JSONL format
- One line per poll
- Contains full data for each poll

Example entry:
```json
{
  "poll_timestamp": "2026-01-10T15:30:00-05:00",
  "poll_timestamp_human": "2026-01-10 15:30:00",
  "session": {
    "percent_used": 0,
    "reset_time": "7pm",
    "reset_timezone": "America/New_York"
  },
  "extra": {
    "percent_used": 48,
    "amount_spent": 24.08,
    "amount_limit": 50.0,
    "reset_date": "Feb 1",
    "reset_timezone": "America/New_York"
  }
}
```

### Summary File: `~/.claudeusagetracker/session_window_test_summary.json`
- Analysis of all collected data
- Reset time change detection
- Automatic conclusion

Example summary:
```json
{
  "test_duration_hours": 12,
  "configured_interval_minutes": 5,
  "actual_avg_interval_minutes": 5.02,
  "total_polls": 144,
  "polls_with_session_data": 144,
  "reset_time_changes_detected": 0,
  "reset_changes": [],
  "start_time": "2026-01-10T15:00:00-05:00",
  "end_time": "2026-01-11T03:00:00-05:00",
  "conclusion": "No reset time changes detected. If test ran for 5+ hours with only /usage calls and no other Claude interactions, this suggests /usage does NOT trigger the 5-hour session window."
}
```

## Interpreting Results

### If NO reset time changes detected:
✅ **Conclusion**: `/usage` command is passive monitoring and does NOT trigger session windows

This would confirm our research findings.

### If reset time changes detected:
⚠️ **Further Analysis Needed**:
1. Check timestamps of changes
2. Correlate with any Claude interactions (did you accidentally use Claude during test?)
3. Check if changes happen every ~5 hours regardless of `/usage` calls
4. May indicate `/usage` does trigger sessions (unexpected!)

### If test shows constant reset time for 5+ hours:
✅ **Strong Evidence**: `/usage` doesn't trigger sessions

Even stronger if session percentage stays at 0%.

## Running Test Overnight

### Recommended Approach

1. **Start test before bed:**
   ```bash
   # Run in background with output to file
   nohup ./venv/bin/python3 session_window_test.py --duration 12 --interval 5 > test_output.log 2>&1 &

   # Save the process ID
   echo $! > test_pid.txt
   ```

2. **Check progress:**
   ```bash
   # View last 20 lines of output
   tail -20 test_output.log

   # Check if still running
   ps aux | grep session_window_test
   ```

3. **Stop early if needed:**
   ```bash
   # Read PID and kill process
   kill $(cat test_pid.txt)
   ```

4. **Check results in morning:**
   ```bash
   # View summary
   cat ~/.claudeusagetracker/session_window_test_summary.json | python3 -m json.tool

   # View full log
   less ~/.claudeusagetracker/session_window_test.jsonl
   ```

### Important Notes

⚠️ **DO NOT interact with Claude during the test!**
- Don't use `claude` command
- Don't use Claude Code
- Don't use claude.ai website
- This ensures `/usage` is the ONLY interaction

⏱️ **Minimum test duration**: 5+ hours
- Need to exceed one full session window
- 12 hours recommended for robust results

📊 **Poll interval recommendations**:
- **Every 5 minutes**: High resolution, good for detecting exact timing
- **Every 10 minutes**: Good balance
- **Every 30 minutes**: Minimal impact if concerned about overhead

## Next Steps After Test

1. **Review summary file** for automatic conclusion
2. **Check reset_changes array** for any detected changes
3. **Correlate findings** with research phase evidence
4. **Document conclusion** in issue #5
5. **Update daemon strategy** if needed based on findings

---

**Related Files:**
- `session_window_test.py` - Test script
- `usage_limits_parser.py` - Used for parsing `/usage` output
- Issue #5 - Tracks this investigation
