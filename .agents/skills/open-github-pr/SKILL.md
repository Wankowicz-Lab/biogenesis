---
name: open-github-pr
description: Prepares and opens a GitHub pull request for this repository. Use when opening a PR, merging via GitHub, pushing a feature branch, or when the user says pull request, gh pr, or ready to merge.
compatibility: Requires git; `git push` and GitHub API need network. Install GitHub CLI (`gh`) for `gh pr create`, or open the compare URL in a browser. Linked worktrees may need **full** (non-sandboxed) terminal permissions for `git checkout -b` / `git push` if refs live outside the worktree path.
---

# Open a GitHub pull request

## Before a PR

1. Follow **[run-tests](../run-tests/SKILL.md)**: scoped tests, then full `pytest` over the project’s test tree with network when needed, until green. Do not open a PR while tests fail locally unless the user explicitly overrides.

2. **Preserve inline comments** (see [AGENTS.md](../../../AGENTS.md) Documentation). Before committing or pushing, scan the branch diff for removed comment lines and restore any that were dropped during refactors (updated wording is fine; delete only if wrong/obsolete):

```bash
git diff origin/main...HEAD -- '*.py' | rg '^-[^-].*#' || true
```

If `origin/main` is unavailable, use `main...HEAD`. Review each hit in context: restore missing comments in the new code, or confirm intentional removal. Do not open the PR until this pass is done.

3. **Commit** all intended changes (`git status` clean for the work you are including).

## Worktree vs branch

The same repo may be edited in a **linked worktree** (`git worktree list` shows this path) or in the primary clone. Behavior differs only when you need a **branch name** for the PR.

| Situation | Action |
|-----------|--------|
| **Detached HEAD** (`git branch --show-current` empty) | Create a branch before push: `git checkout -b <short-descriptive-name>` |
| **On `main` / default branch with local-only commits** | Create a feature branch: `git checkout -b <short-descriptive-name>` — do not PR directly from default unless the user asks |
| **Already on a feature branch** | No extra branch step; ensure it is pushed |

Use a branch name that reflects the change. If unsure, derive it from the main commit theme.

### Worktrees and sandboxed git

In a **linked worktree**, branch refs are stored under the **main repository’s `.git`**, not only inside the worktree directory. Agent terminals with a **filesystem sandbox** may deny creating refs (`cannot lock ref`, `Operation not permitted` under `.../refs/heads/...`). If that happens when running `git checkout -b` or similar, **retry the same git command with full permissions** (disable sandbox / request `all`) so the parent `.git` can be updated.

## Push

From the repository root (worktree or main clone):

```bash
git push -u origin HEAD
```

If the branch already tracks a remote, `git push` may suffice.

## PR title and body (no prompts)

Draft the **title** and **body yourself** from `git log`, `git diff origin/main...HEAD` (or `main...HEAD` if no `origin/main`), and changed file paths. **Do not ask the user** to supply the description unless they volunteer edits.

**Title:** One line, imperative mood, ≤ ~72 characters when possible. Summarizes the whole change set (not only the last commit).

**Body:** Use short, complete sentences (see repository [AGENTS.md](../../../AGENTS.md) if present). Structure:

1. **Goal** — What problem or outcome this PR addresses (why merge it).
2. **Implementation** — How the changes achieve that (modules, key mechanisms, tests added/updated).
3. **Other areas** — Call out incidental edits (docs, skills, CI, refactors, formatting) or explicitly state *None* if the diff is tightly scoped.

If the PR is large, prefer accurate summary over listing every file.

## Open the PR

**Preferred (GitHub CLI):**

```bash
gh pr create --title "..." --body "..."
```

If `gh` is **not on `PATH`** (common in non-interactive shells), try Homebrew locations first, then fall back to the compare URL:

```bash
PATH="/opt/homebrew/bin:/usr/local/bin:$PATH" gh pr create --title "..." --body "..."
# or: /opt/homebrew/bin/gh pr create ...
```

Use `--draft` if the user wants a draft. If `gh` is not installed anywhere, give the remote compare URL: `https://github.com/<org>/<repo>/compare/<branch>?expand=1` (derive org/repo from `git remote -v`).

## Checklist

- [ ] Tests passed per **run-tests** workflow
- [ ] Removed-comment diff scan done; dropped comments restored or intentionally removed
- [ ] On a **non-default** branch (unless explicitly PR’ing to default)
- [ ] Pushed to `origin`
- [ ] Title + body drafted from the diff; user not blocked on writing copy
