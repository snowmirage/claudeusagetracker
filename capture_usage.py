#!/usr/bin/env python3
"""
Helper script to capture /usage output for the TUI.

Run this script and paste your /usage output when prompted.
"""

import os
from pathlib import Path

CACHE_FILE = Path.home() / ".claude_usage_cache.txt"

def main():
    print("=" * 60)
    print("Claude Usage Capture Helper")
    print("=" * 60)
    print()
    print("To update the TUI with current usage limits:")
    print("1. Run '/usage' in your Claude Code terminal")
    print("2. Copy ALL the output (Ctrl+Shift+C)")
    print("3. Paste it here and press Ctrl+D (or Ctrl+Z on Windows)")
    print()
    print("Paste /usage output here:")
    print("─" * 60)

    # Read all input until EOF
    lines = []
    try:
        while True:
            line = input()
            lines.append(line)
    except EOFError:
        pass

    content = "\n".join(lines)

    if not content.strip():
        print("\n❌ No input received")
        return 1

    # Save to cache file
    try:
        with open(CACHE_FILE, 'w') as f:
            f.write(content)

        print()
        print("=" * 60)
        print("✓ Usage data cached successfully!")
        print("=" * 60)
        print(f"Saved to: {CACHE_FILE}")
        print()
        print("The TUI will now display your current usage limits.")
        print("Rerun this script anytime to update the cache.")
        return 0

    except Exception as e:
        print(f"\n❌ Error saving cache: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
