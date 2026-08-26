"""Mechanical Markdown conversion with no semantic rewriting."""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify

HTML_SUFFIXES = {".html", ".htm", ".xml", ".xhtml"}
INLINE_CODE_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)
FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")
MARKDOWN_IMAGE_RE = re.compile(r"!\[([^]]*)\]\(((?:[^()\n\\]|\\.|\([^()\n]*\))*)\)")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^]]+)\]\(((?:[^()\n\\]|\\.|\([^()\n]*\))*)\)")


def markdown_inline_segments(value: str) -> tuple[tuple[bool, str], ...]:
    """Split Markdown into inline-code and ordinary text segments."""
    segments: list[tuple[bool, str]] = []
    cursor = 0
    for match in INLINE_CODE_RE.finditer(value):
        if match.start() > cursor:
            segments.append((False, value[cursor : match.start()]))
        segments.append((True, match.group(0)))
        cursor = match.end()
    if cursor < len(value):
        segments.append((False, value[cursor:]))
    return tuple(segments)


def next_markdown_fence(line: str, fence: tuple[str, int] | None) -> tuple[str, int] | None:
    """Return the fenced-code state after one Markdown line."""
    if fence is not None:
        marker, length = fence
        if re.fullmatch(rf"[ \t]*{re.escape(marker)}{{{length},}}[ \t]*", line):
            return None
        return fence

    match = FENCE_RE.match(line)
    if match is None:
        return None
    run, info = match.groups()
    if run[0] == "`" and "`" in info:
        return None
    return run[0], len(run)


def markdown_fenced_segments(value: str) -> tuple[tuple[bool, str], ...]:
    """Split Markdown into fenced-code and ordinary text segments."""
    fenced_segments: list[tuple[bool, str]] = []
    current: list[str] = []
    current_is_code = False
    fence: tuple[str, int] | None = None

    def finish() -> None:
        if current:
            fenced_segments.append((current_is_code, "".join(current)))
            current.clear()

    for line in value.splitlines(keepends=True):
        raw_line = line.rstrip("\r\n")
        was_fenced = fence is not None
        next_fence = next_markdown_fence(raw_line, fence)
        is_fence_line = next_fence != fence
        line_is_code = was_fenced or is_fence_line
        if current and line_is_code != current_is_code:
            finish()
        current_is_code = line_is_code
        current.append(line)
        fence = next_fence
    finish()

    return tuple(fenced_segments)


def _normalize_generated_markdown(value: str) -> str:
    value = value.replace("\xa0", " ")
    value = "\n".join(line.rstrip() for line in value.splitlines())
    value = re.sub(r"\n{4,}", "\n\n\n", value)
    return value.strip() + "\n"


def markup_to_markdown(value: str, parser: str = "html.parser") -> str:
    """Convert document-oriented HTML or XML to Markdown without summarizing it."""
    soup = BeautifulSoup(value, parser)
    for element in soup.select("script, style, noscript"):
        element.decompose()
    content = (
        soup.find("main")
        or soup.find(id="content")
        or soup.find(attrs={"role": "main"})
        or soup.body
        or soup
    )
    converted = markdownify(
        str(content),
        heading_style="ATX",
        bullets="-",
        strip=["span"],
        bs4_options={"features": parser},
    )
    return _normalize_generated_markdown(converted)


def guide_xml_to_markdown(value: str) -> str:
    """Convert Google's GUIDE/CATEGORY/STYLEPOINT XML into semantic Markdown."""
    soup = BeautifulSoup(value, "xml")
    guide = soup.find("GUIDE")
    if guide is None:
        return markup_to_markdown(value, parser="xml")

    for element, level in (
        (guide, 1),
        *((element, 2) for element in guide.find_all("CATEGORY")),
        *((element, 3) for element in guide.find_all("STYLEPOINT")),
        *((element, 4) for element in guide.find_all("SUBSECTION")),
    ):
        title = element.get("title")
        if title:
            heading = soup.new_tag(f"h{level}")
            heading.string = title
            element.insert(0, heading)

    for element in guide.find_all(("CODE_SNIPPET", "BAD_CODE_SNIPPET")):
        replacement = soup.new_tag("pre")
        replacement.string = element.get_text("", strip=False).strip("\n")
        if element.name == "BAD_CODE_SNIPPET":
            label = soup.new_tag("strong")
            label.string = "Bad code:"
            element.insert_before(label)
        element.replace_with(replacement)

    for element in guide.find_all(("OVERVIEW", "SUMMARY", "BODY")):
        element.unwrap()

    return markup_to_markdown(str(guide), parser="xml")


def source_to_markdown(path: Path) -> tuple[str, str]:
    """Return Markdown plus the conversion mode recorded in provenance."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in HTML_SUFFIXES:
        if path.suffix.lower() == ".xml" and BeautifulSoup(text, "xml").find("GUIDE"):
            return guide_xml_to_markdown(text), "google-styleguide-xml-to-markdown"
        parser = "xml" if path.suffix.lower() in {".xml", ".xhtml"} else "html.parser"
        mode = "xml-to-markdown" if parser == "xml" else "html-to-markdown"
        return markup_to_markdown(text, parser=parser), mode
    return text if text.endswith("\n") else f"{text}\n", "identity"
