# Add Google guide skills to a new repository

Use this guide when a new repository should apply the same engineering guidance across agent
sessions. The result is a small set of installed skills and a short `AGENTS.md` routing section.

Install only the guides the repository needs. A smaller set uses less startup context and makes
routing easier to predict.

## 1. Choose the first skills

Start with the repository's language and the workflows the team already uses. For a Python
project that maintains user documentation and reviews every change, start with:

- `google-python-style`
- `google-documentation-guide`
- `google-code-review-author`
- `google-code-review-reviewer`

Use [`catalog/catalog.md`](../catalog/catalog.md) to find other guides. A project should install
only the skills it plans to route because every installed description consumes startup context.

## 2. Install them

Per-user installation is recommended for personal use because it works across repositories:

```bash
uv run google-guides install \
  --agent codex \
  --agent claude-code \
  --skill google-python-style \
  --skill google-documentation-guide \
  --skill google-code-review-author \
  --skill google-code-review-reviewer
```

Per-user installs link back to this checkout. Keep it at the same path or reinstall after moving
it.

With Node.js/npm installed, add `--project /path/to/new-repository --copy` when the repository
should contain the public skills. Select only the agents the repository supports. Use `--dry-run`
to inspect the install.

Select *Software Engineering at Google* skills with `--skill` like any other guide. For example,
add `--skill google-swe-testing` for test-strategy work. The installer asks you to accept the CC
BY-NC-ND 4.0 license before generating it. A project install links that skill back to this
checkout; keep the link out of version control.

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
public copied skills, `AGENTS.md`, and setup documentation together. Do not commit SWE-book links.
