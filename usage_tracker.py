#!/usr/bin/env python3
"""
Main usage tracker combining local JSONL data with overall limits.
"""

from claude_data_parser import ClaudeDataParser, UsageStats
from usage_limits_parser import UsageLimitsParser, UsageLimits
from datetime import datetime, timedelta
from typing import Dict


class ClaudeUsageTracker:
    """
    Complete Claude usage tracker.

    Combines:
    - Local JSONL data for detailed metrics
    - /usage command output for overall limits
    """

    def __init__(self):
        self.parser = ClaudeDataParser()
        self.limits_parser = UsageLimitsParser()

    def get_detailed_stats(self) -> UsageStats:
        """Get detailed usage statistics from local JSONL files."""
        return self.parser.get_usage_summary()

    def get_overall_limits(self) -> UsageLimits:
        """Get overall plan limits via OAuth API."""
        # v2.0.0: Now uses OAuth API automatically - no manual steps needed
        return self.limits_parser.get_current_limits()

    def get_last_n_days(self, stats: UsageStats, days: int = 7) -> Dict[str, dict]:
        """Get usage data for last N days."""
        if not stats.date_range[1]:
            return {}

        end_date = stats.date_range[1].date()
        result = {}

        for i in range(days - 1, -1, -1):
            date = end_date - timedelta(days=i)
            date_key = date.strftime("%Y-%m-%d")
            usage = stats.by_date.get(date_key)

            if usage:
                # Calculate cost for this day
                cost = 0.0
                for model, model_usage in stats.by_model.items():
                    # This is approximate - we'd need per-day per-model breakdown for accuracy
                    cost += self.parser.calculate_cost(model_usage, model) / len(stats.by_date)

                result[date_key] = {
                    "tokens": usage.total_tokens,
                    "cost": cost,
                    "usage": usage
                }
            else:
                result[date_key] = {
                    "tokens": 0,
                    "cost": 0.0,
                    "usage": None
                }

        return result

    def print_summary(self):
        """Print a summary of usage data."""
        print("=" * 70)
        print("Claude Usage Tracker Summary")
        print("=" * 70)

        # Get detailed stats
        print("\n📊 Fetching detailed usage data from local files...")
        stats = self.get_detailed_stats()

        if stats.message_count == 0:
            print("❌ No usage data found")
            return

        print(f"✅ Analyzed {stats.message_count:,} messages")
        if stats.date_range[0]:
            print(f"   From {stats.date_range[0].date()} to {stats.date_range[1].date()}")

        # Token usage
        print(f"\n📈 Total Token Usage:")
        print(f"   Input:          {stats.total_usage.input_tokens:>12,}")
        print(f"   Output:         {stats.total_usage.output_tokens:>12,}")
        print(f"   Cache creation: {stats.total_usage.cache_creation_tokens:>12,}")
        print(f"   Cache reads:    {stats.total_usage.cache_read_tokens:>12,}")
        print(f"   {'─' * 40}")
        print(f"   Total:          {stats.total_usage.total_tokens:>12,}")

        # Cache efficiency
        if stats.total_usage.cache_creation_tokens > 0:
            cache_ratio = (stats.total_usage.cache_read_tokens /
                          stats.total_usage.cache_creation_tokens)
            print(f"\n💾 Cache Efficiency:")
            print(f"   Cache hit ratio: {cache_ratio:.1f}x")
            print(f"   (Reading {cache_ratio:.1f} tokens for every 1 token created)")

        # Cost breakdown
        print(f"\n💰 Cost Breakdown by Model:")
        total_cost = 0.0
        for model, usage in sorted(stats.by_model.items(),
                                   key=lambda x: x[1].total_tokens,
                                   reverse=True):
            cost = self.parser.calculate_cost(usage, model)
            total_cost += cost
            pct = (usage.total_tokens / stats.total_usage.total_tokens) * 100
            print(f"   {model:40s} ${cost:>8.2f} ({pct:>5.1f}%)")

        print(f"   {'─' * 60}")
        print(f"   {'TOTAL':40s} ${total_cost:>8.2f}")

        # Project breakdown
        print(f"\n📁 Usage by Project:")
        for project, usage in sorted(stats.by_project.items(),
                                     key=lambda x: x[1].total_tokens,
                                     reverse=True):
            pct = (usage.total_tokens / stats.total_usage.total_tokens) * 100
            print(f"   {project:40s} {usage.total_tokens:>12,} ({pct:>5.1f}%)")

        # Last 7 days
        print(f"\n📅 Last 7 Days:")
        last_week = self.get_last_n_days(stats, 7)
        for date_key, data in last_week.items():
            if data["tokens"] > 0:
                print(f"   {date_key}: {data['tokens']:>12,} tokens (~${data['cost']:.2f})")
            else:
                print(f"   {date_key}: {'No activity':>12}")

        # Overall limits from OAuth API
        print(f"\n" + "=" * 70)
        print("📊 Overall Plan Limits (via OAuth API)")
        print("=" * 70)

        limits = self.get_overall_limits()

        if limits.session:
            print(f"\n⏱️  Current Session (5-hour window):")
            print(f"   Usage: {limits.session.percent_used}%")
            print(f"   Resets: {limits.session.reset_time} ({limits.session.reset_timezone})")

        if limits.extra:
            print(f"\n💳 Extra Usage:")
            print(f"   Usage: {limits.extra.percent_used}%")
            print(f"   Spent: ${limits.extra.amount_spent:.2f} / ${limits.extra.amount_limit:.2f}")
            print(f"   Resets: {limits.extra.reset_date}")

        if not limits.session and not limits.extra:
            print("\n⚠️  Could not fetch usage limits")
            print("   Make sure you're logged in to Claude Code")


def main():
    """Run the usage tracker."""
    tracker = ClaudeUsageTracker()
    tracker.print_summary()


if __name__ == "__main__":
    main()
