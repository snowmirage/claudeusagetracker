#!/usr/bin/env python3
"""
Claude Usage Daemon - Background data collection service

Runs continuously in the background to:
1. Poll OAuth usage API every 30 seconds
2. Capture ALL usage data (session %, extra $, reset times, etc.)
3. Calculate session boundaries and extra usage deltas
4. Store complete data in ~/.claudeusagetracker/

This allows the TUI to display accurate session vs extra usage
even when the TUI itself is not running.

v2.0.0 Changes:
- Now uses Claude's OAuth API (fast, reliable, read-only)
- No longer spawns 'claude /usage' command (eliminated usage consumption bug)
- Faster polling (~300ms vs 2-3 seconds)
- More reliable JSON parsing vs terminal output parsing
"""

import os
import sys
import time
import json
import signal
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import logging

# Import our existing parsers
from usage_limits_parser import UsageLimitsParser
from claude_data_parser import ClaudeDataParser, TokenUsage
from version import __version__, __title__


class ClaudeUsageDaemon:
    """Background daemon for collecting Claude usage data."""

    POLL_INTERVAL = 30  # seconds
    DATA_DIR = Path.home() / ".claudeusagetracker"
    RAW_LOG_FILE = DATA_DIR / "raw_usage_log.jsonl"
    DAILY_SUMMARY_FILE = DATA_DIR / "daily_summary.json"
    SESSION_LOG_FILE = DATA_DIR / "session_log.json"

    def __init__(self, debug=False):
        self.limits_parser = UsageLimitsParser()
        self.data_parser = ClaudeDataParser()
        self.running = True
        self.last_extra_usage = None
        self.last_session_reset = None
        self.setup_logging(debug=debug)
        self.ensure_data_directory()

    def setup_logging(self, debug=False):
        """Set up logging to file and console.

        Args:
            debug: If True, set log level to DEBUG; otherwise INFO
        """
        log_file = self.DATA_DIR / "daemon.log"
        self.DATA_DIR.mkdir(exist_ok=True)

        level = logging.DEBUG if debug else logging.INFO

        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

        if debug:
            self.logger.info("Debug logging enabled")
        else:
            self.logger.info("Normal logging (INFO level)")

    def ensure_data_directory(self):
        """Create data directory if it doesn't exist."""
        self.DATA_DIR.mkdir(exist_ok=True)
        self.logger.info(f"Data directory: {self.DATA_DIR}")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False

    def calculate_session_start_time(self, reset_time_str: str, timezone_str: str) -> Optional[datetime]:
        """Calculate when the current session started based on reset time.

        Args:
            reset_time_str: e.g., "2pm" or "7pm"
            timezone_str: e.g., "America/New_York"

        Returns:
            datetime of session start (5 hours before reset)
        """
        try:
            from datetime import datetime
            import pytz

            # Parse reset time (e.g., "2pm" -> 14:00)
            reset_hour = self._parse_time_to_hour(reset_time_str)

            # Get timezone
            tz = pytz.timezone(timezone_str)
            now = datetime.now(tz)

            # Create reset datetime for today
            reset_today = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)

            # If reset hasn't happened yet today, use today's reset
            # Otherwise, it's already reset and the next reset is in the future
            if now < reset_today:
                # Current session started 5 hours before today's reset
                session_start = reset_today - timedelta(hours=5)
            else:
                # Already past today's reset, so session started at the reset time
                session_start = reset_today

            return session_start
        except Exception as e:
            self.logger.error(f"Error calculating session start time: {e}")
            return None

    def _parse_time_to_hour(self, time_str: str) -> int:
        """Parse time string like '2pm' or '7am' to hour (24-hour format)."""
        time_str = time_str.lower().strip()

        # Extract number
        hour = int(''.join(filter(str.isdigit, time_str)))

        # Check AM/PM
        if 'pm' in time_str and hour != 12:
            hour += 12
        elif 'am' in time_str and hour == 12:
            hour = 0

        return hour

    def collect_jsonl_data(self) -> Dict[str, Any]:
        """Collect token usage from JSONL files.

        Returns:
            Dictionary with token counts by date
        """
        try:
            stats = self.data_parser.get_usage_summary()

            # Convert by_date to regular dict for JSON serialization
            by_date = {}
            for date_key, usage in stats.by_date.items():
                by_date[date_key] = {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cache_creation_tokens": usage.cache_creation_tokens,
                    "cache_read_tokens": usage.cache_read_tokens,
                    "total_tokens": usage.total_tokens
                }

            return {
                "total_messages": stats.message_count,
                "by_date": by_date,
                "date_range": [
                    stats.date_range[0].isoformat() if stats.date_range[0] else None,
                    stats.date_range[1].isoformat() if stats.date_range[1] else None
                ]
            }
        except Exception as e:
            self.logger.error(f"Error collecting JSONL data: {e}")
            return {"by_date": {}}

    def collect_usage_data(self) -> Optional[Dict[str, Any]]:
        """Collect current usage data from /usage command.

        Returns:
            Dictionary with all captured data, or None if failed
        """
        try:
            # Get usage limits via OAuth API
            limits = self.limits_parser.get_current_limits()

            # Log what we got from parser (debug level)
            self.logger.debug(f"Parser returned session={limits.session}, extra={limits.extra}, plan={limits.plan}")

            # Build data record with ALL captured fields
            now = datetime.now()
            data = {
                "timestamp": now.isoformat(),
                "session": None,
                "extra": None,
                "plan": None,
                "weekly": None,
                "weekly_opus": None,
                "weekly_sonnet": None
            }

            # Capture plan information
            if limits.plan:
                data["plan"] = {
                    "display_name": limits.plan.display_name,
                    "tier": limits.plan.tier,
                    "session_token_limit": limits.plan.session_token_limit,
                    "has_max": limits.plan.has_max,
                    "has_pro": limits.plan.has_pro,
                    "organization_type": limits.plan.organization_type
                }

            # Capture session data
            if limits.session:
                session_start = self.calculate_session_start_time(
                    limits.session.reset_time,
                    limits.session.reset_timezone
                )

                data["session"] = {
                    "percent_used": limits.session.percent_used,
                    "reset_time": limits.session.reset_time,
                    "reset_timezone": limits.session.reset_timezone,
                    "calculated_start_time": session_start.isoformat() if session_start else None
                }

            # Capture weekly limits (Max plans only)
            if limits.weekly:
                data["weekly"] = {
                    "percent_used": limits.weekly.percent_used,
                    "reset_time": limits.weekly.reset_time,
                    "reset_timezone": limits.weekly.reset_timezone,
                    "limit_type": limits.weekly.limit_type
                }

            if limits.weekly_opus:
                data["weekly_opus"] = {
                    "percent_used": limits.weekly_opus.percent_used,
                    "reset_time": limits.weekly_opus.reset_time,
                    "reset_timezone": limits.weekly_opus.reset_timezone,
                    "limit_type": limits.weekly_opus.limit_type
                }

            if limits.weekly_sonnet:
                data["weekly_sonnet"] = {
                    "percent_used": limits.weekly_sonnet.percent_used,
                    "reset_time": limits.weekly_sonnet.reset_time,
                    "reset_timezone": limits.weekly_sonnet.reset_timezone,
                    "limit_type": limits.weekly_sonnet.limit_type
                }

            # Capture extra usage data
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
            self.logger.error(f"Error collecting usage data: {e}")
            return None

    def append_raw_log(self, data: Dict[str, Any]):
        """Append data to raw JSONL log (one JSON object per line)."""
        try:
            with open(self.RAW_LOG_FILE, 'a') as f:
                f.write(json.dumps(data) + '\n')
        except Exception as e:
            self.logger.error(f"Error writing raw log: {e}")

    def update_daily_summary(self, data: Dict[str, Any]):
        """Update daily summary with new data.

        Tracks:
        - Daily session vs extra token totals (from JSONL)
        - Extra usage cost deltas (from /usage)
        - Session count changes (from /usage)
        """
        try:
            # Load existing summary
            if self.DAILY_SUMMARY_FILE.exists():
                with open(self.DAILY_SUMMARY_FILE, 'r') as f:
                    summary = json.load(f)
            else:
                summary = {}

            # Get today's date
            today = datetime.now().date().isoformat()

            # Initialize today's entry if needed
            if today not in summary:
                summary[today] = {
                    "session_tokens": 0,
                    "extra_tokens": 0,
                    "total_tokens": 0,
                    "extra_cost": 0.0,
                    "sessions_count": 0,
                    "last_updated": data["timestamp"]
                }

            # Update token counts from JSONL data
            if data.get("jsonl_tokens") and data["jsonl_tokens"].get("by_date"):
                today_jsonl = data["jsonl_tokens"]["by_date"].get(today, {})
                if today_jsonl:
                    # Store actual token counts from JSONL
                    summary[today]["total_tokens"] = today_jsonl.get("total_tokens", 0)

                    # Calculate session vs extra tokens
                    # For now, use simple heuristic: everything is session unless we detect extra usage
                    # We'll refine this later with session boundary tracking
                    total = today_jsonl.get("total_tokens", 0)

                    if self.last_extra_usage is not None and data.get("extra"):
                        current_extra = data["extra"]["amount_spent"]
                        if current_extra > 0:
                            # Estimate extra tokens based on cost
                            # Average cost per token ~$0.000003 (rough estimate)
                            estimated_extra_tokens = int(current_extra / 0.000003)
                            summary[today]["extra_tokens"] = min(estimated_extra_tokens, total)
                            summary[today]["session_tokens"] = total - summary[today]["extra_tokens"]
                        else:
                            summary[today]["session_tokens"] = total
                            summary[today]["extra_tokens"] = 0
                    else:
                        # No extra usage yet, all tokens are session
                        summary[today]["session_tokens"] = total
                        summary[today]["extra_tokens"] = 0

            # Detect extra usage changes
            if data.get("extra"):
                current_extra = data["extra"]["amount_spent"]

                if self.last_extra_usage is not None:
                    delta = current_extra - self.last_extra_usage
                    if delta > 0:
                        # Extra usage increased
                        summary[today]["extra_cost"] = current_extra
                        self.logger.info(f"Extra usage increased by ${delta:.2f} to ${current_extra:.2f}")

                self.last_extra_usage = current_extra

            # Detect session resets (reset time changed)
            if data.get("session"):
                current_reset = data["session"]["reset_time"]

                if self.last_session_reset is not None and current_reset != self.last_session_reset:
                    # Session reset detected
                    summary[today]["sessions_count"] += 1
                    self.logger.info(f"Session reset detected: {self.last_session_reset} -> {current_reset}")

                self.last_session_reset = current_reset

            summary[today]["last_updated"] = data["timestamp"]

            # Write updated summary
            with open(self.DAILY_SUMMARY_FILE, 'w') as f:
                json.dump(summary, f, indent=2)

        except Exception as e:
            self.logger.error(f"Error updating daily summary: {e}")

    def run(self):
        """Main daemon loop."""
        self.logger.info("=" * 60)
        self.logger.info("Claude Usage Daemon Started")
        self.logger.info(f"Poll interval: {self.POLL_INTERVAL} seconds")
        self.logger.info(f"Data directory: {self.DATA_DIR}")
        self.logger.info("=" * 60)

        # Register signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

        poll_count = 0

        while self.running:
            try:
                poll_count += 1
                self.logger.info(f"Poll #{poll_count}")

                # Collect /usage limits data
                limits_data = self.collect_usage_data()

                # Collect JSONL token data
                jsonl_data = self.collect_jsonl_data()

                # Combine both data sources
                if limits_data:
                    # Add JSONL data to the record
                    limits_data["jsonl_tokens"] = jsonl_data

                    # Log all captured data
                    self.append_raw_log(limits_data)

                    # Update daily summary (combining both sources)
                    self.update_daily_summary(limits_data)

                    # Log summary
                    if limits_data.get("session"):
                        self.logger.info(f"  Session: {limits_data['session']['percent_used']}% used, resets {limits_data['session']['reset_time']}")
                    if limits_data.get("extra"):
                        self.logger.info(f"  Extra: ${limits_data['extra']['amount_spent']:.2f} / ${limits_data['extra']['amount_limit']:.2f}")

                    # Log JSONL stats
                    today = datetime.now().date().isoformat()
                    today_tokens = jsonl_data.get("by_date", {}).get(today, {}).get("total_tokens", 0)
                    if today_tokens > 0:
                        self.logger.info(f"  Tokens today (JSONL): {today_tokens:,}")
                else:
                    self.logger.warning("Failed to collect usage data")

                # Sleep until next poll
                time.sleep(self.POLL_INTERVAL)

            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                self.logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(self.POLL_INTERVAL)

        self.logger.info("Daemon shutdown complete")


def main():
    """Entry point for daemon."""
    parser = argparse.ArgumentParser(
        prog='claude-usage-daemon',
        description='Background daemon for collecting Claude usage data',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'{__title__} Daemon {__version__}'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging (verbose output)'
    )

    args = parser.parse_args()

    # Run the daemon with debug mode if requested
    daemon = ClaudeUsageDaemon(debug=args.debug)
    daemon.run()


if __name__ == "__main__":
    main()
