# Google Documentation Guide

## Objective

Create or improve technical documentation that helps a defined audience complete one job. Keep
the content accurate, concise, easy to find, readable as plain text, and maintainable with the
code or process it describes.

## Workflow

1. Read repository instructions and inspect the relevant code, configuration, commands, and
   existing documentation. Do not document assumptions as facts.
2. Define the audience, their task, the document's single purpose, and the result they should
   reach. Choose the document type before drafting.
3. Find the canonical document. Update it instead of creating a competing explanation. If no
   suitable document exists, place the new one near the code when practical and establish an
   owner.
4. Draft the smallest document that serves the purpose. Introduce who the document is for, what
   it covers, and why or when the reader needs it before giving detailed instructions.
5. Verify commands, code samples, links, prerequisites, and expected results when possible.
   Update affected documentation in the same change as the code.
6. Review for technical accuracy, audience clarity, source consistency, and freshness. Remove
   obsolete or redundant material rather than preserving it for completeness.

## Decision rules

### Choose the right document

- Use a README to orient someone to a package or directory. State what it contains, what it is
  for, its status, how to use and test it, who owns it, and where detailed documentation lives.
- Use API reference documentation to define the contract: purpose, parameters, return values,
  errors, restrictions, and observable behavior. Keep implementation rationale elsewhere unless
  it changes correct usage.
- Use a tutorial for one end-to-end task. Give prerequisites, ordered actions, expected results,
  and a way to verify success. Present the simplest working path first.
- Use conceptual documentation to explain a model, relationship, or tradeoff spanning several
  APIs. Favor clarity and common use over exhaustive edge cases; leave completeness to reference
  documentation.
- Use a design document to collect feedback on a proposed decision and record its alternatives
  and rationale. After implementation, treat it as a decision record rather than current usage
  documentation.
- Use a landing page only for orientation and navigation. Do not mix a customer-facing entry
  point with an internal team page.

### Keep documentation healthy

- Keep each document focused on one purpose and each section focused on one topic.
- Prefer a small, accurate set of documents to a large, stale set. Delete dead documentation or
  mark it obsolete and direct readers to the replacement.
- Avoid duplication. Link to the canonical source and contribute corrections there.
- Store stable documentation under version control when practical. Record ownership and review
  it as the system changes.
- Optimize for the reader. Use direct language, meaningful names, necessary context, and
  examples only when they materially reduce ambiguity.
- Balance completeness, accuracy, and clarity according to the document's purpose. Never trade
  away accuracy that the reader needs to act safely.

### Write maintainable Markdown

- Use one descriptive H1, followed by a short introduction and logically nested, unique
  headings. Use ATX headings and blank lines around headings and blocks.
- Follow repository formatting rules. Otherwise keep source text reasonably narrow, avoid
  trailing whitespace, and prefer plain Markdown to HTML.
- Use inline code for identifiers, commands, and generic filenames. Use fenced code blocks with
  a language label for multiline examples, and keep shell commands directly copyable.
- Use informative link text. Prefer simple, durable paths and avoid links whose meaning depends
  on “here” or a raw URL. Include enough local context that loss of an external link does not
  make the document unintelligible.
- Use lists for sequential or grouped information and tables only for genuinely tabular,
  parallel data. Keep table cells short.
- Use images only when showing is clearer than describing, and provide useful alternative text.
- Add a table of contents only when the document is long and its renderer supports one.

### Review proportionately

- Seek a subject-matter review for accuracy, an audience review for clarity, and a writing review
  for consistency when the document's reach or risk warrants them.
- Prefer incremental improvement over prolonged polishing. Block a documentation change when it
  introduces material inaccuracy, harmful ambiguity, or a clear regression; make lesser polish
  comments nonblocking.

## Output contract

For a writing task, produce the finished document in the requested location and state any facts,
commands, or links that could not be verified.

For a review, lead with the result, then report:

- `Required`: location and evidence, reader impact, and a concrete correction.
- `Suggested`: a nonblocking improvement and its benefit.
- `Freshness`: missing ownership, obsolete content, duplication, or documentation that must
  change with the code.
- `Verification`: checks performed and anything not verified.

Do not invent project facts, test results, owners, or links. If no material issue exists, say so
directly and identify any remaining verification risk.
