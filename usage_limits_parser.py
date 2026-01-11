#!/usr/bin/env python3
"""
Parse output from `claude /usage` command to get overall plan limits.
"""

import subprocess
import re
import logging
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

# Module-level logger
logger = logging.getLogger(__name__)


@dataclass
class SessionLimit:
    """Current session usage limit."""
    percent_used: float
    reset_time: str
    reset_timezone: str


@dataclass
class ExtraUsage:
    """Extra usage (overage) information."""
    percent_used: float
    amount_spent: float
    amount_limit: float
    reset_date: str
    reset_timezone: str


@dataclass
class UsageLimits:
    """Overall usage limits from Claude Pro plan."""
    session: Optional[SessionLimit] = None
    extra: Optional[ExtraUsage] = None


class UsageLimitsParser:
    """Parse the output of `claude /usage` command."""

    @staticmethod
    def run_usage_command() -> str:
        """
        Get usage data by running 'claude /usage' interactively via pexpect.

        Note: /usage command requires running from a Claude project directory.
        The daemon must be configured to run from a project directory (via
        systemd WorkingDirectory setting).

        CRITICAL: This function MUST NOT send any input to the Claude process.
        It only reads output and then terminates. Sending input would cause
        Claude to process prompts and consume usage.

        Returns:
            Command output as string
        """
        try:
            import pexpect
            import time
            import os

            logger.debug(f"CWD={os.getcwd()}")
            logger.debug(f"PATH={os.environ.get('PATH', 'NOT SET')}")

            # Spawn interactive claude session
            # This inherits the current working directory (set by systemd)
            child = pexpect.spawn('claude /usage', timeout=15, encoding='utf-8')
            logger.debug("Spawned 'claude /usage' process")

            # Wait for the complete usage display to load
            # Look for "escape to cancel" which appears at the bottom
            index = child.expect(['escape to cancel', pexpect.TIMEOUT, pexpect.EOF], timeout=15)
            logger.debug(f"pexpect.expect() returned index={index} (0=found, 1=timeout, 2=EOF)")

            if index != 0:
                logger.error(f"Did not see 'escape to cancel'. Buffer preview: {child.before[:200]}")
                return ""

            # Capture all output so far
            output = child.before + child.after
            logger.debug(f"Captured {len(output)} characters from initial read")

            # Give it more time to ensure the actual usage data loads
            # The UI shows "Loading usage data..." initially, then updates
            time.sleep(2.0)

            # Read any additional data that might have come in
            try:
                additional = child.read_nonblocking(size=4096, timeout=1.0)
                if additional:
                    output += additional
                    logger.debug(f"Read additional {len(additional)} characters")
            except:
                pass

            # Close the session cleanly without sending any input
            # CRITICAL: We use close(force=True) which terminates the process
            # WITHOUT sending any characters. Previously used sendline() which
            # accidentally sent newline characters, causing Claude to process
            # empty prompts and consume $12-15/night in extra usage.
            try:
                child.close(force=True)
                logger.debug("Closed pexpect session (no input sent)")
            except:
                pass

            return output

        except Exception as e:
            # Fallback to cache file if pexpect fails
            import os
            logger.error(f"Failed to run /usage command: {e}")

            cache_file = os.path.expanduser("~/.claude_usage_cache.txt")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r') as f:
                        return f.read()
                except:
                    pass

            # No data available
            return ""

    @staticmethod
    def parse_output(output: str) -> UsageLimits:
        """
        Parse the text output from /usage command using simple split strategy.

        Strategy:
        - Split by the word "used" to get exactly 3 parts:
          Part 0: Everything before first "used" (contains session %)
          Part 1: Between first and second "used" (contains session reset, extra %)
          Part 2: After second "used" (contains dollar amounts, extra reset)

        Example output:
        Current session
        ████████████████                                   32% used
        Resets 7pm (America/New_York)

        Extra usage
        ████████████████████████                           48% used
        $24.08 / $50.00 spent · Resets Feb 1 (America/New_York)

        After splitting by "used":
        x[0] = "Current session\n████...32% "
        x[1] = "\nResets 7pm (America/New_York)\n\nExtra usage\n████...48% "
        x[2] = "\n$24.08 / $50.00 spent · Resets Feb 1 (America/New_York)"
        """
        limits = UsageLimits()

        logger.debug("="*80)
        logger.debug("RAW OUTPUT FROM /usage COMMAND:")
        logger.debug("="*80)
        logger.debug(output)
        logger.debug("="*80)

        # Strip ANSI escape codes and carriage returns
        # ANSI codes: \x1b[...
        ansi_escape = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\[[\?<>][0-9;]*[a-zA-Z]')
        clean_output = ansi_escape.sub('', output)

        # Remove carriage returns - they're just for terminal animation
        clean_output = clean_output.replace('\r', '')

        logger.debug("AFTER CLEANING:")
        logger.debug("="*80)
        logger.debug(clean_output)
        logger.debug("="*80)

        # Split by "used" - should give us exactly 3 parts
        parts = clean_output.split('used')

        logger.debug(f"Split by 'used': got {len(parts)} parts")

        if len(parts) != 3:
            logger.error(f"Expected 3 parts after splitting by 'used', got {len(parts)}")
            logger.error("Cannot parse usage data")
            return limits

        # Part 0: Session percentage (ends with "XX% used")
        logger.debug("="*80)
        logger.debug("PART 0 (Session %):")
        logger.debug(parts[0])
        logger.debug("="*80)

        session_pct_match = re.search(r'(\d+)%\s*$', parts[0])
        if session_pct_match:
            session_percent = float(session_pct_match.group(1))
            logger.debug(f"✓ Found session percent: {session_percent}%")

            # Part 1: Session reset info (starts with reset info)
            logger.debug("="*80)
            logger.debug("PART 1 (Session reset + Extra %):")
            logger.debug(parts[1])
            logger.debug("="*80)

            session_reset_match = re.search(r'Resets\s*(\d+(?::\d+)?[ap]m)\s*\(([^)]+)\)', parts[1], re.IGNORECASE)
            if session_reset_match:
                limits.session = SessionLimit(
                    percent_used=session_percent,
                    reset_time=session_reset_match.group(1).strip(),
                    reset_timezone=session_reset_match.group(2).strip()
                )
                logger.debug(f"✓ Parsed session: {session_percent}%, resets {session_reset_match.group(1)} ({session_reset_match.group(2)})")
            else:
                logger.debug(f"✗ Found session percent but couldn't parse reset time from part 1")
        else:
            logger.debug("✗ Could not find session percentage in part 0")

        # Part 1: Extra percentage (ends with "XX% used")
        extra_pct_match = re.search(r'(\d+)%\s*$', parts[1])
        if extra_pct_match:
            extra_percent = float(extra_pct_match.group(1))
            logger.debug(f"✓ Found extra percent: {extra_percent}%")

            # Part 2: Dollar amounts and extra reset
            logger.debug("="*80)
            logger.debug("PART 2 (Extra $ and reset):")
            logger.debug(parts[2])
            logger.debug("="*80)

            # Extract dollar amounts: $XX.XX / $YY.YY spent
            dollar_match = re.search(r'\$(\d+\.\d+)\s*/\s*\$(\d+\.\d+)\s+spent', parts[2])

            # Extract extra reset date
            extra_reset_match = re.search(r'Resets\s*([^(]+?)\s*\(([^)]+)\)', parts[2], re.IGNORECASE)

            if dollar_match and extra_reset_match:
                limits.extra = ExtraUsage(
                    percent_used=extra_percent,
                    amount_spent=float(dollar_match.group(1)),
                    amount_limit=float(dollar_match.group(2)),
                    reset_date=extra_reset_match.group(1).strip(),
                    reset_timezone=extra_reset_match.group(2).strip()
                )
                logger.debug(f"✓ Parsed extra: {extra_percent}%, ${dollar_match.group(1)}/${dollar_match.group(2)}, resets {extra_reset_match.group(1)} ({extra_reset_match.group(2)})")
            else:
                logger.debug(f"✗ Found extra percent but couldn't parse dollar amounts or reset")
                if not dollar_match:
                    logger.debug("  - No dollar pattern found in part 2")
                if not extra_reset_match:
                    logger.debug("  - No reset pattern found in part 2")
        else:
            logger.debug("✗ Could not find extra percentage in part 1")

        logger.debug("="*80)
        logger.debug("FINAL PARSED RESULT:")
        logger.debug(f"  Session: {limits.session}")
        logger.debug(f"  Extra: {limits.extra}")
        logger.debug("="*80)

        return limits

    @classmethod
    def get_current_limits(cls) -> UsageLimits:
        """
        Get current usage limits by running /usage command.

        Returns:
            UsageLimits object with current data
        """
        output = cls.run_usage_command()
        if output:
            return cls.parse_output(output)
        else:
            return UsageLimits()


def main():
    """Test the usage limits parser."""
    print("=" * 60)
    print("Claude Usage Limits Parser Test")
    print("=" * 60)

    # Test with manual input first
    print("\n📋 Testing with sample output...")

    sample_output = """
    Current session
    ████████████████                                   32% used
    Resets 7pm (America/New_York)

    Extra usage
    ████████████████████████                           48% used
    $24.08 / $50.00 spent · Resets Feb 1 (America/New_York)
    """

    limits = UsageLimitsParser.parse_output(sample_output)

    if limits.session:
        print("\n✅ Current Session:")
        print(f"   Usage: {limits.session.percent_used}%")
        print(f"   Resets: {limits.session.reset_time} ({limits.session.reset_timezone})")
    else:
        print("\n❌ Could not parse session data")

    if limits.extra:
        print("\n✅ Extra Usage:")
        print(f"   Usage: {limits.extra.percent_used}%")
        print(f"   Spent: ${limits.extra.amount_spent:.2f} / ${limits.extra.amount_limit:.2f}")
        print(f"   Resets: {limits.extra.reset_date} ({limits.extra.reset_timezone})")
    else:
        print("\n❌ Could not parse extra usage data")

    # Try running actual command
    print("\n" + "=" * 60)
    print("Attempting to run actual `claude /usage` command...")
    print("=" * 60)
    print("\n⚠️  Note: This may not work in automated mode")
    print("   The /usage command is designed for interactive use")
    print("\n   Instead, we'll use the JSONL parser for detailed data")
    print("   and you can manually check /usage for overall limits")


if __name__ == "__main__":
    main()
