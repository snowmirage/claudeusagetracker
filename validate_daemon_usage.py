#!/usr/bin/env python3
"""
Daemon Usage Validator

Analyzes daemon logs to detect if the daemon is accidentally consuming Claude usage.
Users specify a time window when they KNOW they were not using Claude, and this script
reports any session or extra usage changes during that period.

This tool helps validate that the daemon is truly passive and not consuming usage.
"""

import sys
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple


class LogEntry:
    """Represents a single daemon poll with session and extra usage data."""

    def __init__(self, timestamp: datetime, poll_num: int):
        self.timestamp = timestamp
        self.poll_num = poll_num
        self.session_percent: Optional[float] = None
        self.session_reset_time: Optional[str] = None
        self.extra_spent: Optional[float] = None
        self.extra_limit: Optional[float] = None

    def has_session_data(self) -> bool:
        return self.session_percent is not None

    def has_extra_data(self) -> bool:
        return self.extra_spent is not None


def parse_daemon_log(log_file: Path, start_time: datetime, end_time: datetime) -> List[LogEntry]:
    """Parse daemon log and extract entries within the time window."""

    entries = []
    current_entry = None

    with open(log_file, 'r') as f:
        for line in f:
            # Parse timestamp
            timestamp_match = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if not timestamp_match:
                continue

            timestamp_str = timestamp_match.group(1)
            try:
                timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue

            # Skip if outside time window
            if timestamp < start_time or timestamp > end_time:
                continue

            # Poll number
            poll_match = re.search(r'Poll #(\d+)', line)
            if poll_match:
                if current_entry:
                    entries.append(current_entry)
                current_entry = LogEntry(timestamp, int(poll_match.group(1)))
                continue

            if not current_entry:
                continue

            # Session data
            session_match = re.search(r'Session: ([\d.]+)% used, resets (\S+)', line)
            if session_match:
                current_entry.session_percent = float(session_match.group(1))
                current_entry.session_reset_time = session_match.group(2)
                continue

            # Extra usage data
            extra_match = re.search(r'Extra: \$([\d.]+) / \$([\d.]+)', line)
            if extra_match:
                current_entry.extra_spent = float(extra_match.group(1))
                current_entry.extra_limit = float(extra_match.group(2))
                continue

    # Add last entry
    if current_entry:
        entries.append(current_entry)

    return entries


def detect_session_resets(entries: List[LogEntry]) -> List[int]:
    """Detect indices where session resets occurred."""
    reset_indices = []

    for i in range(1, len(entries)):
        prev = entries[i-1]
        curr = entries[i]

        # Session reset detected if reset time changed or percent dropped significantly
        if prev.has_session_data() and curr.has_session_data():
            if prev.session_reset_time != curr.session_reset_time:
                reset_indices.append(i)
            elif prev.session_percent > curr.session_percent + 50:  # Significant drop
                reset_indices.append(i)

    return reset_indices


def format_timestamp(dt: datetime) -> str:
    """Format datetime for display."""
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def analyze_segment(entries: List[LogEntry], start_idx: int, end_idx: int, segment_name: str):
    """Analyze a segment of log entries (between resets or window boundaries)."""

    if start_idx >= len(entries) or end_idx > len(entries) or start_idx >= end_idx:
        return

    first = entries[start_idx]
    last = entries[end_idx - 1]

    print(f"\n{'='*80}")
    print(f"{segment_name}")
    print(f"{'='*80}")
    print(f"Start: {format_timestamp(first.timestamp)}")
    print(f"End:   {format_timestamp(last.timestamp)}")
    print(f"Polls: {end_idx - start_idx}")

    # Session analysis
    if first.has_session_data() and last.has_session_data():
        session_change = last.session_percent - first.session_percent
        print(f"\nSession Usage:")
        print(f"  Start: {first.session_percent}% (resets {first.session_reset_time})")
        print(f"  End:   {last.session_percent}% (resets {last.session_reset_time})")
        print(f"  Change: {session_change:+.1f}%")

        if session_change > 0:
            print(f"  ⚠️  SESSION USAGE INCREASED!")
    else:
        print(f"\nSession Usage: No data available")

    # Extra usage analysis
    if first.has_extra_data() and last.has_extra_data():
        extra_change = last.extra_spent - first.extra_spent
        print(f"\nExtra Usage:")
        print(f"  Start: ${first.extra_spent:.2f} / ${first.extra_limit:.2f}")
        print(f"  End:   ${last.extra_spent:.2f} / ${last.extra_limit:.2f}")
        print(f"  Change: ${extra_change:+.2f}")

        if extra_change > 0:
            print(f"  ⚠️  EXTRA USAGE INCREASED!")
    else:
        print(f"\nExtra Usage: No data available")

    # Detailed poll list
    print(f"\nDetailed Poll Data:")
    print(f"{'Poll #':<8} {'Timestamp':<20} {'Session':<15} {'Extra':<15}")
    print(f"{'-'*80}")

    for entry in entries[start_idx:end_idx]:
        session_str = f"{entry.session_percent:.0f}%" if entry.has_session_data() else "N/A"
        extra_str = f"${entry.extra_spent:.2f}" if entry.has_extra_data() else "N/A"
        print(f"{entry.poll_num:<8} {format_timestamp(entry.timestamp):<20} {session_str:<15} {extra_str:<15}")


def main():
    """Main entry point."""

    print("="*80)
    print("Claude Usage Daemon - Usage Validation Tool")
    print("="*80)
    print()
    print("This tool analyzes daemon logs to verify the daemon is not consuming")
    print("Claude usage. You'll specify a time window when you KNOW you were not")
    print("actively using Claude, and we'll report any session or extra usage")
    print("changes during that period.")
    print()
    print("The larger the window, the better - but at least 1 hour is recommended.")
    print()

    # Get time window from user
    print("="*80)
    print("Time Window Selection")
    print("="*80)
    print()
    print("Please provide timestamps in this EXACT format: YYYY-MM-DD HH:MM:SS")
    print("Example: 2026-01-11 00:00:00")
    print()

    while True:
        start_str = input("Start of no-work window: ").strip()
        try:
            start_time = datetime.strptime(start_str, '%Y-%m-%d %H:%M:%S')
            break
        except ValueError:
            print("❌ Invalid format. Please use: YYYY-MM-DD HH:MM:SS")

    while True:
        end_str = input("End of no-work window:   ").strip()
        try:
            end_time = datetime.strptime(end_str, '%Y-%m-%d %H:%M:%S')
            break
        except ValueError:
            print("❌ Invalid format. Please use: YYYY-MM-DD HH:MM:SS")

    if end_time <= start_time:
        print("❌ Error: End time must be after start time")
        sys.exit(1)

    duration = (end_time - start_time).total_seconds() / 3600
    print(f"\n✓ Time window: {duration:.1f} hours")

    # Find daemon log
    log_file = Path.home() / ".claudeusagetracker" / "daemon.log"
    if not log_file.exists():
        print(f"\n❌ Error: Daemon log not found at {log_file}")
        print("   Make sure the daemon has been running and logging data.")
        sys.exit(1)

    print(f"✓ Found daemon log: {log_file}")

    # Parse log
    print("\nAnalyzing daemon logs...")
    entries = parse_daemon_log(log_file, start_time, end_time)

    if not entries:
        print("\n❌ No log entries found in the specified time window.")
        print("   Either the daemon wasn't running, or the time window is incorrect.")
        sys.exit(1)

    print(f"✓ Found {len(entries)} daemon polls in the time window")

    # Detect session resets
    reset_indices = detect_session_resets(entries)

    if reset_indices:
        print(f"✓ Detected {len(reset_indices)} session reset(s) during the window")

    # Analyze segments
    print("\n")
    print("="*80)
    print("ANALYSIS RESULTS")
    print("="*80)

    segments = []
    prev_idx = 0

    for i, reset_idx in enumerate(reset_indices):
        segments.append((prev_idx, reset_idx, f"Segment {i+1} (Before Reset)"))
        segments.append((reset_idx, reset_idx + 1, f"Session Reset at Poll #{entries[reset_idx].poll_num}"))
        prev_idx = reset_idx + 1

    # Final segment
    segments.append((prev_idx, len(entries), f"Segment {len(segments)//2 + 1}" if reset_indices else "Full Window Analysis"))

    # Analyze each segment
    for start_idx, end_idx, name in segments:
        if "Session Reset" in name:
            # Just show the reset point
            entry = entries[start_idx]
            print(f"\n{'='*80}")
            print(f"⚠️  {name}")
            print(f"{'='*80}")
            print(f"Timestamp: {format_timestamp(entry.timestamp)}")
            if entry.has_session_data():
                print(f"New session: {entry.session_percent}% used, resets {entry.session_reset_time}")
        else:
            analyze_segment(entries, start_idx, end_idx, name)

    # Overall summary
    print("\n")
    print("="*80)
    print("SUMMARY")
    print("="*80)

    first_entry = entries[0]
    last_entry = entries[-1]

    # Overall session change
    if first_entry.has_session_data() and last_entry.has_session_data():
        # Can't directly compare if there were resets
        if reset_indices:
            print(f"\n⚠️  Session reset {len(reset_indices)} time(s) during the window.")
            print(f"   See segment analysis above for detailed changes.")
        else:
            session_change = last_entry.session_percent - first_entry.session_percent
            print(f"\nSession Usage Change: {session_change:+.1f}%")
            if session_change > 5:
                print(f"⚠️  WARNING: Significant session usage increase detected!")
                print(f"   The daemon may be consuming Claude usage.")
            elif session_change > 0:
                print(f"⚠️  Minor session usage increase detected.")
                print(f"   This could be normal variance or a problem.")
            else:
                print(f"✓ No session usage increase (daemon appears safe)")

    # Overall extra usage change
    if first_entry.has_extra_data() and last_entry.has_extra_data():
        extra_change = last_entry.extra_spent - first_entry.extra_spent
        print(f"\nExtra Usage Change: ${extra_change:+.2f}")
        if extra_change > 0.10:
            print(f"⚠️  WARNING: Extra usage increased!")
            print(f"   The daemon may be consuming Claude usage.")
        elif extra_change > 0:
            print(f"⚠️  Minor extra usage increase detected.")
        else:
            print(f"✓ No extra usage increase (daemon appears safe)")

    print(f"\nTotal Polls Analyzed: {len(entries)}")
    print(f"Time Window: {duration:.1f} hours")
    print(f"Poll Frequency: {len(entries) / duration:.1f} polls/hour")

    print("\n" + "="*80)
    print("Analysis Complete")
    print("="*80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
