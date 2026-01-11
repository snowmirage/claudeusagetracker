#!/usr/bin/env python3
"""
Session Window Test Script

Monitors /usage command output over extended period to determine:
1. Does running /usage trigger the 5-hour session window?
2. How does the reset time change over time?

Usage:
    python3 session_window_test.py --duration 12 --interval 5

Arguments:
    --duration: Hours to run the test (default: 12)
    --interval: Minutes between polls (default: 5)
"""

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List
import sys

# Import our existing parser
from usage_limits_parser import UsageLimitsParser


class SessionWindowTest:
    """Test script to monitor session window behavior."""

    def __init__(self, duration_hours: int = 12, poll_interval_minutes: int = 5):
        self.duration_hours = duration_hours
        self.poll_interval_minutes = poll_interval_minutes
        self.parser = UsageLimitsParser()
        self.test_data: List[Dict[str, Any]] = []
        self.log_file = Path.home() / ".claude_usage_db" / "session_window_test.jsonl"
        self.summary_file = Path.home() / ".claude_usage_db" / "session_window_test_summary.json"

        # Ensure directory exists
        self.log_file.parent.mkdir(exist_ok=True)

    def poll_usage(self) -> Dict[str, Any]:
        """Poll /usage and capture all data.

        Returns:
            Dictionary with timestamp and usage data
        """
        try:
            limits = self.parser.get_current_limits()

            poll_time = datetime.now()

            data = {
                "poll_timestamp": poll_time.isoformat(),
                "poll_timestamp_human": poll_time.strftime("%Y-%m-%d %H:%M:%S"),
                "session": None,
                "extra": None
            }

            if limits.session:
                data["session"] = {
                    "percent_used": limits.session.percent_used,
                    "reset_time": limits.session.reset_time,
                    "reset_timezone": limits.session.reset_timezone
                }

            if limits.extra:
                data["extra"] = {
                    "percent_used": limits.extra.percent_used,
                    "amount_spent": limits.extra.amount_spent,
                    "amount_limit": limits.extra.amount_limit,
                    "reset_date": limits.extra.reset_date,
                    "reset_timezone": limits.extra.reset_timezone
                }

            return data

        except Exception as e:
            return {
                "poll_timestamp": datetime.now().isoformat(),
                "error": str(e)
            }

    def calculate_next_reset(self, reset_time_str: str, current_time: datetime) -> datetime:
        """Calculate when the next reset will occur based on reset time string.

        Args:
            reset_time_str: e.g., "2pm" or "7pm"
            current_time: Current datetime

        Returns:
            Datetime of next reset
        """
        # Parse reset hour
        reset_time_lower = reset_time_str.lower().strip()
        hour = int(''.join(filter(str.isdigit, reset_time_lower)))

        if 'pm' in reset_time_lower and hour != 12:
            hour += 12
        elif 'am' in reset_time_lower and hour == 12:
            hour = 0

        # Calculate next reset
        reset_today = current_time.replace(hour=hour, minute=0, second=0, microsecond=0)

        if current_time < reset_today:
            return reset_today
        else:
            return reset_today + timedelta(days=1)

    def analyze_reset_changes(self) -> Dict[str, Any]:
        """Analyze the test data for reset time changes.

        Returns:
            Analysis summary
        """
        if not self.test_data:
            return {"error": "No test data collected"}

        reset_times = []
        for entry in self.test_data:
            if entry.get("session") and entry["session"].get("reset_time"):
                reset_times.append({
                    "timestamp": entry["poll_timestamp"],
                    "reset_time": entry["session"]["reset_time"]
                })

        # Detect changes in reset time
        changes = []
        prev_reset = None

        for i, rt in enumerate(reset_times):
            if prev_reset and rt["reset_time"] != prev_reset:
                changes.append({
                    "index": i,
                    "timestamp": rt["timestamp"],
                    "from": prev_reset,
                    "to": rt["reset_time"]
                })
            prev_reset = rt["reset_time"]

        # Calculate time between polls
        poll_intervals = []
        for i in range(1, len(self.test_data)):
            t1 = datetime.fromisoformat(self.test_data[i-1]["poll_timestamp"])
            t2 = datetime.fromisoformat(self.test_data[i]["poll_timestamp"])
            interval_minutes = (t2 - t1).total_seconds() / 60
            poll_intervals.append(interval_minutes)

        avg_interval = sum(poll_intervals) / len(poll_intervals) if poll_intervals else 0

        return {
            "test_duration_hours": self.duration_hours,
            "configured_interval_minutes": self.poll_interval_minutes,
            "actual_avg_interval_minutes": round(avg_interval, 2),
            "total_polls": len(self.test_data),
            "polls_with_session_data": len(reset_times),
            "reset_time_changes_detected": len(changes),
            "reset_changes": changes,
            "start_time": self.test_data[0]["poll_timestamp"] if self.test_data else None,
            "end_time": self.test_data[-1]["poll_timestamp"] if self.test_data else None,
            "conclusion": self._generate_conclusion(changes, len(reset_times))
        }

    def _generate_conclusion(self, changes: List[Dict], total_polls: int) -> str:
        """Generate conclusion based on observed data.

        Args:
            changes: List of detected reset time changes
            total_polls: Total number of successful polls

        Returns:
            Conclusion string
        """
        if not total_polls:
            return "No data collected - test failed"

        if not changes:
            return (
                "No reset time changes detected. If test ran for 5+ hours with only "
                "/usage calls and no other Claude interactions, this suggests /usage "
                "does NOT trigger the 5-hour session window."
            )

        # Calculate time between changes
        if len(changes) > 0:
            first_change = datetime.fromisoformat(changes[0]["timestamp"])
            last_change = datetime.fromisoformat(changes[-1]["timestamp"]) if len(changes) > 1 else first_change
            time_span = (last_change - first_change).total_seconds() / 3600  # hours

            return (
                f"Detected {len(changes)} reset time change(s) over {time_span:.1f} hours. "
                "This requires further analysis to determine if changes correlate with "
                "/usage polling or other Claude interactions. Check the detailed logs."
            )

        return "Inconclusive - manual analysis of logs required"

    def print_status(self, poll_num: int, total_polls: int, data: Dict[str, Any]):
        """Print current test status."""
        print(f"\n{'='*70}")
        print(f"Poll {poll_num}/{total_polls} - {data.get('poll_timestamp_human', 'N/A')}")
        print(f"{'='*70}")

        if data.get("error"):
            print(f"❌ Error: {data['error']}")
            return

        if data.get("session"):
            session = data["session"]
            print(f"Session: {session['percent_used']}% used")
            print(f"  Reset time: {session['reset_time']} ({session['reset_timezone']})")

        if data.get("extra"):
            extra = data["extra"]
            print(f"Extra usage: {extra['percent_used']}% used")
            print(f"  Amount: ${extra['amount_spent']:.2f} / ${extra['amount_limit']:.2f}")
            print(f"  Reset date: {extra['reset_date']} ({extra['reset_timezone']})")

    def run(self):
        """Run the test for specified duration."""
        print(f"\n{'='*70}")
        print(f"SESSION WINDOW TEST - STARTING")
        print(f"{'='*70}")
        print(f"Duration: {self.duration_hours} hours")
        print(f"Poll interval: {self.poll_interval_minutes} minutes")
        print(f"Log file: {self.log_file}")
        print(f"Summary file: {self.summary_file}")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

        # Calculate end time and total polls
        end_time = datetime.now() + timedelta(hours=self.duration_hours)
        total_polls = int((self.duration_hours * 60) / self.poll_interval_minutes)

        print(f"Will run until: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Expected polls: ~{total_polls}")
        print(f"\n⚠️  DO NOT interact with Claude during this test (except for Ctrl+C to stop)")
        print(f"\nTest starting in 5 seconds...\n")
        time.sleep(5)

        poll_count = 0

        try:
            while datetime.now() < end_time:
                poll_count += 1

                # Poll /usage
                data = self.poll_usage()
                self.test_data.append(data)

                # Log to file (append-only JSONL)
                with open(self.log_file, 'a') as f:
                    f.write(json.dumps(data) + '\n')

                # Print status
                self.print_status(poll_count, total_polls, data)

                # Calculate time to next poll
                next_poll = datetime.now() + timedelta(minutes=self.poll_interval_minutes)
                print(f"\n⏰ Next poll at: {next_poll.strftime('%H:%M:%S')}")

                # Sleep until next poll
                if datetime.now() < end_time:
                    sleep_seconds = self.poll_interval_minutes * 60

                    # Show countdown for first minute, then sleep silently
                    if sleep_seconds >= 60:
                        print("Sleeping for 1 minute...", end='', flush=True)
                        time.sleep(60)
                        remaining = sleep_seconds - 60
                        if remaining > 0:
                            print(f" sleeping {remaining/60:.1f} more minutes...")
                            time.sleep(remaining)
                    else:
                        time.sleep(sleep_seconds)

        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")

        # Generate and save summary
        print(f"\n{'='*70}")
        print("TEST COMPLETE - ANALYZING RESULTS")
        print(f"{'='*70}\n")

        analysis = self.analyze_reset_changes()

        # Save summary
        with open(self.summary_file, 'w') as f:
            json.dump(analysis, f, indent=2)

        # Print summary
        print(json.dumps(analysis, indent=2))

        print(f"\n{'='*70}")
        print(f"Summary saved to: {self.summary_file}")
        print(f"Full logs saved to: {self.log_file}")
        print(f"{'='*70}\n")


def main():
    """Entry point for test script."""
    parser = argparse.ArgumentParser(
        description="Monitor /usage command to test session window behavior"
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=12,
        help='Duration to run test in hours (default: 12)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Interval between polls in minutes (default: 5)'
    )

    args = parser.parse_args()

    # Validate arguments
    if args.duration < 1 or args.duration > 72:
        print("Error: Duration must be between 1 and 72 hours")
        sys.exit(1)

    if args.interval < 1 or args.interval > 60:
        print("Error: Interval must be between 1 and 60 minutes")
        sys.exit(1)

    # Run test
    test = SessionWindowTest(
        duration_hours=args.duration,
        poll_interval_minutes=args.interval
    )
    test.run()


if __name__ == "__main__":
    main()
