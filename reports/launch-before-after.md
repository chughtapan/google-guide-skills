# Google Guide Skills: Before and After

> Historical experiment: this run used the retired 31-skill corpus. It explains an earlier
> installer and documentation decision but does not measure the current 24-skill pack.

The same Codex model changed the same repository twice: once without Google
Guide Skills and once with the then-current 31-skill pack. Both results work. The
installer code converged exactly, while the
README, maintainer guide, and tests show smaller differences that readers can
inspect directly.

This is one controlled case study, not a benchmark.

## Result

| Result | Without the guides | With the guides |
| --- | ---: | ---: |
| Codex exit status | 0 | 0 |
| Changed files | 11 | 11 |
| Patch size | +149 / -178 | +131 / -176 |
| `tests/test_cli.py` | +24 / -11 | +10 / -10 |
| Full test suite | 197 passed | 197 passed |
| Coverage | 89.63% | 89.60% |
| Format, lint, and diff checks | Passed | Passed |

Read the complete results:

- [Patch without the guides](launch-experiment/baseline.patch)
- [Patch with the guides](launch-experiment/guided.patch)

## Changed trees

Both results changed the same ten existing paths:

```text
CHANGELOG.md
README.md
docs/agent-skills-research.md
docs/architecture.md
docs/licensing.md
docs/migration.md
docs/onboarding.md
src/google_guide_skills/cli.py
src/google_guide_skills/installer.py
tests/test_cli.py
```

The only file-tree difference was the name of the new maintainer guide:

| Without the guides | With the guides |
| --- | --- |
| `docs/maintenance.md` | `docs/development.md` |

## What changed

Both runs removed `--include-swe-book` from the normal install, asked for
license acceptance only when selected skills required it, recommended a
per-user install, retained project installs, rewrote the README around user
value, and moved maintainer commands into a separate document.

The resulting `cli.py` files are byte-for-byte identical. The resulting
`installer.py` files are also byte-for-byte identical. The differences are in
the surrounding communication and tests:

- The unguided result added `docs/maintenance.md`; the guided result added the
  shorter `docs/development.md`.
- The guided README separates installation, skill choice, licensing, and
  project documentation. The unguided README keeps more licensing and catalog
  detail inside the installation and contents sections.
- The guided result changed 20 lines in `tests/test_cli.py`; the unguided
  result changed 35. Both cover the default SWE-book path and public-only
  selection, and both pass the same full suite.

The guided run opened seven installed skills while working:
`google-documentation-guide`, `google-swe-documentation`,
`google-swe-maintenance-and-delivery`, `google-swe-testing`,
`google-swe-style-and-readability`, `google-python-style`, and
`google-json-style`.

## Experiment setup

Both runs used the same inputs. The generated guide pack was the only intended
difference.

| Input | Value |
| --- | --- |
| Source | `890449899f6d8c287480ffda992d1e723c8097f0` |
| Codex | `codex-cli 0.149.0` |
| Model | `gpt-5.6-sol` |
| Dependencies | The same frozen `uv.lock`, prepared before each run |
| Authentication | The same existing OAuth login copied into two fresh homes |
| Without guides | Fresh Codex home with no guide skills |
| With guides | Fresh Codex home with the then-current 31 generated guide skills |
| Runs | One non-interactive run per setup, without follow-up prompts |

The tracked `skills/` payload was omitted from both task copies so the unguided
run could not read the guides from the repository. It was available only
through the guided run's Codex home.

## Task

> Simplify this repository's install experience. The Software Engineering at
> Google skills should be part of the normal install instead of requiring a
> separate include flag. Ask for license acceptance only when selected skills
> need it. Recommend per-user installation, but support a project installation
> when requested. Rewrite the main README to lead with what the project gives
> users and why it matters; move maintainer mechanics out of the README. Keep
> the solution simple, update affected documentation and tests, and do not add
> unnecessary regression tests. Verify the result.
>
> For this experiment, do not inspect or regenerate the repository's `skills/`
> directory; it is intentionally omitted. If a skill named by `AGENTS.md` is
> unavailable, continue without it.

## Verification

Each complete patch was applied to a separate clean checkout containing the
full repository. The same four checks then ran against both:

```shell
uv run ruff format --check src tests
uv run ruff check .
uv run pytest --cov=google_guide_skills --cov-report=term-missing tests
git diff --check
```

All four checks passed for both patches. Neither experimental patch was merged;
the repository's separately reviewed working change remains the release
candidate.

## Limits

This comparison covers one repository, one task, one model, and one run per
setup. The runs were sequential rather than simultaneous. Matching code and a
smaller diff do not prove that the guide pack will improve every task, model,
or repository. The complete patches are published so readers can decide what
is better, worse, or simply different.
