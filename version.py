"""Claude Usage Tracker version information."""

__version__ = "2.0.0"
__title__ = "Claude Usage Tracker"
__description__ = "A btop-style terminal UI for monitoring Claude AI usage in real-time"
__author__ = "Claude Usage Tracker Contributors"
__license__ = "MIT"

# v2.0.0 - Major rewrite to use OAuth API
# BREAKING CHANGES:
# - Completely removed pexpect-based 'claude /usage' command spawning
# - Now uses Claude's OAuth API (fast, reliable, read-only)
# - No more usage consumption during monitoring
# - No manual cookie extraction required
# - Works from any directory (no need to run from Claude project dir)
# - Faster: ~300ms vs 2-3 seconds per poll
# - More reliable: JSON parsing vs terminal output parsing
