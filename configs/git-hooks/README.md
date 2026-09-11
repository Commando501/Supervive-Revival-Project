# Git hooks — repo-tracked policy

This directory holds git hooks that enforce repo policy. They are **not**
installed automatically; setting `core.hooksPath` is a local git config
change and this repo's policy is to never modify a contributor's git config
without an explicit action.

## Install (once per clone)

```bash
git config core.hooksPath configs/git-hooks
```

Verify:

```bash
git config --get core.hooksPath
# → configs/git-hooks
```

## What each hook does

### `pre-commit` — size gate

Rejects any staged file whose blob would fail GitHub's per-file push limit
(100 MB hard). The hook ceiling is set below that (default **90 MB**) so
you never surprise-fail at push time. Files ≥50 MB pass with a warning
(GitHub itself warns at that size).

**Tunables** (env vars):
- `HOOK_MAX_MB=N` — raise/lower the hard ceiling for one commit
- `HOOK_WARN_MB=N` — raise/lower the warning threshold for one commit

**Per-path override**: add the path to `large-file-allowlist.txt` in this
directory with an inline explanation.

**Emergency bypass** (STRONGLY discouraged): `git commit --no-verify`.

**Requires**: `python3` on `$PATH` (used to parse the null-separated raw
diff robustly). It's on any Windows/macOS/Linux dev box.

## Why this hook exists

Commit `38d96d9` (S139) accidentally committed two evidence files (111 MB
and 188 MB) that both exceed GitHub's 100 MB hard push limit. That single
mistake made `git push origin dedicated-server-stub` fail for every
downstream commit until history was rewritten. See:

- The `.gitignore` block starting with "Individual files that hit or exceeded…"
- CLAUDE.md's discussion of the DLP push saga
- The retirement flow: `git lfs migrate` (preserves the files as LFS objects)
  or `git filter-repo` (drops them entirely) — whichever is chosen when the
  rewrite is done
