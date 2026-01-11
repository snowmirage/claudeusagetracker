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

        Note: /usage command requires running from a Claude project directory.
        The daemon must be configured to run from a project directory (via
        systemd WorkingDirectory setting).

        Returns:
            Command output as string
        """
        try:
            import pexpect
            import time
            import logging
            import os

            # DEBUG logging
            logging.info(f"DEBUG: CWD={os.getcwd()}, PATH={os.environ.get('PATH', 'NOT SET')}")

            # Spawn interactive claude session
            # This inherits the current working directory (set by systemd)
            child = pexpect.spawn('claude /usage', timeout=15, encoding='utf-8')

            logging.info(f"DEBUG: Spawned claude /usage")

            # Wait for the complete usage display to load
            # Look for "escape to cancel" which appears at the bottom
            index = child.expect(['escape to cancel', pexpect.TIMEOUT, pexpect.EOF], timeout=15)
            logging.info(f"DEBUG: expect returned index={index}")

            if index != 0:
                logging.error(f"DEBUG: Did not see 'escape to cancel'. Buffer: {child.before[:200]}")
                return ""

            # Capture all output so far
            output = child.before + child.after
            logging.info(f"DEBUG: Captured {len(output)} chars of output")

            # Give it more time to ensure the actual usage data loads
            # The UI shows "Loading usage data..." initially, then updates
            time.sleep(2.0)

            # Read any additional data that might have come in
            try:
                additional = child.read_nonblocking(size=4096, timeout=1.0)
                if additional:
                    output += additional
                    logging.info(f"DEBUG: Read additional {len(additional)} chars")
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
        import logging
        limits = UsageLimits()

        # Strip ANSI escape codes before parsing
        # This handles terminal control sequences that may be in the output
        ansi_escape = re.compile(r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\[[\?<>][0-9;]*[a-zA-Z]')
        clean_output = ansi_escape.sub('', output)

        # Handle carriage returns - collect all non-empty text parts
        # The /usage output uses \r to update the display, but we want all the text
        lines = []
        for line in clean_output.split('\n'):
            if '\r' in line:
                # Collect all non-whitespace-only parts
                parts = line.split('\r')
                text_parts = [p.strip() for p in parts if p.strip() and not p.strip().startswith('escape to cancel')]
                # Join meaningful parts with spaces
                if text_parts:
                    lines.append(' '.join(text_parts))
            else:
                lines.append(line)
        clean_output = '\n'.join(lines)

        # DEBUG: Log a sample of cleaned output
        logging.info(f"DEBUG: After cleaning, output sample:")
        for i, line in enumerate(clean_output.split('\n')[:20]):
            logging.info(f"DEBUG: Line {i}: {repr(line)}")

        # Parse current session
        # Handle both "Current session" and corrupted "Curretsession" or similar
        # The text may have missing spaces due to terminal rendering issues
        session_match = re.search(r'Curre[nt\s]*session.*?(\d+)%\s*used.*?Resets\s*(\d+[ap]m)\s*\((.+?)\)',
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
