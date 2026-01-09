# Development Workflow Guide

This guide explains the standard workflow for making changes to the Phoenix LocalClaude codebase, from issue creation through to merging into the main branch.

---

## Overview

We follow a **GitHub Flow** workflow:
1. Create an issue for each task/bug/feature
2. Create a branch from `main` for that issue
3. Make changes and commit
4. Push branch and create Pull Request
5. Review and merge PR
6. Delete branch and update local `main`

**Core Principle:** Never commit directly to `main` - always use branches and PRs.

---

## Step 1: Create an Issue

Every change starts with an issue. This helps track work and provides context.

### Using GitHub CLI

```bash
# Create an enhancement
gh issue create \
  --title "Short descriptive title" \
  --label "enhancement" \
  --body "Detailed description of what needs to be done"

# Create a bug fix
gh issue create \
  --title "Fix: Brief description of the bug" \
  --label "bug" \
  --body "Steps to reproduce, expected vs actual behavior"

# Create documentation update
gh issue create \
  --title "Update documentation for X" \
  --label "documentation" \
  --body "What docs need updating and why"
```

### Common Labels

- `enhancement` - New features or improvements
- `bug` - Something isn't working
- `documentation` - Documentation updates
- `cleanup` / `tech-debt` - Code cleanup or refactoring
- `tests` - Test-related changes
- `performance` - Performance improvements
- `priority:high` / `priority:medium` / `priority:low` - Priority indicators

### Issue Template

```markdown
**Problem/Goal:**
Brief description of what needs to be done and why

**Solution/Approach:**
How you plan to solve it

**Tasks:**
- [ ] Task 1
- [ ] Task 2
- [ ] Task 3

**Acceptance Criteria:**
What needs to be true for this to be considered complete

**Reference:**
Links to relevant docs, files, or related issues
```

---

## Step 2: Create a Feature Branch

Always create a new branch from the latest `main`:

```bash
# Make sure you're on main and it's up to date
git checkout main
git pull origin main

# Create and checkout new branch
git checkout -b <branch-type>/issue-<number>-<short-description>

# Examples:
git checkout -b feature/issue-1-prompt-caching
git checkout -b fix/issue-5-timeout-bug
git checkout -b cleanup/issue-2-remove-credential-code
git checkout -b docs/issue-3-update-readme
git checkout -b test/issue-8-add-tier3-tests
```

### Branch Naming Convention

Format: `<type>/issue-<number>-<description>`

**Types:**
- `feature/` - New features or enhancements
- `fix/` - Bug fixes
- `cleanup/` - Code cleanup, refactoring, tech debt
- `docs/` - Documentation updates
- `test/` - Test additions or modifications
- `perf/` - Performance improvements

**Examples:**
- `feature/issue-1-add-prompt-caching`
- `fix/issue-12-database-timeout`
- `cleanup/issue-2-remove-old-code`
- `docs/issue-7-update-installation-guide`

---

## Step 3: Make Your Changes

Work on the issue in your branch:

```bash
# Check which branch you're on
git branch

# Make your changes
# ... edit files ...

# Check what changed
git status
git diff

# See changes in specific file
git diff path/to/file.py
```

### Best Practices

- **Keep changes focused** - One issue per branch
- **Test your changes** - Run tests before committing
- **Update documentation** - If you change behavior, update docs
- **Follow code style** - Match existing code formatting
- **Add comments** - Explain complex logic

---

## Step 4: Commit Your Changes

Create clear, descriptive commits:

```bash
# Stage specific files
git add path/to/file1.py path/to/file2.py

# Or stage all changed files
git add .

# Check what's staged
git status

# Commit with descriptive message
git commit -m "Brief summary of change (50 chars or less)

Longer explanation if needed:
- What was changed
- Why it was changed
- Any important details

Fixes #<issue-number>"
```

### Commit Message Format

**Structure:**
```
<type>: <subject>

<body>

<footer>
```

**Example:**
```
Add prompt caching configuration to startup.config

- Added CACHE_PROMPT setting to control KV cache behavior
- Updated llama.cpp startup parameters to use cache flag
- Documented caching behavior in README

This should reduce token processing from 35K to ~9 tokens per request,
improving local deployment speed by ~5-6x.

Fixes #1
```

**Important:** The `Fixes #<number>` in the commit message will automatically close the issue when the PR is merged!

### Commit Types

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring (no behavior change)
- `test:` - Adding or updating tests
- `perf:` - Performance improvement
- `chore:` - Build process, dependencies, etc.

---

## Step 5: Push Your Branch

Push your branch to GitHub:

```bash
# First time pushing this branch
git push -u origin feature/issue-1-prompt-caching

# Subsequent pushes (after -u is set)
git push
```

---

## Step 6: Create a Pull Request

### Using GitHub CLI (Recommended)

```bash
# Create PR from current branch
gh pr create --fill

# Or create with custom title/body
gh pr create \
  --title "Implement prompt caching for local deployment" \
  --body "Adds KV cache configuration to improve local performance.

Closes #1"

# Create as draft PR (for work in progress)
gh pr create --draft --fill
```

### PR Description Template

The PR description should include:
```markdown
## Summary
Brief description of changes

## Related Issue
Closes #<issue-number>

## Changes Made
- Change 1
- Change 2
- Change 3

## Testing
How you tested this:
- [ ] Ran test suite (tier 1 + tier 2)
- [ ] Tested manually with scenario X
- [ ] Verified no regressions

## Screenshots/Output
If applicable, add screenshots or command output

## Checklist
- [ ] Code follows project style
- [ ] Tests pass
- [ ] Documentation updated
- [ ] No sensitive data committed
```

---

## Step 7: Review and Merge

### Self-Review Checklist

Before merging, verify:

```bash
# View your PR
gh pr view

# Check the diff
gh pr diff

# Run tests one more time
python tester.py  # Select Quick Validation

# Check for sensitive data
git log --patch | grep -i "secret\|password\|token\|key"
```

### Merge the PR

**If working solo:**
```bash
# Merge your own PR
gh pr merge --squash --delete-branch

# Or merge via web interface
gh pr view --web
```

**If working with team:**
- Wait for code review
- Address feedback
- Get approval
- Then merge

### Merge Strategies

- **Squash and merge** (recommended) - Combines all commits into one clean commit
- **Merge commit** - Keeps all individual commits
- **Rebase and merge** - Applies commits on top of main

For this project, use **squash and merge** to keep history clean.

---

## Step 8: Clean Up After Merge

After PR is merged:

```bash
# Switch back to main
git checkout main

# Pull latest changes (includes your merged PR)
git pull origin main

# Delete local branch (if not auto-deleted)
git branch -d feature/issue-1-prompt-caching

# Verify it's gone
git branch

# Remote branch should be auto-deleted, but if not:
git push origin --delete feature/issue-1-prompt-caching
```

---

## Complete Example Workflow

Here's a complete example from start to finish:

### 1. Create Issue
```bash
gh issue create \
  --title "Remove unnecessary credential manipulation code" \
  --label "cleanup,tech-debt" \
  --body "Remove old credential backup/restore logic from tester.py that's no longer needed."
# Returns: Created issue #2
```

### 2. Create Branch
```bash
git checkout main
git pull origin main
git checkout -b cleanup/issue-2-remove-credential-code
```

### 3. Make Changes
```bash
# Edit tester.py to remove the code
nano tester.py  # or use PyCharm

# Check what changed
git diff tester.py
```

### 4. Commit Changes
```bash
git add tester.py
git commit -m "Remove unnecessary credential manipulation code

- Removed credential backup/restore logic from tester.py
- Cleaned up related comments and documentation
- Verified both Anthropic and local deployments still work

This code was originally added to prevent local tests from accidentally
using the Anthropic API, but we discovered these were actually local
Claude Code agent spawns (normal behavior), not API calls.

Fixes #2"
```

### 5. Push Branch
```bash
git push -u origin cleanup/issue-2-remove-credential-code
```

### 6. Create PR
```bash
gh pr create --fill
# Or view in browser: gh pr create --web
```

### 7. Merge PR
```bash
# Review the PR
gh pr view

# Merge it
gh pr merge --squash --delete-branch
```

### 8. Clean Up
```bash
git checkout main
git pull origin main
git branch -d cleanup/issue-2-remove-credential-code
```

Done! Issue #2 is now closed and the code is merged into `main`. ✓

---

## Working on Multiple Issues

If working on multiple issues simultaneously:

```bash
# Work on issue #1
git checkout -b feature/issue-1-caching
# ... make changes ...
git push -u origin feature/issue-1-caching
gh pr create --draft  # Mark as draft if not ready

# Switch to work on issue #2
git checkout main
git checkout -b cleanup/issue-2-remove-code
# ... make changes ...
git push -u origin cleanup/issue-2-remove-code
gh pr create

# Switch back to issue #1
git checkout feature/issue-1-caching
# ... continue work ...
```

---

## Handling Conflicts

If `main` has changed since you created your branch:

```bash
# Update your branch with latest main
git checkout feature/issue-1-caching
git fetch origin
git rebase origin/main

# If conflicts occur:
# 1. Fix conflicts in the files
# 2. Stage resolved files: git add <file>
# 3. Continue rebase: git rebase --continue

# Force push (rebase rewrites history)
git push --force-with-lease
```

---

## Common Commands Quick Reference

```bash
# Issues
gh issue list                        # List open issues
gh issue view 5                      # View issue #5
gh issue create                      # Create new issue

# Branches
git checkout main                    # Switch to main
git pull origin main                 # Update main
git checkout -b feature/issue-1      # Create new branch
git branch                           # List branches
git branch -d branch-name            # Delete branch

# Changes
git status                           # What's changed
git diff                             # See changes
git add file.py                      # Stage file
git commit -m "message"              # Commit changes

# Pull Requests
gh pr create --fill                  # Create PR
gh pr list                           # List PRs
gh pr view                           # View current PR
gh pr merge --squash                 # Merge PR

# Repository
gh repo view                         # View repo info
gh repo view --web                   # Open in browser
```

---

## Tips for Success

### Do:
- ✓ Create small, focused PRs (easier to review)
- ✓ Write clear commit messages
- ✓ Reference issue numbers in commits
- ✓ Test before pushing
- ✓ Keep branches up to date with main
- ✓ Delete branches after merging

### Don't:
- ✗ Commit directly to main
- ✗ Create huge PRs with many unrelated changes
- ✗ Leave stale branches hanging around
- ✗ Forget to pull latest main before creating branch
- ✗ Commit sensitive data (secrets, API keys, large files)
- ✗ Use vague commit messages like "fix" or "update"

---

## Getting Help

```bash
# Git help
git --help
git <command> --help

# GitHub CLI help
gh --help
gh <command> --help

# View this workflow guide
cat WORKFLOW.md
```

---

## PyCharm Integration

If using PyCharm for Git operations:

1. **Create branch**: **VCS** → **Git** → **Branches** → **New Branch**
2. **Commit**: **Commit** tool window (Alt+0)
3. **Push**: **VCS** → **Git** → **Push** (Ctrl+Shift+K)
4. **Create PR**: **VCS** → **Git** → **GitHub** → **Create Pull Request**
5. **Update from main**: **VCS** → **Git** → **Rebase**

PyCharm will handle most git commands through the GUI, but the workflow remains the same!

---

**Last Updated:** 2026-01-02
**Workflow Version:** 1.0
