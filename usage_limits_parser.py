#!/usr/bin/env python3
"""
Parse output from `claude /usage` command to get overall plan limits.
"""

import subprocess
import re
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


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
        Run the `claude /usage` command and capture output.

        Returns:
            Command output as string
        """
        try:
            # Run claude command non-interactively
            # We need to send /usage followed by Escape to exit
            result = subprocess.run(
                ["claude"],
                input="/usage\n\x1b",  # /usage command + Escape key
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            print("⚠️  Command timed out")
            return ""
        except FileNotFoundError:
            print("❌ 'claude' command not found in PATH")
            return ""
        except Exception as e:
            print(f"❌ Error running command: {e}")
            return ""

    @staticmethod
    def parse_output(output: str) -> UsageLimits:
        """
        Parse the text output from /usage command.

        Example output:
        Current session
        ████████████████                                   32% used
        Resets 7pm (America/New_York)

        Extra usage
        ████████████████████████                           48% used
        $24.08 / $50.00 spent · Resets Feb 1 (America/New_York)
        """
        limits = UsageLimits()

        # Parse current session
        session_match = re.search(r'Current session.*?(\d+)%\s+used.*?Resets\s+(.+?)\s+\((.+?)\)',
                                  output, re.DOTALL | re.IGNORECASE)
        if session_match:
            limits.session = SessionLimit(
                percent_used=float(session_match.group(1)),
                reset_time=session_match.group(2).strip(),
                reset_timezone=session_match.group(3).strip()
            )

        # Parse extra usage
        extra_match = re.search(
            r'Extra usage.*?(\d+)%\s+used.*?\$(\d+\.\d+)\s*/\s*\$(\d+\.\d+)\s+spent.*?Resets\s+(.+?)\s+\((.+?)\)',
            output, re.DOTALL | re.IGNORECASE
        )
        if extra_match:
            limits.extra = ExtraUsage(
                percent_used=float(extra_match.group(1)),
                amount_spent=float(extra_match.group(2)),
                amount_limit=float(extra_match.group(3)),
                reset_date=extra_match.group(4).strip(),
                reset_timezone=extra_match.group(5).strip()
            )

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
