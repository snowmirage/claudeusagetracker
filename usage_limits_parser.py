#!/usr/bin/env python3
"""
Usage limits parser - backward compatibility wrapper.

This module now serves as a compatibility layer, redirecting all calls
to the new OAuth API implementation in oauth_usage_api.py.

MIGRATION NOTES (v2.0.0):
- Removed pexpect-based approach (spawning 'claude /usage' command)
- Now uses Claude's OAuth API (fast, reliable, no CLI calls)
- All imports remain the same for backward compatibility
- No more risk of consuming usage during monitoring

The old pexpect approach had several issues:
1. Consumed Claude usage when daemon polled (sendline bug)
2. Slow (2-3 seconds per request)
3. Fragile terminal output parsing
4. Required running from Claude project directory
5. Affected by WSL auto-shutdown

New OAuth API approach:
1. Read-only GET requests (zero usage consumption)
2. Fast (~300ms per request)
3. Structured JSON parsing
4. Works from any directory
5. Industry standard (used by all major Claude usage trackers)
"""

import logging

# Import everything from the new OAuth API module
from oauth_usage_api import (
    SessionLimit,
    ExtraUsage,
    UsageLimits,
    OAuthUsageAPI
)

# Module-level logger
logger = logging.getLogger(__name__)


class UsageLimitsParser:
    """
    Parser for Claude usage limits.

    Now uses OAuth API instead of spawning 'claude /usage' command.
    This class is maintained for backward compatibility.
    """

    @staticmethod
    def get_current_limits() -> UsageLimits:
        """
        Get current usage limits via OAuth API.

        Returns:
            UsageLimits object with session and extra usage data
        """
        return OAuthUsageAPI.get_current_limits()

    @staticmethod
    def run_usage_command() -> str:
        """
        DEPRECATED: This method is no longer used.

        The old pexpect-based approach has been completely removed.
        Use get_current_limits() instead.

        Returns:
            Empty string (kept for backward compatibility)
        """
        logger.warning(
            "run_usage_command() is deprecated and does nothing. "
            "Use get_current_limits() instead."
        )
        return ""

    @staticmethod
    def parse_output(output: str) -> UsageLimits:
        """
        DEPRECATED: This method is no longer used.

        The old terminal output parsing has been replaced with JSON parsing
        from the OAuth API.

        Args:
            output: Ignored

        Returns:
            Empty UsageLimits (kept for backward compatibility)
        """
        logger.warning(
            "parse_output() is deprecated and does nothing. "
            "Use get_current_limits() instead."
        )
        return UsageLimits()


def main():
    """Test the usage limits parser."""
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print("=" * 70)
    print("Claude Usage Limits Parser (v2.0.0 - OAuth API)")
    print("=" * 70)

    print("\n📡 Fetching usage limits via OAuth API...")

    limits = UsageLimitsParser.get_current_limits()

    if not limits.session and not limits.extra:
        print("❌ No usage data available")
        print("\nMake sure:")
        print("  1. You're logged in to Claude Code")
        print("  2. Run 'claude' to verify authentication")
        return

    if limits.session:
        print("\n✅ Current Session:")
        print(f"   Usage: {limits.session.percent_used}%")
        print(f"   Resets: {limits.session.reset_time} ({limits.session.reset_timezone})")
    else:
        print("\n⚠️  No session data available")

    if limits.extra:
        print("\n✅ Extra Usage:")
        print(f"   Usage: {limits.extra.percent_used}%")
        print(f"   Spent: ${limits.extra.amount_spent:.2f} / ${limits.extra.amount_limit:.2f}")
        print(f"   Resets: {limits.extra.reset_date} ({limits.extra.reset_timezone})")
    else:
        print("\n⚠️  No extra usage data available")

    print("\n" + "=" * 70)
    print("✅ Using new OAuth API approach (fast, reliable, safe)")
    print("=" * 70)


if __name__ == "__main__":
    main()
