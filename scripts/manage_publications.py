#!/usr/bin/env python3
"""Safely manage HAI publication records and catalogue entries.

This tool treats data/publications.json as the authoritative registry and keeps
publications.html synchronized with it. Mutating commands compute both changes
in memory, validate both representations, then write both files together.

Supported series:
- research-papers
- working-papers
- policy-briefs
- commentary
- special-reports

Publication identifiers are governed by publication-identifiers.json.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import sys
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "publications.html"
REGISTRY = ROOT / "data" / "publications.json"
IDENTIFIER_POLICY = ROOT / "publication-identifiers.json"
TITLES_START = '<div class="series-titles">'
SERIES = (
    "research-papers",
    "working-papers",
    "policy-briefs",
    "commentary",
    "special-reports",
)


def load_identifier_policy() -> dict[str, dict[str, str]]:
    if not IDENTIFIER_POLICY.exists():
        raise SystemExit("publication-identifiers.json is missing")
    policy = json.loads(IDENTIFIER_POLICY.read_text(encoding="utf-8"))
    missing = [series for series in SERIES if series not in policy]
    extra = [series for series in policy if series not in SERIES]
    if missing or extra:
        raise SystemExit(f"Identifier policy series mismatch. Missing={missing}, extra={extra}")
    return policy


def validate_identifier(series: str, code: str) -> str:
    rule = load_identifier_policy()[series]
    if re.fullmatch(rule["pattern"], code) is None:
        raise SystemExit(
            f"Invalid identifier for {series}: {code}. Required format: {rule['format']}"
        )
    return code


def read_catalogue() -> str:
    if not CATALOGUE.exists():
        raise SystemExit("publications.html is missing")
    return CATALOGUE.read_text(encoding="utf-8")


def load_registry() -> dict[str, Any]:
    if not REGISTRY.exists():
        raise SystemExit("data/publications.json is missing")
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if not isinstance(data.get("publications"), list):
        raise SystemExit("Registry must contain a publications array")
    return data


def article_start_marker(series: str) -> str:
    return f'<article class="series-section" id="{series}">'


def article_bounds(text: str, series: str) -> tuple[int, int]:
    marker = article_start_marker(series)
    start = text.find(marker)
    if start < 0 or text.count(marker) != 1:
        raise SystemExit(f"Could not uniquely locate series section: {series}")
    next_positions = []
    for candidate in SERIES:
        if candidate == series:
            continue
        pos = text.find(article_start_marker(candidate), start + len(marker))
        if pos >= 0:
            next_positions.append(pos)
    end = min(next_positions) if next_positions else text.find("</section>", start)
    if end < 0 or end <= start:
        raise SystemExit(f"Could not locate end of series section: {series}")
    return start, end


def titles_bounds(text: str, series: str) -> tuple[int, int]:
    article_start, article_end = article_bounds(text, series)
    titles_start = text.find(TITLES_START, article_start, article_end)
    if titles_start < 0:
        raise SystemExit(f"Could not locate series-titles block: {series}")
    content_start = titles_start + len(TITLES_START)
    titles_end = text.find("</div>", content_start, article_end)
    if titles_end < 0:
        raise SystemExit(f"Could not locate end of series-titles block: {series}")
    return content_start, titles_end


def replace_targeted(original: str, series: str, replacement_block: str) -> str:
    start, end = titles_bounds(original, series)
    updated = original[:start] + replacement_block + original[end:]
    suffix_start = start + len(replacement_block)
    if original[:start] != updated[:start] or original[end:] != updated[suffix_start:]:
        raise SystemExit("Safety check failed: content outside target series would change")
    return updated


def locked_item(title: str, subtitle: str | None = None) -> str:
    escaped_title = html.escape(title, quote=False)
    subtitle_html = ""
    if subtitle:
        subtitle_html = f'<span class="report-subtitle">{html.escape(subtitle, quote=False)}</span>'
    return (
        '              <li><span class="access-icon locked" role="img" '
        'aria-label="Not publicly available" title="Not publicly available">&#128274;</span>'
        f'<cite>{escaped_title}{subtitle_html}</cite></li>\n'
    )


def remove_locked(block: str, title: str) -> str:
    escaped = re.escape(html.escape(title, quote=False))
    pattern = re.compile(
        r'\s*<li><span class="access-icon locked"[^>]*>.*?</span><cite>'
        + escaped
        + r'(?:<span class="report-subtitle">.*?</span>)?</cite></li>\s*',
        re.DOTALL,
    )
    return pattern.sub("\n", block, count=1)


def registry_index(registry: dict[str, Any], series: str, title: str) -> int | None:
    matches = [
        i for i, item in enumerate(registry["publications"])
        if item.get("series") == series and item.get("title") == title
    ]
    if len(matches) > 1:
        raise SystemExit(f"Duplicate registry records for {series}: {title}")
    return matches[0] if matches else None


def validate_registry(registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    policy = load_identifier_policy()
    seen_codes: set[str] = set()
    seen_titles: set[tuple[str, str]] = set()
    for i, item in enumerate(registry["publications"], start=1):
        series = item.get("series")
        title = item.get("title")
        status = item.get("status")
        code = item.get("id")
        key = (series, title)
        if series not in SERIES:
            errors.append(f"Registry record {i} has invalid series: {series}")
        if not title:
            errors.append(f"Registry record {i} has no title")
        elif key in seen_titles:
            errors.append(f"Duplicate registry title in {series}: {title}")
        else:
            seen_titles.add(key)
        if status not in {"locked", "published"}:
            errors.append(f"Registry record {i} has invalid status: {status}")
        if code:
            if code in seen_codes:
                errors.append(f"Duplicate publication identifier: {code}")
            seen_codes.add(code)
            if series in policy and re.fullmatch(policy[series]["pattern"], code) is None:
                errors.append(f"Identifier {code} does not match series {series}")
        if status == "locked":
            for field in ("id", "author", "publication_date", "landing_page", "pdf"):
                if item.get(field) is not None:
                    errors.append(f"Locked registry item has {field}: {title}")
        if status == "published":
            for field in ("id", "author", "publication_date", "landing_page", "pdf"):
                if not item.get(field):
                    errors.append(f"Published registry item missing {field}: {title}")
    return errors


def validate_catalogue_against_registry(text: str, registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for item in registry["publications"]:
        series = item["series"]
        title = item["title"]
        start, end = article_bounds(text, series)
        block = text[start:end]
        escaped_title = html.escape(title, quote=False)
        if title not in block and escaped_title not in block:
            errors.append(f"Registry title missing from {series} catalogue: {title}")
        if item.get("subtitle"):
            subtitle = item["subtitle"]
            if subtitle not in block and html.escape(subtitle, quote=False) not in block:
                errors.append(f"Registry subtitle missing from {series} catalogue: {subtitle}")
        if item["status"] == "published":
            for field in ("id", "author", "landing_page"):
                value = item[field]
                if value not in block and html.escape(value, quote=True) not in block:
                    errors.append(f"Published registry {field} missing from catalogue for {title}: {value}")
    return errors


def check_series(text: str, series: str) -> list[str]:
    errors: list[str] = []
    article_start, article_end = article_bounds(text, series)
    content_start, content_end = titles_bounds(text, series)
    if not (article_start < content_start < content_end < article_end):
        errors.append(f"Boundary inconsistency: {series}")
    block = text[content_start:content_end]
    if series == "commentary":
        if "published-entry" not in block:
            errors.append("Commentary has no published entries")
        if "access-icon locked" not in block:
            errors.append("Commentary has no locked entries")
    elif "<ol>" not in block or "</ol>" not in block:
        errors.append(f"Series list missing ordered-list structure: {series}")
    return errors


def check_all() -> int:
    text = read_catalogue()
    registry = load_registry()
    errors: list[str] = []
    for series in SERIES:
        errors.extend(check_series(text, series))
    errors.extend(validate_registry(registry))
    errors.extend(validate_catalogue_against_registry(text, registry))
    if errors:
        print("PUBLICATION MANAGER CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PUBLICATION MANAGER CHECK PASSED: registry, catalogue, boundaries, and identifiers are consistent.")
    return 0


def validate_candidate(text: str, registry: dict[str, Any]) -> None:
    errors = validate_registry(registry) + validate_catalogue_against_registry(text, registry)
    for series in SERIES:
        errors.extend(check_series(text, series))
    if errors:
        raise SystemExit("Candidate publication update failed validation:\n- " + "\n- ".join(errors))


def write_atomic(text: str, registry: dict[str, Any]) -> None:
    validate_candidate(text, registry)
    # Each local write is atomic via replace; both candidates are fully validated first.
    catalogue_tmp = CATALOGUE.with_suffix(".html.tmp")
    registry_tmp = REGISTRY.with_suffix(".json.tmp")
    catalogue_tmp.write_text(text, encoding="utf-8")
    registry_tmp.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    catalogue_tmp.replace(CATALOGUE)
    registry_tmp.replace(REGISTRY)


def add_locked(series: str, title: str, subtitle: str | None) -> int:
    text = read_catalogue()
    registry = load_registry()
    start, end = titles_bounds(text, series)
    block = text[start:end]
    escaped = html.escape(title, quote=False)
    existing_idx = registry_index(registry, series, title)
    in_html = title in block or escaped in block

    if existing_idx is not None or in_html:
        if existing_idx is not None and in_html:
            print(f"No change: title already exists in registry and {series}: {title}")
            return 0
        raise SystemExit(f"Registry/catalogue mismatch for existing title: {title}")

    if "</ol>" not in block:
        raise SystemExit(f"Cannot add locked item: ordered list missing in {series}")
    insert_at = block.rfind("</ol>")
    new_block = block[:insert_at] + locked_item(title, subtitle) + block[insert_at:]
    new_text = replace_targeted(text, series, new_block)

    registry["publications"].append({
        "id": None,
        "series": series,
        "title": title,
        "subtitle": subtitle,
        "author": None,
        "publication_date": None,
        "status": "locked",
        "landing_page": None,
        "pdf": None,
    })
    write_atomic(new_text, registry)
    print(f"Added locked publication atomically to registry and {series}: {title}")
    return 0


def display_date(iso_date: str) -> str:
    parsed = dt.date.fromisoformat(iso_date)
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def publish_commentary(
    title: str,
    href: str,
    code: str,
    date: str,
    author: str,
    pdf: str,
    display_date_override: str | None,
) -> int:
    validate_identifier("commentary", code)
    try:
        dt.date.fromisoformat(date)
    except ValueError as exc:
        raise SystemExit("--date must use YYYY-MM-DD") from exc

    text = read_catalogue()
    registry = load_registry()
    idx = registry_index(registry, "commentary", title)
    if idx is None:
        raise SystemExit(f"Commentary must exist in registry before publication: {title}")
    record = registry["publications"][idx]
    if record.get("status") == "published":
        expected = {"id": code, "author": author, "publication_date": date, "landing_page": href, "pdf": pdf}
        if all(record.get(k) == v for k, v in expected.items()):
            print(f"No change: Commentary is already published with matching metadata: {title}")
            return 0
        raise SystemExit(f"Commentary is already published with different metadata: {title}")

    duplicate = [item for item in registry["publications"] if item.get("id") == code]
    if duplicate:
        raise SystemExit(f"Identifier already assigned in registry: {code}")

    start, end = titles_bounds(text, "commentary")
    block = text[start:end]
    cleaned = remove_locked(block, title)
    if cleaned == block:
        raise SystemExit(f"Locked Commentary entry not found in catalogue: {title}")

    shown_date = display_date_override or display_date(date)
    escaped_title = html.escape(title, quote=False)
    entry = (
        f'\n            <a class="published-entry" href="{html.escape(href, quote=True)}">\n'
        '              <span class="publication-access"><span class="access-icon unlocked" role="img" '
        'aria-label="Publicly available" title="Publicly available">&#128275;</span></span>\n'
        f'              <span class="entry-type">{html.escape(code)} · {html.escape(shown_date)}</span>\n'
        f'              <cite>{escaped_title}</cite>\n'
        f'              <span class="entry-author">{html.escape(author)}</span>\n'
        '            </a>'
    )
    ol_pos = cleaned.find("<ol>")
    new_block = cleaned[:ol_pos] + entry + "\n            " + cleaned[ol_pos:] if ol_pos >= 0 else cleaned + entry
    new_text = replace_targeted(text, "commentary", new_block)

    record.update({
        "id": code,
        "author": author,
        "publication_date": date,
        "status": "published",
        "landing_page": href,
        "pdf": pdf,
    })
    write_atomic(new_text, registry)
    print(f"Published Commentary atomically in registry and catalogue: {title}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate registry/catalogue synchronization")
    sub = parser.add_subparsers(dest="command")

    add = sub.add_parser("add-locked", help="Add a locked publication to registry and catalogue")
    add.add_argument("--series", required=True, choices=SERIES)
    add.add_argument("--title", required=True)
    add.add_argument("--subtitle")

    pub = sub.add_parser("publish-commentary", help="Publish an existing locked Commentary atomically")
    pub.add_argument("--title", required=True)
    pub.add_argument("--href", required=True)
    pub.add_argument("--pdf", required=True)
    pub.add_argument("--code", required=True)
    pub.add_argument("--date", required=True, help="Publication date in YYYY-MM-DD format")
    pub.add_argument("--display-date", help="Optional display wording, e.g. 'Revised August 11, 2026'")
    pub.add_argument("--author", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.check:
        return check_all()
    if args.command == "add-locked":
        return add_locked(args.series, args.title, args.subtitle)
    if args.command == "publish-commentary":
        return publish_commentary(
            args.title, args.href, args.code, args.date, args.author, args.pdf, args.display_date
        )
    print("Choose --check, add-locked, or publish-commentary.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
