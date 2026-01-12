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
class WeeklyLimit:
    """Weekly usage limit (Max plans only)."""
    percent_used: float
    reset_time: str
    reset_timezone: str
    limit_type: str  # "overall", "opus", "sonnet", "oauth_apps"


@dataclass
class ExtraUsage:
    """Extra usage (overage) information."""
    percent_used: float
    amount_spent: float
    amount_limit: float
    reset_date: str
    reset_timezone: str


@dataclass
class PlanInfo:
    """Claude subscription plan information."""
    has_max: bool
    has_pro: bool
    tier: str  # e.g., "default_claude_max_5x", "default_claude_ai"
    organization_type: str  # e.g., "claude_max", "individual"
    display_name: str  # e.g., "Claude Max 5x", "Claude Pro"
    session_token_limit: int  # e.g., 88000 for Max 5x, 44000 for Pro


@dataclass
class UsageLimits:
    """Overall usage limits from Claude plan."""
    session: Optional[SessionLimit] = None
    extra: Optional[ExtraUsage] = None
    plan: Optional[PlanInfo] = None
    weekly: Optional[WeeklyLimit] = None
    weekly_opus: Optional[WeeklyLimit] = None
    weekly_sonnet: Optional[WeeklyLimit] = None


class OAuthUsageAPI:
    """
    Fetch Claude usage data using OAuth API.

    This uses the OAuth token stored by Claude Code at ~/.claude/.credentials.json
    No manual authentication or cookie extraction required.
    """

    API_URL = "https://api.anthropic.com/api/oauth/usage"
    PROFILE_URL = "https://api.anthropic.com/api/oauth/profile"
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
    def get_user_profile(cls) -> Optional[Dict[str, Any]]:
        """
        Fetch user profile and plan information from OAuth API.

        Returns:
            Dictionary with profile data including plan type, tier, etc.
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

        logger.debug(f"Making OAuth profile request to {cls.PROFILE_URL}")

        try:
            response = requests.get(
                cls.PROFILE_URL,
                headers=headers,
                timeout=cls.TIMEOUT
            )

            logger.debug(f"Profile API response status: {response.status_code}")
            response.raise_for_status()

            data = response.json()
            logger.debug(f"Successfully fetched profile data")

            return data

        except requests.exceptions.Timeout:
            logger.error(f"Profile request timed out after {cls.TIMEOUT} seconds")
            return None
        except requests.exceptions.HTTPError as e:
            logger.error(f"Profile HTTP error: {e}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Profile request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse profile JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching profile: {e}")
            return None

    @classmethod
    def parse_plan_info(cls, profile_data: Dict[str, Any]) -> Optional[PlanInfo]:
        """
        Parse plan information from profile API response.

        Args:
            profile_data: Raw profile API response

        Returns:
            PlanInfo object with plan details
        """
        try:
            account = profile_data.get("account", {})
            org = profile_data.get("organization", {})

            has_max = account.get("has_claude_max", False)
            has_pro = account.get("has_claude_pro", False)
            tier = org.get("rate_limit_tier", "unknown")
            org_type = org.get("organization_type", "unknown")

            # Determine display name and session limit based on tier
            if "max_20x" in tier.lower():
                display_name = "Claude Max 20x"
                session_limit = 220000
            elif "max_5x" in tier.lower():
                display_name = "Claude Max 5x"
                session_limit = 88000
            elif has_max:
                display_name = "Claude Max"
                session_limit = 88000  # Default to 5x if unclear
            elif has_pro:
                display_name = "Claude Pro"
                session_limit = 44000
            else:
                display_name = "Claude Free"
                session_limit = 0

            plan = PlanInfo(
                has_max=has_max,
                has_pro=has_pro,
                tier=tier,
                organization_type=org_type,
                display_name=display_name,
                session_token_limit=session_limit
            )

            logger.debug(f"Parsed plan: {display_name} (tier: {tier}, session limit: {session_limit:,} tokens)")

            return plan

        except Exception as e:
            logger.error(f"Error parsing plan info: {e}")
            return None

    @classmethod
    def parse_usage_limits(cls, data: Dict[str, Any], plan: Optional[PlanInfo] = None) -> UsageLimits:
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

        # Include plan information
        limits.plan = plan

        # Parse weekly limits (Max plans only)
        def parse_weekly(key: str, limit_type: str) -> Optional[WeeklyLimit]:
            if data.get(key):
                weekly_data = data[key]
                resets_at_str = weekly_data.get("resets_at", "")
                try:
                    resets_at = datetime.fromisoformat(resets_at_str.replace('Z', '+00:00'))
                    reset_time = resets_at.strftime("%Y-%m-%d %I:%M%p").lower()
                except:
                    reset_time = resets_at_str

                limit = WeeklyLimit(
                    percent_used=float(weekly_data.get("utilization", 0.0)),
                    reset_time=reset_time,
                    reset_timezone="UTC",
                    limit_type=limit_type
                )
                logger.debug(f"Parsed weekly {limit_type}: {limit.percent_used}%, resets {limit.reset_time}")
                return limit
            return None

        limits.weekly = parse_weekly("seven_day", "overall")
        limits.weekly_opus = parse_weekly("seven_day_opus", "opus")
        limits.weekly_sonnet = parse_weekly("seven_day_sonnet", "sonnet")

        return limits

    @classmethod
    def get_current_limits(cls) -> UsageLimits:
        """
        Get current usage limits.

        This is the main public method that combines fetching and parsing.

        Returns:
            UsageLimits object with current session and extra usage data,
            plan information, and weekly limits (for Max plans),
            or empty UsageLimits if request fails.
        """
        logger.info("Fetching usage data and plan info via OAuth API")

        # Fetch profile/plan data
        profile_data = cls.get_user_profile()
        plan = None
        if profile_data:
            plan = cls.parse_plan_info(profile_data)

        # Fetch usage data from API
        data = cls.get_usage_data()

        if not data:
            logger.warning("Failed to fetch usage data from OAuth API")
            # Return empty limits but include plan if we got it
            limits = UsageLimits()
            limits.plan = plan
            return limits

        # Parse and return (includes plan info)
        limits = cls.parse_usage_limits(data, plan)

        logger.info("Successfully retrieved usage limits and plan info")
        return limits


def main():
    """Test the OAuth usage API."""
    # Set up logging for testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print("=" * 70)
    print("OAuth Usage API Test (v2.0.0 with Plan Detection)")
    print("=" * 70)

    # Test fetching complete limits (includes plan detection)
    print("\n📡 Fetching usage data and plan info...")
    limits = OAuthUsageAPI.get_current_limits()

    if not limits.session and not limits.extra and not limits.plan:
        print("❌ Failed to fetch data")
        print("\nMake sure:")
        print("  1. You're logged in to Claude Code (run 'claude' to check)")
        print("  2. The credentials file exists at ~/.claude/.credentials.json")
        return

    print("✅ Successfully fetched data")

    # Display plan information
    print("\n" + "=" * 70)
    print("📋 Plan Information")
    print("=" * 70)

    if limits.plan:
        print(f"\n✅ Subscription: {limits.plan.display_name}")
        print(f"   Tier: {limits.plan.tier}")
        print(f"   Session Token Limit: {limits.plan.session_token_limit:,}")
        print(f"   Has Max: {limits.plan.has_max}")
        print(f"   Has Pro: {limits.plan.has_pro}")
    else:
        print("\n⚠️  Could not determine plan type")

    # Display usage limits
    print("\n" + "=" * 70)
    print("📊 Usage Limits")
    print("=" * 70)

    if limits.session:
        print("\n✅ Current Session (5-hour window):")
        print(f"   Usage: {limits.session.percent_used}%")
        print(f"   Resets: {limits.session.reset_time} ({limits.session.reset_timezone})")
    else:
        print("\n❌ No session data available")

    # Weekly limits (Max plans only)
    if limits.weekly:
        print("\n✅ Weekly Limit (Overall):")
        print(f"   Usage: {limits.weekly.percent_used}%")
        print(f"   Resets: {limits.weekly.reset_time}")

    if limits.weekly_opus:
        print("\n✅ Weekly Opus Limit:")
        print(f"   Usage: {limits.weekly_opus.percent_used}%")
        print(f"   Resets: {limits.weekly_opus.reset_time}")

    if limits.weekly_sonnet:
        print("\n✅ Weekly Sonnet Limit:")
        print(f"   Usage: {limits.weekly_sonnet.percent_used}%")
        print(f"   Resets: {limits.weekly_sonnet.reset_time}")

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
