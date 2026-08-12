#!/usr/bin/env python3
"""Validate the Horn of Africa Institute static site before deployment.

Checks:
1. Local href/src targets in HTML resolve to files in the repository.
2. Required Commentary catalogue entries remain present in publications.html.
3. Published Commentary landing pages and PDFs exist.
4. Publication identifiers follow the institutional series policy.
5. The authoritative publication registry matches the website catalogue and assets.

Uses only the Python standard library so GitHub Actions requires no package install.
"""

from __future__ import annotations

import html.parser
import json
import pathlib
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = pathlib.Path(__file__).resolve().parents[1]
IDENTIFIER_POLICY = ROOT / "publication-identifiers.json"
PUBLICATION_REGISTRY = ROOT / "data" / "publications.json"

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
SERIES = (
    "research-papers",
    "working-papers",
    "policy-briefs",
    "commentary",
    "special-reports",
)
VALID_STATUSES = {"locked", "published"}


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


def load_identifier_policy() -> dict[str, dict[str, str]]:
    if not IDENTIFIER_POLICY.exists():
        raise FileNotFoundError("publication-identifiers.json is missing")
    return json.loads(IDENTIFIER_POLICY.read_text(encoding="utf-8"))


def load_publication_registry() -> dict:
    if not PUBLICATION_REGISTRY.exists():
        raise FileNotFoundError("data/publications.json is missing")
    return json.loads(PUBLICATION_REGISTRY.read_text(encoding="utf-8"))


def check_identifier_policy() -> list[str]:
    errors: list[str] = []
    try:
        policy = load_identifier_policy()
    except Exception as exc:
        return [f"Identifier policy cannot be loaded: {exc}"]

    for series in SERIES:
        if series not in policy:
            errors.append(f"Identifier policy missing series: {series}")
            continue
        rule = policy[series]
        for field in ("label", "prefix", "format", "pattern"):
            if not rule.get(field):
                errors.append(f"Identifier policy missing {field} for {series}")

    expected_formats = {
        "research-papers": "HAI-RP-YYYY-##",
        "working-papers": "HAI-WP-YYYY-##",
        "policy-briefs": "HAI-PB-YYYY-##",
        "commentary": "HAI-CM-YYYY-##",
        "special-reports": "HAI-SR-YYYY-##",
    }
    for series, expected in expected_formats.items():
        if policy.get(series, {}).get("format") != expected:
            errors.append(
                f"Identifier format mismatch for {series}: expected {expected}, "
                f"found {policy.get(series, {}).get('format')}"
            )
    return errors


def check_registry(catalogue_text: str) -> list[str]:
    errors: list[str] = []
    try:
        registry = load_publication_registry()
        policy = load_identifier_policy()
    except Exception as exc:
        return [f"Publication registry cannot be validated: {exc}"]

    if registry.get("schema_version") != 1:
        errors.append("Publication registry schema_version must be 1")
    if registry.get("identifier_policy") != "publication-identifiers.json":
        errors.append("Publication registry identifier_policy must reference publication-identifiers.json")

    publications = registry.get("publications")
    if not isinstance(publications, list):
        return errors + ["Publication registry publications must be a list"]

    seen_titles: set[tuple[str, str]] = set()
    seen_ids: set[str] = set()

    for index, item in enumerate(publications, start=1):
        context = f"Registry item {index}"
        if not isinstance(item, dict):
            errors.append(f"{context} must be an object")
            continue

        series = item.get("series")
        title = item.get("title")
        status = item.get("status")
        pub_id = item.get("id")

        if series not in SERIES:
            errors.append(f"{context} has invalid series: {series}")
        if not isinstance(title, str) or not title.strip():
            errors.append(f"{context} has no title")
            continue
        if status not in VALID_STATUSES:
            errors.append(f"{context} has invalid status: {status}")

        title_key = (str(series), title)
        if title_key in seen_titles:
            errors.append(f"Duplicate registry title in series {series}: {title}")
        seen_titles.add(title_key)

        if title not in catalogue_text:
            errors.append(f"Registry title missing from publications.html: {title}")

        subtitle = item.get("subtitle")
        if subtitle and subtitle not in catalogue_text:
            errors.append(f"Registry subtitle missing from publications.html: {subtitle}")

        if pub_id is not None:
            if not isinstance(pub_id, str):
                errors.append(f"{context} identifier must be a string or null")
            else:
                if pub_id in seen_ids:
                    errors.append(f"Duplicate publication identifier in registry: {pub_id}")
                seen_ids.add(pub_id)
                if series in policy:
                    pattern = re.compile(policy[series]["pattern"])
                    if not pattern.fullmatch(pub_id):
                        errors.append(f"Identifier {pub_id} does not match series {series}")
                if pub_id not in catalogue_text:
                    errors.append(f"Published identifier missing from publications.html: {pub_id}")

        landing_page = item.get("landing_page")
        pdf = item.get("pdf")
        author = item.get("author")
        publication_date = item.get("publication_date")

        if status == "published":
            for field_name, value in (
                ("id", pub_id),
                ("author", author),
                ("publication_date", publication_date),
                ("landing_page", landing_page),
                ("pdf", pdf),
            ):
                if not value:
                    errors.append(f"Published registry item missing {field_name}: {title}")
            for field_name, value in (("landing_page", landing_page), ("pdf", pdf)):
                if value and not (ROOT / value).exists():
                    errors.append(f"Published registry {field_name} does not exist for {title}: {value}")
        elif status == "locked":
            if pub_id is not None or publication_date is not None or landing_page is not None or pdf is not None:
                errors.append(f"Locked registry item has publication metadata assigned: {title}")

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

    try:
        policy = load_identifier_policy()
    except Exception as exc:
        errors.append(f"Identifier policy cannot be loaded: {exc}")
        return errors

    all_codes = re.findall(r"HAI-[A-Z]{2}-[0-9]{4}-[0-9]{2}", text)
    allowed_patterns = [re.compile(rule["pattern"]) for rule in policy.values()]
    for code in all_codes:
        if not any(pattern.fullmatch(code) for pattern in allowed_patterns):
            errors.append(f"Invalid HAI publication identifier in publications.html: {code}")

    errors.extend(check_registry(text))
    return errors


def main() -> int:
    errors = check_links() + check_identifier_policy() + check_publications()
    if errors:
        print("SITE VALIDATION FAILED")
        for error in errors:
            print(f"- {error}")
        return 1

    html_count = sum(1 for _ in ROOT.rglob("*.html"))
    print(f"SITE VALIDATION PASSED: {html_count} HTML files checked.")
    print("Publication catalogue, registry, assets, and identifier policy are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
