"""Claude Usage Tracker version information."""

__version__ = "2.0.1"
__title__ = "Claude Usage Tracker"
__description__ = "A btop-style terminal UI for monitoring Claude AI usage in real-time"
__author__ = "Claude Usage Tracker Contributors"
__license__ = "MIT"

# v2.0.1 - Plan detection and weekly limits
# - Auto-detect user plan (Pro, Max 5x, Max 20x)
# - Display correct session token limits per plan
# - Track and display weekly limits for Max plans (overall, Sonnet, Opus)
# - Fixed TUI widget height to accommodate new sections
# - Cap progress bars at 100% visual display (text shows actual %)
# - Tightened UI layout for more compact display

# v2.0.0 - Major rewrite to use OAuth API
# BREAKING CHANGES:
# - Completely removed pexpect-based 'claude /usage' command spawning
# - Now uses Claude's OAuth API (fast, reliable, read-only)
# - No more usage consumption during monitoring
# - No manual cookie extraction required
# - Works from any directory (no need to run from Claude project dir)
# - Faster: ~300ms vs 2-3 seconds per poll
# - More reliable: JSON parsing vs terminal output parsing
