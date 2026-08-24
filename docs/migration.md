# Add Google guide skills to an existing repository

Migrate one workflow at a time. Keep project rules in force while you test the skill.

## 1. Pick a small pilot

Choose one repeated task, such as Python review, README maintenance, test
design, or change review. Find the matching guide in
[`catalog/catalog.md`](../catalog/catalog.md). Avoid changing generated code, formatting the whole
repository, or adopting several new processes in the same change.

## 2. Install the matching skills

Per-user installation is recommended for a pilot:

```bash
uv run google-guides install \
  --agent codex \
  --agent claude-code \
  --skill google-python-style \
  --skill google-code-review-reviewer
```

Add `--project /path/to/existing-repository --copy` when the repository should contain the public
skills. Add `--include-swe-book` when the pilot needs the Software Engineering at Google guides;
the installer asks for license acceptance. Project SWE-book installs are links to this checkout
and should remain untracked.

## 3. Add one routing section

Add the rules to the repository's `AGENTS.md`:

```markdown
## Guide routing

- Python changes: use `$google-python-style` and the repository's existing formatter.
- Change reviews: use `$google-code-review-reviewer` and the repository's existing review rules.
```

Do not duplicate local conventions already stated elsewhere. Link to their source of truth when a
skill needs to be combined with them.

## 4. Validate before expanding

Use the skill on a normal change, run the repository's tests and linters, and review the diff.
Keep the skill when it improves the result without adding unrelated work. Then migrate the next
workflow in another small change. If it does not help, remove its install and routing line.
