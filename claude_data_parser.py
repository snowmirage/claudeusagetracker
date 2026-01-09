#!/usr/bin/env python3
"""
Parse Claude Code local JSONL files to extract usage data.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class TokenUsage:
    """Token usage for a single message."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens."""
        return (self.input_tokens + self.output_tokens +
                self.cache_creation_tokens + self.cache_read_tokens)

    def __add__(self, other):
        """Add two TokenUsage objects."""
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens
        )


@dataclass
class MessageData:
    """Data from a single Claude message."""
    timestamp: datetime
    model: str
    usage: TokenUsage
    project: str
    request_id: str
    conversation_id: str


@dataclass
class UsageStats:
    """Aggregated usage statistics."""
    total_usage: TokenUsage = field(default_factory=TokenUsage)
    by_model: Dict[str, TokenUsage] = field(default_factory=lambda: defaultdict(TokenUsage))
    by_date: Dict[str, TokenUsage] = field(default_factory=lambda: defaultdict(TokenUsage))
    by_project: Dict[str, TokenUsage] = field(default_factory=lambda: defaultdict(TokenUsage))
    message_count: int = 0
    date_range: tuple = field(default_factory=lambda: (None, None))


class ClaudeDataParser:
    """Parse Claude Code JSONL files and extract usage data."""

    # Official Anthropic pricing (as of Jan 2026)
    # Source: https://www.anthropic.com/pricing
    PRICING = {
        "claude-sonnet-4-5": {
            "input": 3.00 / 1_000_000,      # $3 per MTok
            "output": 15.00 / 1_000_000,    # $15 per MTok
            "cache_write": 3.75 / 1_000_000, # $3.75 per MTok
            "cache_read": 0.30 / 1_000_000   # $0.30 per MTok
        },
        "claude-opus-4-5": {
            "input": 15.00 / 1_000_000,     # $15 per MTok
            "output": 75.00 / 1_000_000,    # $75 per MTok
            "cache_write": 18.75 / 1_000_000, # $18.75 per MTok
            "cache_read": 1.50 / 1_000_000   # $1.50 per MTok
        },
        "claude-3-5-haiku": {
            "input": 1.00 / 1_000_000,      # $1 per MTok
            "output": 5.00 / 1_000_000,     # $5 per MTok
            "cache_write": 1.25 / 1_000_000, # $1.25 per MTok
            "cache_read": 0.10 / 1_000_000   # $0.10 per MTok
        }
    }

    def __init__(self, claude_dir: Optional[Path] = None):
        """
        Initialize parser.

        Args:
            claude_dir: Path to .claude directory (default: ~/.claude)
        """
        self.claude_dir = claude_dir or Path.home() / ".claude"
        self.projects_dir = self.claude_dir / "projects"

    def get_model_pricing(self, model_name: str) -> Optional[Dict[str, float]]:
        """Get pricing for a model."""
        # Normalize model name to match pricing keys
        if "sonnet-4" in model_name.lower():
            return self.PRICING["claude-sonnet-4-5"]
        elif "opus-4" in model_name.lower():
            return self.PRICING["claude-opus-4-5"]
        elif "haiku" in model_name.lower():
            return self.PRICING["claude-3-5-haiku"]
        else:
            # Default to Sonnet pricing for unknown models
            return self.PRICING["claude-sonnet-4-5"]

    def calculate_cost(self, usage: TokenUsage, model: str) -> float:
        """Calculate cost in USD for token usage."""
        pricing = self.get_model_pricing(model)
        if not pricing:
            return 0.0

        cost = (
            usage.input_tokens * pricing["input"] +
            usage.output_tokens * pricing["output"] +
            usage.cache_creation_tokens * pricing["cache_write"] +
            usage.cache_read_tokens * pricing["cache_read"]
        )
        return cost

    def parse_message(self, line: str, project: str, conversation_id: str) -> Optional[MessageData]:
        """Parse a single JSONL line."""
        try:
            data = json.loads(line)

            # Only process assistant messages with usage data
            if data.get("type") != "assistant" or "usage" not in data.get("message", {}):
                return None

            message = data["message"]
            usage_data = message["usage"]

            # Extract token counts
            usage = TokenUsage(
                input_tokens=usage_data.get("input_tokens", 0),
                output_tokens=usage_data.get("output_tokens", 0),
                cache_creation_tokens=usage_data.get("cache_creation_input_tokens", 0),
                cache_read_tokens=usage_data.get("cache_read_input_tokens", 0)
            )

            # Parse timestamp
            timestamp = datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

            return MessageData(
                timestamp=timestamp,
                model=message["model"],
                usage=usage,
                project=project,
                request_id=data.get("requestId", ""),
                conversation_id=conversation_id
            )

        except (json.JSONDecodeError, KeyError) as e:
            # Skip malformed lines
            return None

    def parse_conversation(self, jsonl_file: Path, project: str) -> List[MessageData]:
        """Parse a single conversation JSONL file."""
        messages = []
        conversation_id = jsonl_file.stem

        try:
            with open(jsonl_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue

                    msg = self.parse_message(line, project, conversation_id)
                    if msg:
                        messages.append(msg)
        except Exception as e:
            print(f"Error parsing {jsonl_file}: {e}")

        return messages

    def parse_all_projects(self) -> List[MessageData]:
        """Parse all projects and return all messages."""
        all_messages = []

        if not self.projects_dir.exists():
            print(f"Projects directory not found: {self.projects_dir}")
            return all_messages

        # Iterate through all project directories
        for project_dir in self.projects_dir.iterdir():
            if not project_dir.is_dir():
                continue

            project_name = project_dir.name

            # Find all JSONL files in project
            for jsonl_file in project_dir.glob("*.jsonl"):
                messages = self.parse_conversation(jsonl_file, project_name)
                all_messages.extend(messages)

        return all_messages

    def aggregate_stats(self, messages: List[MessageData]) -> UsageStats:
        """Aggregate messages into statistics."""
        stats = UsageStats()

        if not messages:
            return stats

        # Sort by timestamp
        messages.sort(key=lambda m: m.timestamp)

        # Track date range
        stats.date_range = (messages[0].timestamp, messages[-1].timestamp)
        stats.message_count = len(messages)

        # Aggregate usage
        for msg in messages:
            # Total usage
            stats.total_usage += msg.usage

            # By model
            stats.by_model[msg.model] += msg.usage

            # By date
            date_key = msg.timestamp.strftime("%Y-%m-%d")
            stats.by_date[date_key] += msg.usage

            # By project
            stats.by_project[msg.project] += msg.usage

        return stats

    def get_usage_summary(self) -> UsageStats:
        """Get complete usage summary from all projects."""
        messages = self.parse_all_projects()
        return self.aggregate_stats(messages)


def main():
    """Test the parser."""
    print("=" * 60)
    print("Claude Data Parser Test")
    print("=" * 60)

    parser = ClaudeDataParser()

    print("\n📊 Parsing all projects...")
    stats = parser.get_usage_summary()

    print(f"\n✅ Parsed {stats.message_count} messages")

    if stats.date_range[0]:
        print(f"   Date range: {stats.date_range[0].date()} to {stats.date_range[1].date()}")

    print(f"\n📈 Total Token Usage:")
    print(f"   Input tokens:          {stats.total_usage.input_tokens:,}")
    print(f"   Output tokens:         {stats.total_usage.output_tokens:,}")
    print(f"   Cache creation tokens: {stats.total_usage.cache_creation_tokens:,}")
    print(f"   Cache read tokens:     {stats.total_usage.cache_read_tokens:,}")
    print(f"   Total tokens:          {stats.total_usage.total_tokens:,}")

    print(f"\n💰 Cost Breakdown by Model:")
    total_cost = 0.0
    for model, usage in stats.by_model.items():
        cost = parser.calculate_cost(usage, model)
        total_cost += cost
        print(f"   {model}: ${cost:.4f}")

    print(f"\n   💵 TOTAL COST: ${total_cost:.2f}")

    print(f"\n📁 Usage by Project:")
    for project, usage in sorted(stats.by_project.items(),
                                   key=lambda x: x[1].total_tokens,
                                   reverse=True):
        print(f"   {project}: {usage.total_tokens:,} tokens")

    print(f"\n📅 Last 7 Days:")
    # Get last 7 days of data
    from datetime import timedelta
    if stats.date_range[1]:
        end_date = stats.date_range[1].date()
        for i in range(6, -1, -1):
            date = end_date - timedelta(days=i)
            date_key = date.strftime("%Y-%m-%d")
            usage = stats.by_date.get(date_key, TokenUsage())
            if usage.total_tokens > 0:
                cost = sum(parser.calculate_cost(stats.by_model[m], m)
                          for m in stats.by_model.keys())
                print(f"   {date_key}: {usage.total_tokens:,} tokens")


if __name__ == "__main__":
    main()
