#!/usr/bin/env python3
"""Validate the Horn of Africa Institute static site before deployment.

Checks:
1. Local href/src targets in HTML resolve to files in the repository.
2. Required Commentary catalogue entries remain present in publications.html.
3. Published Commentary landing pages and PDFs exist.

Uses only the Python standard library so GitHub Actions requires no package install.
"""

from __future__ import annotations

import html.parser
import pathlib
import sys
from urllib.parse import unquote, urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]

REQUIRED_COMMENTARY = (
    "How Renewed Red Sea Insecurity Is Reshaping Regional Alignments",
    "Toward a Gulf-Horn Partnership: Opportunities, Institutional Constraints, and Political Risks",
    "Why Competition over Red Sea Ports Has Become a Regional Power Contest",
    "What to Watch as Regional Powers Reassess Their Horn of Africa Strategies",
    "Sudan’s Worsening Crisis: Regional Consequences and the Limits of International Response",
)

REQUIRED_PUBLICATION_ASSETS = (
    "publications/hai-cm-2026-18.html",
    "publications/HAI-CM-2026-18.pdf",
    "publications/commentary/toward-a-gulf-horn-partnership.html",
    "publications/HAI-CM-2025-22.pdf",
)

SKIP_SCHEMES = {"http", "https", "mailto", "tel", "data", "javascript"}


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.targets: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value and name in {"href", "src"}:
                self.targets.append((name, value))


def resolve_local_target(source: pathlib.Path, raw: str) -> pathlib.Path | None:
    raw = raw.strip()
    if not raw or raw.startswith("#") or raw.startswith("//"):
        return None

    parts = urlsplit(raw)
    if parts.scheme.lower() in SKIP_SCHEMES:
        return None

    path = unquote(parts.path)
    if not path:
        return None

    if path.startswith("/"):
        candidate = ROOT / path.lstrip("/")
    else:
        candidate = source.parent / path

    candidate = candidate.resolve()
    try:
        candidate.relative_to(ROOT.resolve())
    except ValueError:
        return candidate

    if candidate.is_dir():
        candidate = candidate / "index.html"
    return candidate


def check_links() -> list[str]:
    errors: list[str] = []
    for html_file in sorted(ROOT.rglob("*.html")):
        parser = LinkParser()
        try:
            parser.feed(html_file.read_text(encoding="utf-8"))
        except Exception as exc:
            errors.append(f"HTML parse/read failure: {html_file.relative_to(ROOT)}: {exc}")
            continue

        for attr, raw in parser.targets:
            target = resolve_local_target(html_file, raw)
            if target is None:
                continue
            if not target.exists():
                errors.append(
                    f"Broken local {attr}: {html_file.relative_to(ROOT)} -> {raw} "
                    f"(expected {target.relative_to(ROOT) if target.is_relative_to(ROOT) else target})"
                )
    return errors


def check_publications() -> list[str]:
    errors: list[str] = []
    catalogue = ROOT / "publications.html"
    if not catalogue.exists():
        return ["Missing publications.html"]

    text = catalogue.read_text(encoding="utf-8")
    for title in REQUIRED_COMMENTARY:
        if title not in text:
            errors.append(f"Required Commentary entry missing from publications.html: {title}")

    for rel in REQUIRED_PUBLICATION_ASSETS:
        if not (ROOT / rel).exists():
            errors.append(f"Required published asset missing: {rel}")

    return errors


def main() -> int:
    errors = check_links() + check_publications()
    if errors:
        print("SITE VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    html_count = sum(1 for _ in ROOT.rglob("*.html"))
    print(f"SITE VALIDATION PASSED: {html_count} HTML files checked.")
    print("Required Commentary catalogue entries and publication assets are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
