#!/usr/bin/env python3
"""
OLDEV static-site builder.

Renders partials/header.html and partials/footer.html into every *.html page
under the site root (excluding partials/ itself), substituting:
  - {{T:key}} translatable strings (looked up by per-page locale in partials/strings.json)
  - {{ROOT}} document-relative path back to site root for the page being built
  - {{LOCALE}} the page's locale ("en" or "fr")
  - {{LANG_ALT_HREF}} document-relative URL of the same page in the OTHER locale
  - {{NAV_ACTIVE_*}} active-state attributes for the matching nav item, empty elsewhere

Idempotent: re-running on already-built pages produces zero diffs.

Usage:
    python build.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# --- Configuration ----------------------------------------------------------

SITE_ROOT = Path(__file__).resolve().parent
PARTIALS_DIR = SITE_ROOT / "partials"
STRINGS_PATH = PARTIALS_DIR / "strings.json"
HEADER_PATH = PARTIALS_DIR / "header.html"
FOOTER_PATH = PARTIALS_DIR / "footer.html"

# Page identity map. Keys are POSIX-style paths relative to site root.
# Values are (page_id, locale).
PAGES: dict[str, tuple[str, str]] = {
    "index.html":                                  ("home",    "en"),
    "crm-migration-service/index.html":            ("crm",     "en"),
    "contact.html":                                ("contact", "en"),
    "free-deliverability-audit/index.html":        ("audit",   "en"),
    "privacy/index.html":                          ("privacy", "en"),
    "404.html":                                    ("notfound","en"),
    "fr/index.html":                               ("home",    "fr"),
    "fr/crm-migration-service/index.html":         ("crm",     "fr"),
    "fr/contact.html":                             ("contact", "fr"),
    "fr/free-deliverability-audit/index.html":     ("audit",   "fr"),
    "fr/privacy/index.html":                       ("privacy", "fr"),
    "fr/404.html":                                 ("notfound","fr"),
}

# Marker comments delimiting the regions that get replaced on each build.
HEADER_MARKERS = ("<!-- HEADER:START -->", "<!-- HEADER:END -->")
FOOTER_MARKERS = ("<!-- FOOTER:START -->", "<!-- FOOTER:END -->")

# Active-state CSS-class snippet used in the header partial. Note the trailing
# space — the snippet is concatenated directly with the rest of the class list.
ACTIVE_SNIPPET = 'active '
INACTIVE_SNIPPET = ''

# Map page_id -> nav-active token name in the partial.
ACTIVE_TOKEN_BY_PAGE = {
    "home":    "NAV_ACTIVE_HOME",
    "crm":     "NAV_ACTIVE_CRM",
    "contact": "NAV_ACTIVE_CONTACT",
    "audit":   "NAV_ACTIVE_AUDIT",
}
ALL_ACTIVE_TOKENS = list(ACTIVE_TOKEN_BY_PAGE.values())


def doc_relative_root(page_path: str, locale: str) -> str:
    """Return the document-relative path back to the LOCALE root for a given page.

    FR pages live under fr/, so depth-from-locale-root = depth - 1.
    EN pages live at site root, so depth-from-locale-root = depth.

    This ensures FR nav links resolve to /fr/... not / (the EN tree).
    """
    depth = page_path.count("/")
    if locale == "fr":
        depth -= 1
    return "../" * depth if depth > 0 else "./"


def alt_locale_href(page_id: str, current_locale: str) -> str:
    """Document-relative href to the same page in the OTHER locale, computed
    from the current page's filesystem position. Emits clean URLs (no
    `.html`, no trailing `index.html`)."""
    # Page-id -> on-disk path (used to compute current page depth)
    en_disk = {
        "home":     "index.html",
        "crm":      "crm-migration-service/index.html",
        "contact":  "contact.html",
        "audit":    "free-deliverability-audit/index.html",
        "privacy":  "privacy/index.html",
        "notfound": "404.html",
    }
    # Page-id -> clean URL relative to language root (no .html, no index.html)
    en_clean = {
        "home":     "",
        "crm":      "crm-migration-service/",
        "contact":  "contact",
        "audit":    "free-deliverability-audit/",
        "privacy":  "privacy/",
        "notfound": "404",
    }
    disk_path = en_disk[page_id]
    clean_path = en_clean[page_id]
    if current_locale == "en":
        # current page is at <root>/<disk_path>; alt under fr/
        depth = disk_path.count("/")
        prefix = "../" * depth if depth else "./"
        target = f"fr/{clean_path}" if clean_path else "fr/"
        return f"{prefix}{target}"
    else:
        # current page is at <root>/fr/<disk_path>; alt at root
        depth = disk_path.count("/") + 1  # +1 because we're under fr/
        prefix = "../" * depth
        return f"{prefix}{clean_path}" if clean_path else prefix


# --- Token rendering --------------------------------------------------------

T_KEY_RE = re.compile(r"\{\{T:([a-zA-Z0-9_]+)\}\}")


def render_translations(
    text: str,
    strings: dict,
    locale: str,
    page_path: str,
    warnings: list[str],
) -> str:
    """Replace every {{T:key}} occurrence with the translation for `locale`."""

    def sub(m: re.Match) -> str:
        key = m.group(1)
        bucket = strings.get(locale, {})
        if key not in bucket:
            warnings.append(
                f"  ! [{locale}] missing translation key '{key}' (referenced in {page_path})"
            )
            return m.group(0)  # leave token untouched so it shows up in output
        return bucket[key]

    return T_KEY_RE.sub(sub, text)


def render_partial(
    partial_text: str,
    *,
    page_id: str,
    page_path: str,
    locale: str,
    strings: dict,
    warnings: list[str],
) -> str:
    """Render a partial (header or footer) for a given page."""
    out = partial_text
    out = out.replace("{{ROOT}}", doc_relative_root(page_path, locale))
    out = out.replace("{{LOCALE}}", locale)
    out = out.replace("{{LANG_ALT_HREF}}", alt_locale_href(page_id, locale))
    # Active-state tokens: matching one becomes ACTIVE_SNIPPET, others empty.
    active_token = ACTIVE_TOKEN_BY_PAGE.get(page_id)
    for token in ALL_ACTIVE_TOKENS:
        snippet = ACTIVE_SNIPPET if token == active_token else INACTIVE_SNIPPET
        out = out.replace("{{" + token + "}}", snippet)
    out = render_translations(out, strings, locale, page_path, warnings)
    return out


# --- Marker-region replacement ---------------------------------------------

def replace_marker_region(
    text: str, start_marker: str, end_marker: str, replacement: str, page_path: str
) -> tuple[str, bool]:
    """Replace everything strictly between start_marker and end_marker with
    replacement. Markers themselves are preserved. Returns (new_text, found)."""
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)
    if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
        return text, False
    before = text[: start_idx + len(start_marker)]
    after = text[end_idx:]
    # Insert with single newlines on either side for readable output
    new_text = f"{before}\n{replacement.rstrip()}\n{after}"
    return new_text, True


# --- Main build loop -------------------------------------------------------

def main() -> int:
    # Load resources
    if not STRINGS_PATH.is_file():
        print(f"ERROR: strings file not found at {STRINGS_PATH}", file=sys.stderr)
        return 2
    if not HEADER_PATH.is_file() or not FOOTER_PATH.is_file():
        print("ERROR: header.html or footer.html missing in partials/", file=sys.stderr)
        return 2

    strings = json.loads(STRINGS_PATH.read_text(encoding="utf-8"))
    header_partial = HEADER_PATH.read_text(encoding="utf-8")
    footer_partial = FOOTER_PATH.read_text(encoding="utf-8")

    # Sanity: verify both locales have all keys present in the partials.
    en_keys = set(strings.get("en", {}).keys())
    fr_keys = set(strings.get("fr", {}).keys())
    asym = (en_keys - fr_keys) | (fr_keys - en_keys)
    if asym:
        print(
            "ERROR: strings.json has asymmetric keys between en/fr:",
            sorted(asym), file=sys.stderr,
        )
        return 2

    warnings: list[str] = []
    summary: dict[str, list[str]] = {"en": [], "fr": []}
    pages_no_markers: list[str] = []

    # Walk every *.html under SITE_ROOT, skipping partials/.
    for html_path in sorted(SITE_ROOT.rglob("*.html")):
        rel = html_path.relative_to(SITE_ROOT).as_posix()
        if rel.startswith("partials/"):
            continue
        if rel not in PAGES:
            print(f"  ? skipping unmapped page: {rel}")
            continue

        page_id, locale = PAGES[rel]
        original = html_path.read_text(encoding="utf-8")

        rendered_header = render_partial(
            header_partial, page_id=page_id, page_path=rel,
            locale=locale, strings=strings, warnings=warnings,
        )
        rendered_footer = render_partial(
            footer_partial, page_id=page_id, page_path=rel,
            locale=locale, strings=strings, warnings=warnings,
        )

        new_text, found_header = replace_marker_region(
            original, HEADER_MARKERS[0], HEADER_MARKERS[1], rendered_header, rel,
        )
        new_text, found_footer = replace_marker_region(
            new_text, FOOTER_MARKERS[0], FOOTER_MARKERS[1], rendered_footer, rel,
        )

        if not (found_header and found_footer):
            pages_no_markers.append(rel)
            continue

        # Body-level translations (page authors can use {{T:key}} outside the
        # marker regions and have them resolve too).
        new_text = render_translations(new_text, strings, locale, rel, warnings)

        if new_text != original:
            html_path.write_text(new_text, encoding="utf-8")
            summary[locale].append(rel + "  (updated)")
        else:
            summary[locale].append(rel + "  (no change)")

    # --- Summary ------------------------------------------------------------
    print("\n=== Build summary ===")
    for locale_code in ("en", "fr"):
        print(f"\n[{locale_code}] {len(summary[locale_code])} page(s):")
        for line in summary[locale_code]:
            print(f"  - {line}")

    if pages_no_markers:
        print("\nPages without HEADER/FOOTER markers (skipped):")
        for p in pages_no_markers:
            print(f"  ! {p}")

    # --- Clean-URL self-check ----------------------------------------------
    # After build, scan every output HTML for internal href="…html" links
    # (excluding external URLs, mailto, tel, anchors, asset paths). Warn for
    # each match — clean URL mode is supposed to drop .html from internal hrefs.
    INTERNAL_HTML_RE = re.compile(
        r'href="(?!https?://|mailto:|tel:|#|/?(?:css|js|images)/)([^"]*\.html)(?:#[^"]*)?"',
        re.IGNORECASE,
    )
    clean_url_warnings: list[str] = []
    for html_path in sorted(SITE_ROOT.rglob("*.html")):
        rel = html_path.relative_to(SITE_ROOT).as_posix()
        if rel.startswith("partials/"):
            continue
        text = html_path.read_text(encoding="utf-8")
        for m in INTERNAL_HTML_RE.finditer(text):
            ref = m.group(1)
            # Skip the canonical/hreflang region — those are handled separately
            # by intent (they may use clean URLs but the regex sees the path).
            clean_url_warnings.append(f"  ! {rel}: internal href to .html → {ref}")

    if clean_url_warnings:
        print(f"\nClean-URL warnings ({len(clean_url_warnings)}):")
        for w in clean_url_warnings:
            print(w)
        warnings.extend(clean_url_warnings)

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(w)
        print("\nBuild completed WITH WARNINGS.")
        return 1
    print("\nBuild completed cleanly. Zero warnings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
