#!/usr/bin/env python3
"""
OAuth-based usage data fetcher using Claude's official OAuth API.

This module provides a clean, reliable way to fetch Claude usage data
using the OAuth tokens already stored by Claude Code in ~/.claude/.credentials.json

Key advantages over pexpect approach:
- Fast (~300ms vs 2-3 seconds)
- No risk of consuming usage (read-only GET request)
- Structured JSON response (no terminal output parsing)
- Works anywhere (no need to run from Claude project directory)
- Industry standard (used by all major Claude usage trackers)
"""

import json
import requests
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass

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


class OAuthUsageAPI:
    """
    Fetch Claude usage data using OAuth API.

    This uses the OAuth token stored by Claude Code at ~/.claude/.credentials.json
    No manual authentication or cookie extraction required.
    """

    API_URL = "https://api.anthropic.com/api/oauth/usage"
    CREDENTIALS_FILE = Path.home() / ".claude" / ".credentials.json"

    # Request timeout in seconds
    TIMEOUT = 10

    @classmethod
    def load_oauth_token(cls) -> Optional[str]:
        """
        Load OAuth access token from Claude Code credentials.

        Returns:
            Access token string (starts with sk-ant-oat01-) or None if not found
        """
        try:
            if not cls.CREDENTIALS_FILE.exists():
                logger.error(f"Credentials file not found: {cls.CREDENTIALS_FILE}")
                return None

            with open(cls.CREDENTIALS_FILE, 'r') as f:
                creds = json.load(f)

            token = creds.get("claudeAiOauth", {}).get("accessToken")

            if not token:
                logger.error("No OAuth access token found in credentials file")
                return None

            logger.debug(f"Successfully loaded OAuth token (starts with {token[:20]}...)")
            return token

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse credentials file: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading OAuth token: {e}")
            return None

    @classmethod
    def get_usage_data(cls) -> Optional[Dict[str, Any]]:
        """
        Fetch usage data from Claude's OAuth API.

        Returns:
            Dictionary with usage data:
            {
                "five_hour": {
                    "utilization": float (0-100),
                    "resets_at": str (ISO 8601 timestamp)
                },
                "extra_usage": {
                    "is_enabled": bool,
                    "monthly_limit": int (cents),
                    "used_credits": float (cents),
                    "utilization": float (0-100)
                },
                "seven_day": null,  # Pro plan doesn't have weekly limits
                ...
            }

            Returns None if request fails.
        """
        # Load OAuth token
        token = cls.load_oauth_token()
        if not token:
            return None

        # Prepare headers
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "claude-code/2.0.37"
        }

        logger.debug(f"Making OAuth API request to {cls.API_URL}")

        try:
            response = requests.get(
                cls.API_URL,
                headers=headers,
                timeout=cls.TIMEOUT
            )

            # Log response status
            logger.debug(f"API response status: {response.status_code}")

            # Raise exception for bad status codes
            response.raise_for_status()

            # Parse JSON response
            data = response.json()
            logger.debug(f"Successfully fetched usage data: {json.dumps(data, indent=2)}")

            return data

        except requests.exceptions.Timeout:
            logger.error(f"Request timed out after {cls.TIMEOUT} seconds")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            logger.error(f"Response body: {e.response.text if e.response else 'N/A'}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching usage data: {e}")
            return None

    @classmethod
    def parse_usage_limits(cls, data: Dict[str, Any]) -> UsageLimits:
        """
        Parse usage data from API response into UsageLimits object.

        Args:
            data: Raw API response dictionary

        Returns:
            UsageLimits object with parsed session and extra usage data
        """
        limits = UsageLimits()

        # Parse session data (5-hour rolling window)
        if data.get("five_hour"):
            five_hour = data["five_hour"]

            # Extract reset time from ISO 8601 timestamp
            resets_at_str = five_hour.get("resets_at", "")
            try:
                resets_at = datetime.fromisoformat(resets_at_str.replace('Z', '+00:00'))
                # Format as "3pm" or "2:59pm"
                reset_time = resets_at.strftime("%-I:%M%p").lower()
                if reset_time.endswith(":00am") or reset_time.endswith(":00pm"):
                    reset_time = resets_at.strftime("%-I%p").lower()
            except:
                reset_time = resets_at_str

            limits.session = SessionLimit(
                percent_used=float(five_hour.get("utilization", 0.0)),
                reset_time=reset_time,
                reset_timezone="UTC"
            )

            logger.debug(f"Parsed session: {limits.session.percent_used}%, resets {limits.session.reset_time}")

        # Parse extra usage data
        if data.get("extra_usage"):
            extra = data["extra_usage"]

            # Convert cents to dollars
            used_dollars = extra.get("used_credits", 0.0) / 100.0
            limit_dollars = extra.get("monthly_limit", 0) / 100.0

            # Calculate utilization percentage
            utilization = extra.get("utilization", 0.0)

            limits.extra = ExtraUsage(
                percent_used=float(utilization),
                amount_spent=used_dollars,
                amount_limit=limit_dollars,
                reset_date="Monthly",
                reset_timezone="UTC"
            )

            logger.debug(f"Parsed extra: {limits.extra.percent_used}%, ${limits.extra.amount_spent:.2f}/${limits.extra.amount_limit:.2f}")

        return limits

    @classmethod
    def get_current_limits(cls) -> UsageLimits:
        """
        Get current usage limits.

        This is the main public method that combines fetching and parsing.

        Returns:
            UsageLimits object with current session and extra usage data,
            or empty UsageLimits if request fails.
        """
        logger.info("Fetching usage data via OAuth API")

        # Fetch data from API
        data = cls.get_usage_data()

        if not data:
            logger.warning("Failed to fetch usage data from OAuth API")
            return UsageLimits()

        # Parse and return
        limits = cls.parse_usage_limits(data)

        logger.info("Successfully retrieved usage limits")
        return limits


def main():
    """Test the OAuth usage API."""
    # Set up logging for testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print("=" * 70)
    print("OAuth Usage API Test")
    print("=" * 70)

    # Test fetching data
    print("\n📡 Fetching usage data from OAuth API...")
    data = OAuthUsageAPI.get_usage_data()

    if not data:
        print("❌ Failed to fetch usage data")
        print("\nMake sure:")
        print("  1. You're logged in to Claude Code (run 'claude' to check)")
        print("  2. The credentials file exists at ~/.claude/.credentials.json")
        return

    print("✅ Successfully fetched data")
    print("\n📊 Raw API Response:")
    print(json.dumps(data, indent=2))

    # Test parsing
    print("\n" + "=" * 70)
    print("Parsed Usage Limits")
    print("=" * 70)

    limits = OAuthUsageAPI.parse_usage_limits(data)

    if limits.session:
        print("\n✅ Current Session:")
        print(f"   Usage: {limits.session.percent_used}%")
        print(f"   Resets: {limits.session.reset_time} ({limits.session.reset_timezone})")
    else:
        print("\n❌ No session data available")

    if limits.extra:
        print("\n✅ Extra Usage:")
        print(f"   Usage: {limits.extra.percent_used}%")
        print(f"   Spent: ${limits.extra.amount_spent:.2f} / ${limits.extra.amount_limit:.2f}")
        print(f"   Resets: {limits.extra.reset_date} ({limits.extra.reset_timezone})")
    else:
        print("\n❌ No extra usage data available")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
