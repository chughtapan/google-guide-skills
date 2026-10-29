"""Capture and verify explicitly enumerated public documentation snapshots."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup
from soupsieve import SelectorSyntaxError

from .errors import SourceError
from .models import Manifest, WebSource
from .path_policy import require_safe_project_path

MAX_PAGE_BYTES = 5 * 1024 * 1024
PUBLIC_HOSTS = frozenset({"developers.google.com", "docs.cloud.google.com", "cloud.google.com"})
CC_URL = "https://creativecommons.org/licenses/by/4.0/"
APACHE_URL = "https://www.apache.org/licenses/LICENSE-2.0"


def require_public_url(url: str) -> None:
    """Reject non-documentation origins, credentials, and noncanonical URLs."""
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.netloc not in PUBLIC_HOSTS
        or parsed.query
        or parsed.fragment
        or not (
            parsed.path in {"/style", "/tech-writing"}
            or parsed.path.startswith(
                ("/architecture/", "/stackdriver/docs/", "/style/", "/tech-writing/")
            )
        )
        or any(part in {".", ".."} for part in urllib.parse.unquote(parsed.path).split("/"))
    ):
        raise SourceError(f"Not an approved public documentation URL: {url}")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _license_notice(html: str, source: WebSource) -> str:
    soup = BeautifulSoup(html, "html.parser")
    notices = soup.select(f'p:has(a[href="{CC_URL}"])')
    if len(notices) != 1:
        raise SourceError("Expected exactly one CC BY 4.0 page license notice")
    notice = notices[0].get_text(" ", strip=True)
    if "content of this page is licensed" not in notice.lower():
        raise SourceError("Page does not identify its content license")
    if source.license.code_samples_spdx and (
        not notices[0].select(f'a[href="{APACHE_URL}"]') or "code samples" not in notice.lower()
    ):
        raise SourceError("Page lost its Apache-2.0 code sample notice")
    evidence = f"{notice}\n\nContent license: {CC_URL}\n"
    if source.license.code_samples_spdx:
        evidence += f"Code samples: {APACHE_URL}\n"
    return evidence


def article_html(html: str, selector: str) -> str:
    """Extract one article, retaining its title, examples, and substantive sidebars."""
    soup = BeautifulSoup(html, "html.parser")
    try:
        matches = soup.select(selector)
    except (ValueError, NotImplementedError, SelectorSyntaxError) as exc:
        raise SourceError(f"Invalid article selector: {selector}") from exc
    if len(matches) != 1 or len(matches[0].select("h1")) != 1:
        raise SourceError(f"Expected one article with one title for selector {selector!r}")
    article = matches[0]
    for element in article.select(
        "script, style, noscript, .nocontent, devsite-bookmark, "
        "devsite-feedback, devsite-page-summary, .devsite-page-summary, "
        "devsite-key-takeaways, devsite-key-takeaways-panel, .devsite-key-takeaways-panel, "
        "devsite-thumb-rating, .devsite-article-meta, .devsite-article-footer"
    ):
        element.decompose()
    return str(article)


def _snapshot_bytes(html: str) -> bytes:
    """Keep document and license markup without browser scripts or styling."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.select("script, style, noscript"):
        element.decompose()
    return str(soup).encode("utf-8")


class _PublicRedirects(urllib.request.HTTPRedirectHandler):
    """Apply the same source boundary before following an HTTP redirect."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require_public_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download(url: str) -> tuple[bytes, str]:
    require_public_url(url)
    request = urllib.request.Request(
        url, headers={"Accept-Language": "en", "User-Agent": "google-guide-skills/0.3"}
    )
    try:
        with urllib.request.build_opener(_PublicRedirects()).open(request, timeout=30) as response:
            resolved = response.geturl()
            require_public_url(resolved)
            if response.headers.get_content_type() != "text/html":
                raise SourceError(f"Expected HTML from {url}")
            data = response.read(MAX_PAGE_BYTES + 1)
    except (OSError, urllib.error.URLError) as exc:
        raise SourceError(f"Could not capture {url}: {exc}") from exc
    if len(data) > MAX_PAGE_BYTES:
        raise SourceError(f"Snapshot exceeds the {MAX_PAGE_BYTES}-byte page limit: {url}")
    return data, resolved


def snapshot_root(manifest: Manifest, source: WebSource) -> Path:
    """Return a physically safe source-owned snapshot directory."""
    return require_safe_project_path(
        manifest.project_root,
        manifest.project_root / "sources" / "web" / source.id,
        context="Web snapshot",
        error_type=SourceError,
    )


def _safe_file(manifest: Manifest, path: Path) -> Path:
    return require_safe_project_path(
        manifest.project_root, path, context="Web snapshot file", error_type=SourceError
    )


def refresh_snapshot(manifest: Manifest, source_id: str) -> Path:
    """Capture a source, then atomically switch its lock to an immutable bundle."""
    if source_id not in manifest.web_sources:
        raise SourceError(f"Unknown web source: {source_id}")
    source = manifest.web_sources[source_id]
    root = snapshot_root(manifest, source)
    files: dict[str, bytes] = {}
    records: list[dict[str, str]] = []
    notices: list[str] = []
    # Finish all downloads and validation before changing the accepted snapshot.
    for page in source.pages:
        data, resolved = _download(page.url)
        try:
            html = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SourceError(f"Snapshot is not UTF-8: {page.url}") from exc
        article_html(html, page.selector)
        notice = _license_notice(html, source)
        data = _snapshot_bytes(html)
        files[page.path] = data
        evidence_path = f"licenses/{page.path.removesuffix('.html')}.txt"
        files[evidence_path] = notice.encode()
        records.append(
            {
                **page.to_dict(),
                "resolved_url": resolved,
                "sha256": _digest(data),
                "license_path": evidence_path,
                "license_sha256": _digest(files[evidence_path]),
            }
        )
        notices.append(f"Source: {page.url}\n{notice}")
    files["LICENSE.txt"] = "\n".join(notices).encode()
    payload = {
        "schema_version": 1,
        "source": source.id,
        "url": source.url,
        "license": source.license.to_dict(),
        "license_sha256": _digest(files["LICENSE.txt"]),
        "pages": records,
    }
    revision = _digest(_json_bytes(payload))
    lock = {**payload, "snapshot": revision}
    bundles = _safe_file(manifest, root / "snapshots")
    bundles.mkdir(parents=True, exist_ok=True)
    destination = _safe_file(manifest, bundles / revision)
    with tempfile.TemporaryDirectory(prefix=".capture-", dir=root) as temporary:
        staging = Path(temporary) / "bundle"
        staging.mkdir()
        for relative, data in files.items():
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        if destination.exists():
            for relative, data in files.items():
                if _safe_file(manifest, destination / relative).read_bytes() != data:
                    raise SourceError(f"Existing snapshot bundle was modified: {destination}")
        else:
            staging.replace(destination)
        lock_path = _safe_file(manifest, root / "lock.json")
        staged_lock = Path(temporary) / "lock.json"
        staged_lock.write_bytes(_json_bytes(lock))
        staged_lock.replace(lock_path)
    return lock_path


def verify_snapshot(manifest: Manifest, source: WebSource) -> tuple[Path, dict[str, object]]:
    """Verify accepted bytes, page identities, extraction, and license evidence offline."""
    root = snapshot_root(manifest, source)
    lock_path = _safe_file(manifest, root / "lock.json")
    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SourceError(
            f"Missing or invalid snapshot; run `google-guides snapshot --source {source.id}`"
        ) from exc
    if not isinstance(lock, dict):
        raise SourceError("Snapshot lock must be an object")
    revision = lock.get("snapshot")
    payload = {key: value for key, value in lock.items() if key != "snapshot"}
    if not isinstance(revision, str) or not re.fullmatch(r"[a-f0-9]{64}", revision):
        raise SourceError("Snapshot lock has an invalid content hash")
    if revision != _digest(_json_bytes(payload)):
        raise SourceError("Snapshot lock content hash does not match")
    if (
        lock.get("schema_version") != 1
        or lock.get("source") != source.id
        or lock.get("url") != source.url
        or lock.get("license") != source.license.to_dict()
    ):
        raise SourceError("Snapshot source or license no longer matches the manifest")
    records = lock.get("pages")
    if not isinstance(records, list) or len(records) != len(source.pages):
        raise SourceError("Snapshot page enumeration no longer matches the manifest")
    bundle = _safe_file(manifest, root / "snapshots" / revision)
    notices: list[str] = []
    try:
        for page, record in zip(source.pages, records, strict=True):
            if not isinstance(record, dict) or any(
                record.get(key) != value for key, value in page.to_dict().items()
            ):
                raise SourceError("Snapshot page identity or selector changed")
            require_public_url(str(record.get("resolved_url", "")))
            data = _safe_file(manifest, bundle / page.path).read_bytes()
            if _digest(data) != record.get("sha256"):
                raise SourceError(f"Snapshot hash mismatch: {page.path}")
            html = data.decode("utf-8")
            article_html(html, page.selector)
            notice = _license_notice(html, source)
            evidence_path = f"licenses/{page.path.removesuffix('.html')}.txt"
            evidence = _safe_file(manifest, bundle / evidence_path).read_bytes()
            if (
                record.get("license_path") != evidence_path
                or _digest(evidence) != record.get("license_sha256")
                or evidence != notice.encode()
            ):
                raise SourceError(f"Snapshot license evidence mismatch: {page.path}")
            notices.append(f"Source: {page.url}\n{notice}")
        license_bytes = _safe_file(manifest, bundle / "LICENSE.txt").read_bytes()
        if (
            _digest(license_bytes) != lock.get("license_sha256")
            or license_bytes != "\n".join(notices).encode()
        ):
            raise SourceError("Snapshot source license was modified")
    except (OSError, UnicodeDecodeError) as exc:
        raise SourceError(f"Cannot read snapshot {source.id}: {exc}") from exc
    return bundle, lock
