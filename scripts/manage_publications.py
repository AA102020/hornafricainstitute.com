#!/usr/bin/env python3
"""Safely edit publication-series catalogue blocks in publications.html.

Supported series:
- research-papers
- working-papers
- policy-briefs
- commentary
- special-reports

The tool locates exactly one series section and rewrites only that section's
.series-titles block. Content outside the requested block must remain byte-for-byte
unchanged.
"""

from __future__ import annotations

import argparse
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "publications.html"
TITLES_START = '<div class="series-titles">'
SERIES = (
    "research-papers",
    "working-papers",
    "policy-briefs",
    "commentary",
    "special-reports",
)


def read_catalogue() -> str:
    if not CATALOGUE.exists():
        raise SystemExit("publications.html is missing")
    return CATALOGUE.read_text(encoding="utf-8")


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


def write_targeted(original: str, series: str, replacement_block: str) -> None:
    start, end = titles_bounds(original, series)
    updated = original[:start] + replacement_block + original[end:]
    if original[:start] != updated[:start]:
        raise SystemExit("Safety check failed before target block")
    suffix_start = start + len(replacement_block)
    if original[end:] != updated[suffix_start:]:
        raise SystemExit("Safety check failed after target block")
    CATALOGUE.write_text(updated, encoding="utf-8")


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
    else:
        if "<ol>" not in block or "</ol>" not in block:
            errors.append(f"Series list missing ordered-list structure: {series}")
    return errors


def check_all() -> int:
    text = read_catalogue()
    errors: list[str] = []
    for series in SERIES:
        errors.extend(check_series(text, series))
    if errors:
        print("PUBLICATION MANAGER CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PUBLICATION MANAGER CHECK PASSED: all targeted editing boundaries are valid.")
    return 0


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


def add_locked(series: str, title: str, subtitle: str | None) -> int:
    text = read_catalogue()
    start, end = titles_bounds(text, series)
    block = text[start:end]
    escaped = html.escape(title, quote=False)
    if title in block or escaped in block:
        print(f"No change: title already exists in {series}: {title}")
        return 0
    item = locked_item(title, subtitle)
    if "</ol>" not in block:
        raise SystemExit(f"Cannot add locked item: ordered list missing in {series}")
    insert_at = block.rfind("</ol>")
    new_block = block[:insert_at] + item + block[insert_at:]
    write_targeted(text, series, new_block)
    print(f"Added locked item to {series}: {title}")
    return 0


def remove_locked(block: str, title: str) -> str:
    escaped = re.escape(html.escape(title, quote=False))
    pattern = re.compile(
        r'\s*<li><span class="access-icon locked"[^>]*>.*?</span><cite>'
        + escaped
        + r'(?:<span class="report-subtitle">.*?</span>)?</cite></li>\s*',
        re.DOTALL,
    )
    return pattern.sub("\n", block, count=1)


def publish_commentary(title: str, href: str, code: str, date: str, author: str) -> int:
    text = read_catalogue()
    start, end = titles_bounds(text, "commentary")
    block = text[start:end]
    escaped_title = html.escape(title, quote=False)
    published_pattern = re.compile(
        r'<a class="published-entry"[^>]*>.*?<cite>' + re.escape(escaped_title) + r'</cite>.*?</a>',
        re.DOTALL,
    )
    if published_pattern.search(block):
        print(f"No change: Commentary is already published: {title}")
        return 0

    cleaned = remove_locked(block, title)
    entry = (
        f'\n            <a class="published-entry" href="{html.escape(href, quote=True)}">\n'
        '              <span class="publication-access"><span class="access-icon unlocked" role="img" '
        'aria-label="Publicly available" title="Publicly available">&#128275;</span></span>\n'
        f'              <span class="entry-type">{html.escape(code)} · {html.escape(date)}</span>\n'
        f'              <cite>{escaped_title}</cite>\n'
        f'              <span class="entry-author">{html.escape(author)}</span>\n'
        '            </a>'
    )
    ol_pos = cleaned.find("<ol>")
    new_block = cleaned[:ol_pos] + entry + "\n            " + cleaned[ol_pos:] if ol_pos >= 0 else cleaned + entry
    write_targeted(text, "commentary", new_block)
    print(f"Published Commentary catalogue entry: {title}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate all safe editing boundaries")
    sub = parser.add_subparsers(dest="command")

    add = sub.add_parser("add-locked", help="Add a locked title to one series")
    add.add_argument("--series", required=True, choices=SERIES)
    add.add_argument("--title", required=True)
    add.add_argument("--subtitle")

    pub = sub.add_parser("publish-commentary", help="Publish a Commentary catalogue entry")
    pub.add_argument("--title", required=True)
    pub.add_argument("--href", required=True)
    pub.add_argument("--code", required=True)
    pub.add_argument("--date", required=True)
    pub.add_argument("--author", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.check:
        return check_all()
    if args.command == "add-locked":
        return add_locked(args.series, args.title, args.subtitle)
    if args.command == "publish-commentary":
        return publish_commentary(args.title, args.href, args.code, args.date, args.author)
    print("Choose --check, add-locked, or publish-commentary.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
