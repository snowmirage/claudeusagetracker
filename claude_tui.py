#!/usr/bin/env python3
"""
Claude Usage Tracker - btop-style Terminal UI
"""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, Static, ProgressBar, Label
from textual.reactive import reactive
from rich.text import Text
from rich.panel import Panel
from rich.table import Table
from datetime import datetime, timedelta
from pathlib import Path
import json
import math
import argparse
import sys

from usage_tracker import ClaudeUsageTracker
from claude_data_parser import TokenUsage
from version import __version__, __title__, __description__


class SessionLimits(Static):
    """Display session limits like /usage command."""

    # Default limits (will be overridden by plan detection)
    DEFAULT_SESSION_TOKEN_LIMIT = 44000  # Pro plan default
    DEFAULT_EXTRA_USAGE_LIMIT = 50.00    # Pro plan default

    # Daemon data directory
    DAEMON_DATA_DIR = Path.home() / ".claudeusagetracker"
    RAW_LOG_FILE = DAEMON_DATA_DIR / "raw_usage_log.jsonl"

    def __init__(self):
        super().__init__()
        self.tracker = ClaudeUsageTracker()
        self.limits_parser = self.tracker.limits_parser
        # Cache the limits
        self.cached_limits = None
        self.last_fetch_time = None
        # Plan-specific limits (detected from data)
        self.session_token_limit = self.DEFAULT_SESSION_TOKEN_LIMIT
        self.plan_name = "Claude"

    def on_mount(self) -> None:
        """Set up auto-refresh."""
        # Refresh immediately on first load
        self.refresh_data()
        # Then refresh every 15 seconds
        self.set_interval(15, self.refresh_data)

    def _load_latest_daemon_data(self):
        """Load the latest usage data from daemon's raw log file.

        Returns tuple of (limits_dict, timestamp) or (None, None) if unavailable
        """
        try:
            if self.RAW_LOG_FILE.exists():
                # Read the last line of the JSONL file
                with open(self.RAW_LOG_FILE, 'r') as f:
                    lines = f.readlines()
                    if lines:
                        last_line = lines[-1].strip()
                        data = json.loads(last_line)
                        return data, data.get('timestamp')
        except Exception as e:
            pass
        return None, None

    def refresh_data(self) -> None:
        """Refresh session limits from daemon data."""
        from rich.table import Table as RichTable
        from rich.console import Group

        # Try to load from daemon's stored data first
        daemon_data, timestamp = self._load_latest_daemon_data()

        if daemon_data and daemon_data.get('session') and daemon_data.get('extra'):
            # Use daemon's cached data
            session_data = daemon_data['session']
            extra_data = daemon_data['extra']
            plan_data = daemon_data.get('plan')  # May be None for older daemon data
            weekly_data = daemon_data.get('weekly')
            weekly_opus_data = daemon_data.get('weekly_opus')
            weekly_sonnet_data = daemon_data.get('weekly_sonnet')

            # Detect plan and set limits
            if plan_data:
                self.plan_name = plan_data.get('display_name', 'Claude')
                self.session_token_limit = plan_data.get('session_token_limit', self.DEFAULT_SESSION_TOKEN_LIMIT)
            else:
                self.plan_name = "Claude"
                self.session_token_limit = self.DEFAULT_SESSION_TOKEN_LIMIT

            # Parse timestamp
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(timestamp)
                time_str = dt.strftime("%Y-%m-%d %I:%M:%S %p")
            except:
                time_str = "Unknown"

            output = []

            # Current Session with timestamp on same line
            first_line_table = RichTable.grid(expand=True)
            first_line_table.add_column(justify="left")
            first_line_table.add_column(justify="right")
            first_line_table.add_row("[bold cyan]Current session (5-hour)[/bold cyan]", f"[dim]Last Updated: {time_str}[/dim]")
            output.append(first_line_table)

            bar_len = 40
            session_pct = session_data['percent_used']
            filled = min(int((session_pct / 100) * bar_len), bar_len)  # Cap at 100%
            bar = "█" * filled + "░" * (bar_len - filled)

            # Calculate token counts
            session_used = int((session_pct / 100) * self.session_token_limit)

            output.append(f"[cyan]{bar}[/cyan] {session_pct:.0f}% used")
            output.append(f"[dim]{session_used:,} / {self.session_token_limit:,} tokens (estimated)[/dim]")
            output.append(f"[dim]Resets {session_data['reset_time']} ({session_data['reset_timezone']})[/dim]")

            # Weekly limits (Max plans only)
            if weekly_data:
                output.append("")
                output.append("[bold magenta]Weekly limit (overall)[/bold magenta]")

                weekly_pct = weekly_data['percent_used']
                filled = min(int((weekly_pct / 100) * bar_len), bar_len)  # Cap at 100%
                bar = "█" * filled + "░" * (bar_len - filled)

                output.append(f"[magenta]{bar}[/magenta] {weekly_pct:.0f}% used")
                output.append(f"[dim]Resets {weekly_data['reset_time']}[/dim]")

            if weekly_sonnet_data:
                output.append("")
                output.append("[bold blue]Weekly Sonnet limit[/bold blue]")

                weekly_pct = weekly_sonnet_data['percent_used']
                filled = min(int((weekly_pct / 100) * bar_len), bar_len)  # Cap at 100%
                bar = "█" * filled + "░" * (bar_len - filled)

                output.append(f"[blue]{bar}[/blue] {weekly_pct:.0f}% used")
                output.append(f"[dim]Resets {weekly_sonnet_data['reset_time']}[/dim]")

            if weekly_opus_data:
                output.append("")
                output.append("[bold green]Weekly Opus limit[/bold green]")

                weekly_pct = weekly_opus_data['percent_used']
                filled = min(int((weekly_pct / 100) * bar_len), bar_len)  # Cap at 100%
                bar = "█" * filled + "░" * (bar_len - filled)

                output.append(f"[green]{bar}[/green] {weekly_pct:.0f}% used")
                output.append(f"[dim]Resets {weekly_opus_data['reset_time']}[/dim]")

            output.append("")

            # Extra Usage
            output.append("[bold yellow]Extra usage[/bold yellow]")

            bar_len = 40
            extra_pct = extra_data['percent_used']
            filled = min(int((extra_pct / 100) * bar_len), bar_len)  # Cap at 100%
            bar = "█" * filled + "░" * (bar_len - filled)

            output.append(f"[yellow]{bar}[/yellow] {extra_pct:.0f}% used")
            output.append(f"[dim]${extra_data['amount_spent']:.2f} / ${extra_data['amount_limit']:.2f} spent[/dim]")
            output.append(f"[dim]Resets {extra_data['reset_date']} ({extra_data['reset_timezone']})[/dim]")

            # Create content group (first item is table, rest are strings)
            content = Group(*output)

            panel = Panel(
                content,
                title=f"[bold white]{self.plan_name}",
                border_style="white"
            )
        else:
            # No daemon data available
            output = []
            output.append("[bold cyan]Current session[/bold cyan]")
            output.append("[dim]⚠️  No daemon data available[/dim]")
            output.append("[dim]   Start daemon: systemctl --user start claude-usage-daemon[/dim]")
            output.append("")
            output.append("[bold yellow]Extra usage[/bold yellow]")
            output.append("[dim]⚠️  No daemon data available[/dim]")

            panel = Panel(
                "\n".join(output),
                title="[bold white]Session Limits (from daemon)",
                border_style="red"
            )

        self.update(panel)


class TokenBreakdown(Static):
    """Display token usage breakdown."""

    def __init__(self):
        super().__init__()
        self.tracker = ClaudeUsageTracker()

    def on_mount(self) -> None:
        """Set up auto-refresh."""
        # Refresh immediately on first load
        self.refresh_data()
        # Then refresh every 15 seconds
        self.set_interval(15, self.refresh_data)

    def refresh_data(self) -> None:
        """Refresh token data."""
        stats = self.tracker.get_detailed_stats()

        if stats.message_count == 0:
            self.update("No data")
            return

        table = Table.grid(padding=(0, 1))
        table.add_column(style="yellow", width=18)
        table.add_column(style="white", justify="right")

        table.add_row("Input:", f"{stats.total_usage.input_tokens:,}")
        table.add_row("Output:", f"{stats.total_usage.output_tokens:,}")
        table.add_row("Cache Creation:", f"{stats.total_usage.cache_creation_tokens:,}")
        table.add_row("Cache Reads:", f"{stats.total_usage.cache_read_tokens:,}")

        panel = Panel(
            table,
            title="[bold yellow]Token Breakdown",
            border_style="yellow"
        )

        self.update(panel)


class DailyUsageChart(Static):
    """Display daily usage as a bar chart with token type breakdown."""

    # Pro plan session limit
    SESSION_TOKEN_LIMIT = 44000
    # Daemon data directory
    DAEMON_DATA_DIR = Path.home() / ".claudeusagetracker"
    DAILY_SUMMARY_FILE = DAEMON_DATA_DIR / "daily_summary.json"

    # API Pricing (Sonnet 4.5) - for reference display
    PRICING = {
        "input": 3.00 / 1_000_000,
        "output": 15.00 / 1_000_000,
        "cache_creation": 3.75 / 1_000_000,
        "cache_read": 0.30 / 1_000_000
    }

    def __init__(self):
        super().__init__()
        self.tracker = ClaudeUsageTracker()
        self.limits_parser = self.tracker.limits_parser
        self.history_offset = 0  # For scrolling through history

    def on_mount(self) -> None:
        """Set up auto-refresh."""
        # Refresh immediately on first load
        self.refresh_data()
        # Then refresh every 15 seconds
        self.set_interval(15, self.refresh_data)

    def _get_token_breakdown_by_type(self, stats, dates):
        """Get detailed token breakdown by type for each date.

        Returns dict like:
        {
            '2026-01-10': {
                'input_tokens': X,
                'output_tokens': Y,
                'cache_creation_tokens': Z,
                'cache_read_tokens': W,
                'total_tokens': X+Y+Z+W
            }
        }
        """
        breakdown = {}
        for date in dates:
            if date in stats.by_date:
                usage = stats.by_date[date]
                breakdown[date] = {
                    'input_tokens': usage.input_tokens,
                    'output_tokens': usage.output_tokens,
                    'cache_creation_tokens': usage.cache_creation_tokens,
                    'cache_read_tokens': usage.cache_read_tokens,
                    'total_tokens': usage.total_tokens
                }
            else:
                breakdown[date] = {
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'cache_creation_tokens': 0,
                    'cache_read_tokens': 0,
                    'total_tokens': 0
                }
        return breakdown

    def _load_daemon_data(self):
        """Load daily summary from daemon's data file.

        Returns dict with date keys and values like:
        {'session_tokens': X, 'extra_tokens': Y, 'total_tokens': Z}
        """
        try:
            if self.DAILY_SUMMARY_FILE.exists():
                with open(self.DAILY_SUMMARY_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            # Fallback to empty dict if daemon data unavailable
            pass
        return {}

    def _calculate_session_extra_breakdown(self, last_days, limits):
        """Calculate session vs extra usage for each day.

        Returns dict with date keys and values like:
        {'session_tokens': X, 'extra_tokens': Y}
        """
        # First, try to load from daemon data
        daemon_data = self._load_daemon_data()

        breakdown = {}

        for date_key, data in last_days.items():
            total_tokens = data["tokens"]

            # Check if we have daemon data for this date
            if date_key in daemon_data:
                # Use daemon's accurate breakdown
                breakdown[date_key] = {
                    'session_tokens': daemon_data[date_key].get('session_tokens', 0),
                    'extra_tokens': daemon_data[date_key].get('extra_tokens', 0)
                }
            else:
                # Fallback to simple approximation for dates before daemon started
                if total_tokens <= self.SESSION_TOKEN_LIMIT:
                    breakdown[date_key] = {
                        'session_tokens': total_tokens,
                        'extra_tokens': 0
                    }
                else:
                    breakdown[date_key] = {
                        'session_tokens': self.SESSION_TOKEN_LIMIT,
                        'extra_tokens': total_tokens - self.SESSION_TOKEN_LIMIT
                    }

        return breakdown

    def refresh_data(self) -> None:
        """Refresh daily usage chart with token type breakdown."""
        stats = self.tracker.get_detailed_stats()

        if stats.message_count == 0:
            self.update("No data")
            return

        # Get last 7 days
        last_days = self.tracker.get_last_n_days(stats, 7)

        if not last_days:
            self.update("No data")
            return

        # Get data in order (oldest to newest)
        dates = list(last_days.keys())

        # Get token breakdown by type for each day
        token_breakdown = self._get_token_breakdown_by_type(stats, dates)

        # Build chart - height will vary per bar based on actual token counts
        box_width = 13   # Wider to fit totals: 13×7=91 chars
        MIN_BAR_HEIGHT = 3   # Minimum height for smallest bar
        MAX_BAR_HEIGHT = 30  # Cap to fit on screen

        lines = []

        # Find min and max total tokens to determine scale factor
        min_total_tokens = float('inf')
        max_total_tokens = 0
        for date_key in dates:
            total = token_breakdown[date_key]['total_tokens']
            if total > 0:
                min_total_tokens = min(min_total_tokens, total)
                max_total_tokens = max(max_total_tokens, total)

        # Scale so minimum bar = MIN_BAR_HEIGHT chars
        if min_total_tokens != float('inf') and min_total_tokens > 0:
            scale_factor = MIN_BAR_HEIGHT / min_total_tokens

            # Check if this would make max bar too tall
            max_bar_with_scale = max_total_tokens * scale_factor
            if max_bar_with_scale > MAX_BAR_HEIGHT:
                # Rescale to fit within screen
                scale_factor = MAX_BAR_HEIGHT / max_total_tokens

            max_bar_height = int(max_total_tokens * scale_factor) + 1
        else:
            scale_factor = 1
            max_bar_height = MAX_BAR_HEIGHT

        # Legend at top
        lines.append("[bold cyan]Legend:[/bold cyan] [bright_blue]█[/bright_blue]=Input  [bright_green]█[/bright_green]=Output  [yellow]█[/yellow]=Cache Create  [bright_magenta]█[/bright_magenta]=Cache Read")
        lines.append(f"[dim italic]Bar heights proportional to total tokens • Sections sized proportionally • Prices = API rates (Sonnet 4.5)[/dim italic]")
        lines.append("")

        # Top borders
        top_row = "┌" + ("─" * box_width) + "┐"
        lines.append(" ".join([top_row] * 7))

        # Dates (centered)
        date_row_parts = []
        for date_key in dates:
            date_short = date_key[-5:]  # MM-DD
            centered_date = date_short.center(box_width)
            date_row_parts.append(f"│{centered_date}│")
        lines.append(" ".join(date_row_parts))

        # Vertical stacked bars with labels
        for row in range(max_bar_height, 0, -1):
            bar_row_parts = []

            for date_key in dates:
                tokens = token_breakdown[date_key]
                total = tokens['total_tokens']

                if total == 0:
                    bar_row_parts.append(f"│{' ' * box_width}│")
                    continue

                # Calculate total bar height based on total tokens (linear scale)
                total_bar_height = total * scale_factor

                # Use LOG scale for proportions WITHIN the bar so all sections are visible
                # Token order (bottom to top, smallest to largest typically):
                # 1. Input (blue) - smallest, ~10-80K
                # 2. Output (green) - small, ~6-116K
                # 3. Cache creation (yellow) - medium, ~274K-7M
                # 4. Cache read (magenta) - largest, ~3.8M-77M
                log_input = math.log10(tokens['input_tokens'] + 1)
                log_output = math.log10(tokens['output_tokens'] + 1)
                log_cache_create = math.log10(tokens['cache_creation_tokens'] + 1)
                log_cache_read = math.log10(tokens['cache_read_tokens'] + 1)
                log_total = log_input + log_output + log_cache_create + log_cache_read

                if log_total > 0:
                    # Divide the bar height proportionally based on log of token counts
                    # But ensure minimum 1 char height for each non-zero token type
                    MIN_SECTION = 1.0

                    input_section = max(MIN_SECTION if tokens['input_tokens'] > 0 else 0, (log_input / log_total) * total_bar_height)
                    output_section = max(MIN_SECTION if tokens['output_tokens'] > 0 else 0, (log_output / log_total) * total_bar_height)
                    cache_create_section = max(MIN_SECTION if tokens['cache_creation_tokens'] > 0 else 0, (log_cache_create / log_total) * total_bar_height)
                    cache_read_section = max(MIN_SECTION if tokens['cache_read_tokens'] > 0 else 0, (log_cache_read / log_total) * total_bar_height)

                    # Stack them
                    input_height = input_section
                    output_height = input_height + output_section
                    cache_create_height = output_height + cache_create_section
                    cache_read_height = cache_create_height + cache_read_section
                else:
                    input_height = output_height = cache_create_height = cache_read_height = 0

                # Determine which section this row belongs to
                content = ""
                if row <= input_height:
                    # Input tokens (bright blue background, black text)
                    tokens_k = int(tokens['input_tokens'] / 1000)
                    cost = tokens['input_tokens'] * self.PRICING['input']
                    if tokens_k > 0 and row == int(input_height / 2) + 1:
                        # Show label in middle of this section
                        label = f"{tokens_k:,}K/${cost:.2f}"
                        if len(label) <= box_width:
                            content = f"[black on bright_blue]{label.center(box_width)}[/]"
                        else:
                            content = f"[black on bright_blue]{' ' * box_width}[/]"
                    else:
                        content = f"[black on bright_blue]{' ' * box_width}[/]"
                elif row <= output_height:
                    # Output tokens (bright green background, black text)
                    tokens_k = int(tokens['output_tokens'] / 1000)
                    cost = tokens['output_tokens'] * self.PRICING['output']
                    section_middle = int((input_height + output_height) / 2) + 1
                    if tokens_k > 0 and row == section_middle:
                        label = f"{tokens_k:,}K/${cost:.2f}"
                        if len(label) <= box_width:
                            content = f"[black on bright_green]{label.center(box_width)}[/]"
                        else:
                            content = f"[black on bright_green]{' ' * box_width}[/]"
                    else:
                        content = f"[black on bright_green]{' ' * box_width}[/]"
                elif row <= cache_create_height:
                    # Cache creation tokens (yellow background, black text)
                    tokens_k = int(tokens['cache_creation_tokens'] / 1000)
                    cost = tokens['cache_creation_tokens'] * self.PRICING['cache_creation']
                    section_middle = int((output_height + cache_create_height) / 2) + 1
                    if tokens_k > 0 and row == section_middle:
                        label = f"{tokens_k:,}K/${cost:.2f}"
                        if len(label) <= box_width:
                            content = f"[black on yellow]{label.center(box_width)}[/]"
                        else:
                            content = f"[black on yellow]{' ' * box_width}[/]"
                    else:
                        content = f"[black on yellow]{' ' * box_width}[/]"
                elif row <= cache_read_height:
                    # Cache read tokens (bright magenta background, black text)
                    tokens_k = int(tokens['cache_read_tokens'] / 1000)
                    cost = tokens['cache_read_tokens'] * self.PRICING['cache_read']
                    section_middle = int((cache_create_height + cache_read_height) / 2) + 1
                    if tokens_k > 0 and row == section_middle:
                        label = f"{tokens_k:,}K/${cost:.2f}"
                        if len(label) <= box_width:
                            content = f"[black on bright_magenta]{label.center(box_width)}[/]"
                        else:
                            content = f"[black on bright_magenta]{' ' * box_width}[/]"
                    else:
                        content = f"[black on bright_magenta]{' ' * box_width}[/]"
                else:
                    # Empty space above bars
                    content = " " * box_width

                bar_row_parts.append(f"│{content}│")

            lines.append(" ".join(bar_row_parts))

        # Total tokens at bottom
        count_row_parts = []
        for date_key in dates:
            total = token_breakdown[date_key]['total_tokens']
            if total > 0:
                total_cost = (
                    token_breakdown[date_key]['input_tokens'] * self.PRICING['input'] +
                    token_breakdown[date_key]['output_tokens'] * self.PRICING['output'] +
                    token_breakdown[date_key]['cache_creation_tokens'] * self.PRICING['cache_creation'] +
                    token_breakdown[date_key]['cache_read_tokens'] * self.PRICING['cache_read']
                )
                label = f"{int(total/1000):,}K/${total_cost:.2f}"
                count_row_parts.append(f"│[bold]{label.center(box_width)}[/bold]│")
            else:
                count_row_parts.append(f"│[dim]{'No data'.center(box_width)}[/dim]│")
        lines.append(" ".join(count_row_parts))

        # Bottom borders
        bottom_row = "└" + ("─" * box_width) + "┘"
        lines.append(" ".join([bottom_row] * 7))

        panel = Panel(
            "\n".join(lines),
            title="[bold green]Daily Usage by Token Type",
            border_style="green"
        )

        self.update(panel)


class DailyUsageChartDots(Static):
    """Display daily usage as dot-matrix style bars (btop-inspired)."""

    # API Pricing (Sonnet 4.5) - for reference display
    PRICING = {
        "input": 3.00 / 1_000_000,
        "output": 15.00 / 1_000_000,
        "cache_creation": 3.75 / 1_000_000,
        "cache_read": 0.30 / 1_000_000
    }

    # Token-based scale
    TOKENS_PER_SUBDOT = 10_000  # 10K tokens per subdot (1/8 of full character)
    TOKENS_PER_FULL_DOT = 80_000  # 80K tokens per full Braille character (⣿ = 8 subdots)

    # Cost-based scale
    COST_PER_SUBDOT = 0.01  # $0.01 per subdot
    COST_PER_FULL_DOT = 0.08  # $0.08 per full Braille character (⣿ = 8 subdots)

    # Braille patterns for partial dots (0/8 to 8/8 filled)
    BRAILLE_PATTERNS = [
        " ",   # 0/8 - empty
        "⠁",   # 1/8
        "⠉",   # 2/8
        "⠋",   # 3/8
        "⠛",   # 4/8
        "⠟",   # 5/8
        "⠿",   # 6/8
        "⣟",   # 7/8
        "⣿"    # 8/8 - full
    ]

    def __init__(self):
        super().__init__()
        self.tracker = ClaudeUsageTracker()
        self.display_mode = 'tokens'  # 'tokens' or 'cost'
        self.last_refresh = None
        self.days_visible = 2  # Default to 2 days
        self.days_offset = 0  # How many days back we've scrolled

    def on_mount(self) -> None:
        """Set up auto-refresh."""
        self.refresh_data()
        self.set_interval(15, self.refresh_data)

    def toggle_display_mode(self) -> None:
        """Toggle between token and cost display modes."""
        self.display_mode = 'cost' if self.display_mode == 'tokens' else 'tokens'
        self.refresh_data()

    def scroll_days_forward(self) -> None:
        """Scroll to show older dates."""
        self.days_offset += 1
        self.refresh_data()

    def scroll_days_backward(self) -> None:
        """Scroll to show newer dates."""
        if self.days_offset > 0:
            self.days_offset -= 1
            self.refresh_data()

    def increase_visible_days(self) -> None:
        """Increase number of visible days (max 5)."""
        if self.days_visible < 5:
            self.days_visible += 1
            self.refresh_data()

    def decrease_visible_days(self) -> None:
        """Decrease number of visible days (min 1)."""
        if self.days_visible > 1:
            self.days_visible -= 1
            self.refresh_data()

    def _render_bar(self, tokens: int, cost: float, color: str, max_width: int = 60) -> str:
        """Render a horizontal bar using Braille characters with wrapping.

        Args:
            tokens: Number of tokens
            cost: Cost in dollars
            color: Rich color name (e.g., 'bright_blue')
            max_width: Maximum characters per line before wrapping

        Returns:
            Formatted bar string with color (may include newlines for wrapping)
        """
        # Choose value based on display mode
        if self.display_mode == 'tokens':
            value = tokens
            per_subdot = self.TOKENS_PER_SUBDOT
            per_full_dot = self.TOKENS_PER_FULL_DOT
        else:  # cost mode
            value = cost
            per_subdot = self.COST_PER_SUBDOT
            per_full_dot = self.COST_PER_FULL_DOT

        if value == 0:
            return ""

        # Always show at least 1 subdot for any non-zero amount
        if value < per_subdot:
            return f"[{color}]{self.BRAILLE_PATTERNS[1]}[/{color}]"

        # Calculate number of full characters and partial
        full_chars = int(value / per_full_dot)
        remaining_value = value % per_full_dot
        partial_index = int((remaining_value / per_subdot))

        # Build the bar
        bar = self.BRAILLE_PATTERNS[8] * full_chars

        # Add partial character if we have remaining value
        if remaining_value > 0:
            if partial_index == 0:
                partial_index = 1
            bar += self.BRAILLE_PATTERNS[partial_index]

        # Wrap if needed
        if len(bar) > max_width:
            wrapped_lines = []
            for i in range(0, len(bar), max_width):
                wrapped_lines.append(f"[{color}]{bar[i:i+max_width]}[/{color}]")
            return "\n               ".join(wrapped_lines)  # 15 spaces to align with label
        else:
            return f"[{color}]{bar}[/{color}]"

    def _render_merged_bar(self, token_breakdown: dict, cost_breakdown: dict, max_width: int = 100) -> str:
        """Render a single merged bar with all token types flowing together.

        Args:
            token_breakdown: Dict with 'input_tokens', 'output_tokens', etc.
            cost_breakdown: Dict with 'input_cost', 'output_cost', etc.
            max_width: Maximum width per line before wrapping

        Returns:
            Merged bar with color transitions
        """
        # Render each section without wrapping first
        input_bar = self._render_bar(
            token_breakdown['input_tokens'],
            cost_breakdown['input_cost'],
            'bright_blue',
            max_width=999999
        )
        output_bar = self._render_bar(
            token_breakdown['output_tokens'],
            cost_breakdown['output_cost'],
            'bright_green',
            max_width=999999
        )
        cache_create_bar = self._render_bar(
            token_breakdown['cache_creation_tokens'],
            cost_breakdown['cache_create_cost'],
            'yellow',
            max_width=999999
        )
        cache_read_bar = self._render_bar(
            token_breakdown['cache_read_tokens'],
            cost_breakdown['cache_read_cost'],
            'bright_magenta',
            max_width=999999
        )

        # Combine all bars
        merged = input_bar + output_bar + cache_create_bar + cache_read_bar

        # Now wrap the merged bar
        if not merged:
            return ""

        # Strip color tags to count actual characters
        import re
        plain_merged = re.sub(r'\[/?[^\]]+\]', '', merged)

        if len(plain_merged) <= max_width:
            return merged
        else:
            # Need to wrap - this is complex with color tags, so we'll keep it simple
            # and just return the merged bar (Textual will handle wrapping)
            return merged

    def refresh_data(self) -> None:
        """Refresh daily usage chart with horizontal dot-matrix bars."""
        from datetime import datetime
        self.last_refresh = datetime.now()

        stats = self.tracker.get_detailed_stats()

        if stats.message_count == 0:
            self.update("No data")
            return

        # Get enough days to support scrolling (get 30 days total)
        all_days = self.tracker.get_last_n_days(stats, 30)

        if not all_days:
            self.update("No data")
            return

        # Get data in reverse order (newest to oldest)
        all_dates = list(reversed(list(all_days.keys())))

        # Apply offset and limit based on days_visible
        start_idx = self.days_offset
        end_idx = start_idx + self.days_visible
        dates = all_dates[start_idx:end_idx]

        # Create last_days dict with only the visible dates
        last_days = {date: all_days[date] for date in dates if date in all_days}

        # Get token breakdown by type for each day
        token_breakdown = {}
        for date in dates:
            if date in stats.by_date:
                usage = stats.by_date[date]
                token_breakdown[date] = {
                    'input_tokens': usage.input_tokens,
                    'output_tokens': usage.output_tokens,
                    'cache_creation_tokens': usage.cache_creation_tokens,
                    'cache_read_tokens': usage.cache_read_tokens,
                    'total_tokens': usage.total_tokens
                }
            else:
                token_breakdown[date] = {
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'cache_creation_tokens': 0,
                    'cache_read_tokens': 0,
                    'total_tokens': 0
                }

        # Build horizontal bar chart
        from rich.table import Table as RichTable
        from rich.console import Group

        lines = []

        # Legend with timestamp on same line
        refresh_time = self.last_refresh.strftime("%Y-%m-%d %I:%M:%S %p") if self.last_refresh else "Never"
        first_line_table = RichTable.grid(expand=True)
        first_line_table.add_column(justify="left")
        first_line_table.add_column(justify="right")
        first_line_table.add_row(
            "[bold cyan]Legend:[/bold cyan] [bright_blue]⣿[/bright_blue]=Input  [bright_green]⣿[/bright_green]=Output  [yellow]⣿[/yellow]=Cache Create  [bright_magenta]⣿[/bright_magenta]=Cache Read",
            f"[dim]Last Updated: {refresh_time}[/dim]"
        )
        lines.append(first_line_table)

        # Display mode info
        if self.display_mode == 'tokens':
            lines.append(f"[dim]Mode: TOKENS | ⣿ = {self.TOKENS_PER_FULL_DOT/1000:.0f}K tokens (each subdot = {self.TOKENS_PER_SUBDOT/1000:.0f}K) | Press 'd' to switch to cost mode[/dim]")
        else:
            lines.append(f"[dim]Mode: COST | ⣿ = ${self.COST_PER_FULL_DOT:.2f} (each subdot = ${self.COST_PER_SUBDOT:.2f}) | Press 'd' to switch to token mode[/dim]")

        # View controls info
        lines.append(f"[dim]Showing {self.days_visible} day(s) | ↑/↓: Scroll | +/-: Adjust days[/dim]")
        lines.append("")

        # First pass: calculate all values and determine max widths
        day_data = []
        max_widths = {
            'total_tokens': 0, 'total_cost': 0,
            'input_tokens': 0, 'input_cost': 0,
            'output_tokens': 0, 'output_cost': 0,
            'cache_create_tokens': 0, 'cache_create_cost': 0,
            'cache_read_tokens': 0, 'cache_read_cost': 0
        }

        for date_key in dates:
            tokens = token_breakdown[date_key]
            total = tokens['total_tokens']

            if total == 0:
                day_data.append({'date_key': date_key, 'total': 0})
                continue

            # Parse date
            from datetime import datetime
            date_obj = datetime.strptime(date_key, "%Y-%m-%d")
            day_name = date_obj.strftime("%a")

            # Calculate costs
            total_cost = (
                tokens['input_tokens'] * self.PRICING['input'] +
                tokens['output_tokens'] * self.PRICING['output'] +
                tokens['cache_creation_tokens'] * self.PRICING['cache_creation'] +
                tokens['cache_read_tokens'] * self.PRICING['cache_read']
            )
            input_cost = tokens['input_tokens'] * self.PRICING['input']
            output_cost = tokens['output_tokens'] * self.PRICING['output']
            cache_create_cost = tokens['cache_creation_tokens'] * self.PRICING['cache_creation']
            cache_read_cost = tokens['cache_read_tokens'] * self.PRICING['cache_read']

            # Store data
            day_info = {
                'date_key': date_key,
                'day_name': day_name,
                'total': total,
                'tokens': tokens,
                'total_cost': total_cost,
                'input_cost': input_cost,
                'output_cost': output_cost,
                'cache_create_cost': cache_create_cost,
                'cache_read_cost': cache_read_cost
            }
            day_data.append(day_info)

            # Calculate widths for each field
            max_widths['total_tokens'] = max(max_widths['total_tokens'], len(f"{int(total/1000):,}K"))
            max_widths['total_cost'] = max(max_widths['total_cost'], len(f"${total_cost:.2f}"))

            if tokens['input_tokens'] > 0:
                max_widths['input_tokens'] = max(max_widths['input_tokens'], len(f"{int(tokens['input_tokens']/1000):,}K"))
                max_widths['input_cost'] = max(max_widths['input_cost'], len(f"${input_cost:.2f}"))

            if tokens['output_tokens'] > 0:
                max_widths['output_tokens'] = max(max_widths['output_tokens'], len(f"{int(tokens['output_tokens']/1000):,}K"))
                max_widths['output_cost'] = max(max_widths['output_cost'], len(f"${output_cost:.2f}"))

            if tokens['cache_creation_tokens'] > 0:
                max_widths['cache_create_tokens'] = max(max_widths['cache_create_tokens'], len(f"{int(tokens['cache_creation_tokens']/1000):,}K"))
                max_widths['cache_create_cost'] = max(max_widths['cache_create_cost'], len(f"${cache_create_cost:.2f}"))

            if tokens['cache_read_tokens'] > 0:
                max_widths['cache_read_tokens'] = max(max_widths['cache_read_tokens'], len(f"{int(tokens['cache_read_tokens']/1000):,}K"))
                max_widths['cache_read_cost'] = max(max_widths['cache_read_cost'], len(f"${cache_read_cost:.2f}"))

        # Second pass: render with consistent widths
        for day_info in day_data:
            if day_info['total'] == 0:
                lines.append(f"[bold white]{day_info['date_key']}[/bold white] | [dim]No data[/dim]")
                lines.append("")
                continue

            # Extract precomputed values
            date_key = day_info['date_key']
            day_name = day_info['day_name']
            total = day_info['total']
            tokens = day_info['tokens']
            total_cost = day_info['total_cost']
            input_cost = day_info['input_cost']
            output_cost = day_info['output_cost']
            cache_create_cost = day_info['cache_create_cost']
            cache_read_cost = day_info['cache_read_cost']

            # Build header with dynamically calculated widths
            header_parts = [
                f"[bold white]{day_name:<3} {date_key}[/bold white]",
                f"[white]Total: {f'{int(total/1000):,}K':>{max_widths['total_tokens']}} / {f'${total_cost:.2f}':>{max_widths['total_cost']}}[/white]"
            ]

            if tokens['input_tokens'] > 0:
                header_parts.append(f"[bright_blue]{f'{int(tokens['input_tokens']/1000):,}K':>{max_widths['input_tokens']}} / {f'${input_cost:.2f}':>{max_widths['input_cost']}}[/bright_blue]")

            if tokens['output_tokens'] > 0:
                header_parts.append(f"[bright_green]{f'{int(tokens['output_tokens']/1000):,}K':>{max_widths['output_tokens']}} / {f'${output_cost:.2f}':>{max_widths['output_cost']}}[/bright_green]")

            if tokens['cache_creation_tokens'] > 0:
                header_parts.append(f"[yellow]{f'{int(tokens['cache_creation_tokens']/1000):,}K':>{max_widths['cache_create_tokens']}} / {f'${cache_create_cost:.2f}':>{max_widths['cache_create_cost']}}[/yellow]")

            if tokens['cache_read_tokens'] > 0:
                header_parts.append(f"[bright_magenta]{f'{int(tokens['cache_read_tokens']/1000):,}K':>{max_widths['cache_read_tokens']}} / {f'${cache_read_cost:.2f}':>{max_widths['cache_read_cost']}}[/bright_magenta]")

            lines.append(" | ".join(header_parts))

            # Create cost breakdown dict
            cost_breakdown = {
                'input_cost': input_cost,
                'output_cost': output_cost,
                'cache_create_cost': cache_create_cost,
                'cache_read_cost': cache_read_cost,
                'total_cost': total_cost
            }

            # Single merged bar
            merged_bar = self._render_merged_bar(tokens, cost_breakdown)
            if merged_bar:
                lines.append(merged_bar)

            lines.append("")  # Blank line between days

        # Create content group (first item is table, rest are strings)
        content = Group(*lines)

        panel = Panel(
            content,
            title="[bold magenta]Daily Usage - Dot Matrix",
            border_style="magenta"
        )

        self.update(panel)


class ClaudeUsageTUI(App):
    """Claude Usage Tracker TUI Application."""

    ENABLE_COMMAND_PALETTE = False

    CSS = """
    Screen {
        background: $surface;
    }

    #top_row {
        height: 20;
        dock: top;
        margin: 0;
        padding: 0;
    }

    #middle_row {
        height: auto;
        margin: 0 0 1 0;
        padding: 0;
    }

    Container {
        border: none;
        height: auto;
        padding: 0;
        margin: 0;
    }

    Static {
        margin: 0;
        padding: 0;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_display", "Toggle Display Mode"),
        ("up", "scroll_backward", "Newer Dates"),
        ("down", "scroll_forward", "Older Dates"),
        ("plus,equals", "increase_days", "More Days"),
        ("minus", "decrease_days", "Fewer Days"),
    ]

    def compose(self) -> ComposeResult:
        """Create layout."""
        yield Header(show_clock=True)

        # Top row - Session limits (like /usage)
        with Horizontal(id="top_row"):
            yield SessionLimits()
            yield TokenBreakdown()

        # Middle row - Dot matrix chart
        with Horizontal(id="middle_row"):
            yield DailyUsageChartDots()

        yield Footer()

    def action_toggle_display(self) -> None:
        """Toggle display mode between tokens and cost."""
        for widget in self.query(DailyUsageChartDots):
            widget.toggle_display_mode()

    def action_scroll_forward(self) -> None:
        """Scroll to show older dates."""
        for widget in self.query(DailyUsageChartDots):
            widget.scroll_days_forward()

    def action_scroll_backward(self) -> None:
        """Scroll to show newer dates."""
        for widget in self.query(DailyUsageChartDots):
            widget.scroll_days_backward()

    def action_increase_days(self) -> None:
        """Increase number of visible days."""
        for widget in self.query(DailyUsageChartDots):
            widget.increase_visible_days()

    def action_decrease_days(self) -> None:
        """Decrease number of visible days."""
        for widget in self.query(DailyUsageChartDots):
            widget.decrease_visible_days()


def main():
    """Run the TUI application."""
    parser = argparse.ArgumentParser(
        prog='claude-usage-tracker',
        description=__description__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--version',
        action='version',
        version=f'{__title__} {__version__}'
    )

    args = parser.parse_args()

    # Run the TUI
    app = ClaudeUsageTUI()
    app.run()


if __name__ == "__main__":
    main()
