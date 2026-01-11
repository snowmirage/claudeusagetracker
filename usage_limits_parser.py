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
        Get usage data by running 'claude /usage' interactively via pexpect.

        Note: /usage command only works from within a Claude project directory.

        Returns:
            Command output as string
        """
        try:
            import pexpect
            import os
            import time
            from pathlib import Path

            # /usage only works from within a Claude project directory
            # Find a Claude project to run from
            claude_projects_dir = Path.home() / ".claude" / "projects"
            if not claude_projects_dir.exists():
                # No Claude projects found
                return ""

            # Get the first available project directory
            project_dirs = [d for d in claude_projects_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
            if not project_dirs:
                return ""

            # Use the first project directory
            project_dir = project_dirs[0]

            # Spawn interactive claude session from project directory
            child = pexpect.spawn('claude /usage', timeout=15, encoding='utf-8', cwd=str(project_dir))

            # Wait for the complete usage display to load
            # Look for "escape to cancel" which appears at the bottom
            child.expect('escape to cancel', timeout=15)

            # Capture all output so far
            output = child.before + child.after

            # Give it a bit more time to ensure all data is rendered
            time.sleep(0.5)

            # Read any additional data that might have come in
            try:
                additional = child.read_nonblocking(size=4096, timeout=0.5)
                if additional:
                    output += additional
            except:
                pass

            # Send ESC to exit
            try:
                child.sendline('\x1b')
                child.close(force=True)
            except:
                pass

            return output

        except Exception as e:
            # Fallback to cache file if pexpect fails
            import os
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

        # Strip ANSI escape codes before parsing
        # This handles terminal control sequences that may be in the output
        ansi_escape = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\[[\?<>][0-9;]*[a-zA-Z]')
        clean_output = ansi_escape.sub('', output)

        # Parse current session
        # Use \s* (zero or more whitespace) instead of \s+ to handle concatenated text
        session_match = re.search(r'Current session.*?(\d+)%\s*used.*?Resets\s*(.+?)\s*\((.+?)\)',
                                  clean_output, re.DOTALL | re.IGNORECASE)
        if session_match:
            limits.session = SessionLimit(
                percent_used=float(session_match.group(1)),
                reset_time=session_match.group(2).strip(),
                reset_timezone=session_match.group(3).strip()
            )

        # Parse extra usage
        extra_match = re.search(
            r'Extra usage.*?(\d+)%\s*used.*?\$(\d+\.\d+)\s*/\s*\$(\d+\.\d+)\s+spent.*?Resets\s*(.+?)\s*\((.+?)\)',
            clean_output, re.DOTALL | re.IGNORECASE
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
