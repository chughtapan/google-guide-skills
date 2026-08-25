---
name: google-html-css-style
description: >-
  Use when writing or reviewing HTML and CSS under Google's conventions for validity, semantics,
  accessibility, formatting, naming, and organization. Do not use for visual design-system
  decisions.
---

# Google HTML/CSS Style

## Scope and precedence

Use this guide for raw, maintained HTML and CSS, including Sass and GSS source. It does not govern
minified or obfuscated output, visual design-system choices, or generated serialization. Follow
repository rules, component-framework syntax, accessibility requirements, browser support, and
checked-in formatter or linter configuration first. Where this guide marks a choice optional,
preserve the project's consistent choice rather than turning it into a new hard rule.

## Workflow

1. Read repository instructions and identify the template language, stylesheet dialect, supported
   browsers, accessibility checks, validator, formatter, and test commands.
2. Inspect nearby markup and styles for semantic structure, selector conventions, component
   prefixes, optional-tag policy, declaration ordering, and wrapping.
3. Build semantic, accessible HTML first; keep presentation in stylesheets and behavior in
   scripts. Add only the classes, data attributes, and IDs needed by those layers.
4. Write the smallest valid CSS selector and declaration set that expresses the design without
   hacks or unnecessary specificity.
5. Format and validate the changed HTML and CSS, then test accessibility, supported viewports,
   states, and browser behavior in proportion to the change.

## High-impact rules

### General source rules

- Use HTTPS for embedded images, media, stylesheets, scripts, and imports whenever the resource is
  available over HTTPS. Do not use protocol-relative URLs.
- Encode source as UTF-8 without a byte-order mark. In HTML, declare
  `<meta charset="utf-8">`; do not add an encoding declaration to ordinary stylesheets.
- Indent with two spaces and no tabs, use lowercase HTML and CSS tokens except literal string
  content, and remove trailing whitespace.
- Write comments only when they add purpose or reasoning. Mark temporary work as
  `TODO: action item`.

### HTML semantics and accessibility

- Begin documents with `<!doctype html>` and produce valid HTML unless a measured file-size
  constraint makes a deviation necessary.
- Use each element for its semantic purpose: headings for headings, paragraphs for prose, anchors
  for navigation, and appropriate controls for interaction. Do not substitute a clickable `div`
  for a link or button.
- Give informative images meaningful `alt` text. Use `alt=""` for decorative or genuinely
  redundant images. Provide captions or transcripts for audio and video when available.
- Keep structure, presentation, and behavior separate. Avoid inline presentation and behavior,
  and minimize the number of linked stylesheets and scripts.
- Write printable UTF-8 characters directly. Use entity references only for characters that are
  special to HTML or are invisible or controlling.
- Omitting optional tags is optional. If the project omits them, do so consistently rather than
  selecting an arbitrary subset.
- Omit `type` on CSS stylesheets and JavaScript scripts. Avoid unnecessary `id` attributes: use
  classes for styling and data attributes for scripts. If an ID is required, include a hyphen so
  it cannot be mistaken for a global JavaScript identifier.

### HTML formatting

- Put block, list, and table elements on new lines and indent their block, list, or table
  children. Account for any meaningful whitespace behavior in inline content.
- There is no fixed HTML column limit. Wrap long markup only when it improves readability, and use
  the project formatter's consistent form so continuation attributes remain distinguishable from
  children.
- Use double quotes for quoted attribute values.

### CSS selectors and values

- Produce valid CSS unless a validator bug or required proprietary syntax makes that impossible.
- Name classes for purpose, not appearance. Keep names brief but meaningful and separate words
  with hyphens. In a large or embedded application, consider a short unique application prefix.
- Prefer class selectors. Avoid ID selectors and type-qualified class selectors such as
  `div.error` unless the element type is essential to the selector.
- Use shorthand properties when they are clear and correct. Omit units from zero unless the
  grammar or supported browser requires one; include the leading zero in fractional values; use
  three-digit hexadecimal colors when equivalent.
- Avoid `!important`, user-agent detection, and CSS hacks. Resolve cascade and compatibility
  problems through structure, selector design, feature support, or a documented last resort.

### CSS formatting

- Keep declaration order consistent with project tooling. If the project has no enforced order,
  alphabetical order is a simple optional choice; ignore vendor prefixes when choosing a
  property's position.
- Indent declarations and nested rules. End every declaration with a semicolon and use exactly
  one space after the property colon.
- Put one space before an opening declaration brace and keep it on the selector line. Put each
  selector and each declaration on its own line, and separate rules with one blank line.
- Use single quotes for CSS strings and attribute selector values. Leave `url()` values unquoted;
  if `@charset` is required, use double quotes.
- Use section comments only when they materially improve navigation through a larger stylesheet.

## Verification and review output

Run the repository formatter and linters, validate changed HTML and CSS, and run relevant template
or component tests. Check keyboard and assistive semantics, media alternatives, responsive states,
and supported browsers when affected. Record any check that could not be run.

For a review, lead with `Ready` or `Needs changes`. Report material issues as `Location`, `Area`
(`Semantics`, `Accessibility`, `HTML`, `Selector`, `CSS`, or `Compatibility`), `Evidence`,
`Impact`, and `Fix`. Keep optional consistency suggestions nonblocking and state validation and
runtime coverage explicitly.
