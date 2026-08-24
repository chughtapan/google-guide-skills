# Add Google guide skills to a new repository

Install only the guides the repository needs, then name them in `AGENTS.md`. Agents route from the
installed descriptions and the repository's instructions.

## 1. Choose the first skills

Start with the repository's language and the workflows the team already uses. For a Python
project that maintains user documentation and reviews every change, start with:

- `google-python-style`
- `google-documentation-guide`
- `google-code-review-author`
- `google-code-review-reviewer`

Use [`catalog/catalog.md`](../catalog/catalog.md) to find other guides. Do not install the full
pack unless the repository uses it; every installed description consumes agent startup context.

## 2. Install them into the repository

From this checkout, run:

```bash
uv run google-guides install \
  --project /path/to/new-repository \
  --agent codex \
  --agent claude-code \
  --copy \
  --skill google-python-style \
  --skill google-documentation-guide \
  --skill google-code-review-author \
  --skill google-code-review-reviewer
```

Select only the agents the repository supports. Use `--dry-run` to inspect the install command.

## 3. Route work in `AGENTS.md`

Keep the routing short and name only installed skills:

```markdown
## Guide routing

- Python changes: use `$google-python-style`.
- Developer documentation: use `$google-documentation-guide`.
- Preparing a change: use `$google-code-review-author`.
- Reviewing a change: use `$google-code-review-reviewer`.
```

Repository rules still take precedence. Add another skill only when a recurring task needs it.

## 4. Verify the setup

Ask each supported agent to perform one normal repository task. Confirm that it loads the intended
skill, follows the repository's existing commands, and does not select unrelated skills. Commit
the installed files, `AGENTS.md`, and any setup documentation together.
