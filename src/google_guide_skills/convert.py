"""Mechanical Markdown conversion with no semantic rewriting."""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify

HTML_SUFFIXES = {".html", ".htm", ".xml", ".xhtml"}


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


def source_to_markdown(path: Path) -> tuple[str, str]:
    """Return Markdown plus the conversion mode recorded in provenance."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in HTML_SUFFIXES:
        parser = "xml" if path.suffix.lower() in {".xml", ".xhtml"} else "html.parser"
        mode = "xml-to-markdown" if parser == "xml" else "html-to-markdown"
        return markup_to_markdown(text, parser=parser), mode
    return text if text.endswith("\n") else f"{text}\n", "identity"
