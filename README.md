# Google Guide Skills

Coding agents can produce working code, but keeping that code readable and maintainable still
means repeatedly explaining style, testing, review, and documentation standards. Google published
much of the engineering guidance behind those standards. This project turns that guidance into
[Agent Skills](https://agentskills.io/) that agents can apply while they work.

The pack helps agents:

- write and review code using Google's language guides;
- prepare and review changes using Google's engineering practices;
- write documentation that stays useful;
- make better decisions about testing, engineering standards, code review, change management,
  builds, dependencies, CI, team practices, developer productivity, and compute platforms.

Each skill is small enough to load as one useful guide. Agents do not have to guess which chapter
or reference file contains the rule they need.

## Install

You need Git and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/chughtapan/google-guide-skills.git
cd google-guide-skills
uv run google-guides install
```

The default installs the full pack for the current user in Codex and Claude Code. It shows the
*Software Engineering at Google* license before generating and linking the eight skills drawn
from that book. The links point to this checkout, so keep it at the same path or reinstall after
moving it.

To target one agent, pass `--agent codex` or `--agent claude-code`. For a noninteractive install,
pass `--accept-swe-book-license` after reading the license.

To install into one repository instead, also install Node.js/npm for `npx`:

```bash
uv run google-guides install --project /path/to/repository --copy
```

Public skills are copied into the repository. SWE-book skills are linked to this checkout so the
licensed generated text is not copied into the project. Keep those links out of version control.

## Use the skills in a repository

Agents can discover installed skills from their descriptions. Add only the routing rules your
repository needs to `AGENTS.md`:

```markdown
## Guide routing

- Python changes: use `$google-python-style`.
- Documentation: use `$google-documentation-guide`.
- Change reviews: use `$google-code-review-reviewer` and `$google-swe-testing`.
```

The [new-repository guide](docs/onboarding.md) shows how to choose a starting set. The
[migration guide](docs/migration.md) shows how to add the skills to an existing repository one
workflow at a time. The [catalog](catalog/catalog.md) lists all 16 public and 8 local skills.

## Sources and licenses

Every skill records its pinned source, input hashes, and license. Public skills are installable
from the checkout. The installer requires license acceptance before generating the eight local
SWE-book skills under CC BY-NC-ND 4.0. They must not be committed or redistributed.

See the [licensing policy](docs/licensing.md), [architecture](docs/architecture.md), and
[evaluation method](docs/evaluation.md) for project details.

This independent project is not affiliated with or endorsed by Google.
