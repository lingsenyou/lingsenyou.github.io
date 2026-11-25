"""Render the four static publication lists from data/publications.json.

Run after editing the records; pass --check in CI to detect stale generated cards.
Only the HTML between the two publication-card comments is generated.
"""
import argparse
from html import escape
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BEGIN = "<!-- BEGIN GENERATED PUBLICATION CARDS -->"
END = "<!-- END GENERATED PUBLICATION CARDS -->"
LANG_NAMES = {
    "en": {"Lingsen You": "L. You", "Li Shen": "L. Shen", "Junbo Ge": "J.B. Ge"},
    "zh": {"Lingsen You": "游凌森", "Li Shen": "沈雳", "Junbo Ge": "葛均波"},
}


def link(label, href, css=None, *, download=None, tip=None):
    attrs = [f'href="{escape(href, quote=True)}"']
    if css:
        attrs.append(f'class="{css}"')
    if download:
        attrs.append(f'download="{escape(download, quote=True)}"')
    elif href.startswith("https://"):
        attrs += ['target="_blank"', 'rel="noopener"']
    if tip:
        attrs.append(f'title="{escape(tip, quote=True)}"')
    return '<a ' + ' '.join(attrs) + '>' + escape(label) + '</a>'


def byline(raw, lang, full=False):
    names = [n.rstrip("#*") for n in raw]
    indices = range(len(raw))
    if not full and len(raw) > 3:
        indices = sorted({0, names.index("Lingsen You"), len(raw) - 1})
    parts, previous = [], -1
    for ix in indices:
        if ix - previous > 1:
            parts.append("…")
        name = names[ix]
        label = name if full else LANG_NAMES[lang].get(name, f"{name[0]}. {name.split()[-1]}")
        label = escape(label)
        if name == "Lingsen You":
            label = f"<strong>{label}</strong>"
        if full and raw[ix] != name:
            label += f"<sup>{escape(raw[ix][len(name):])}</sup>"
        parts.append(label)
        previous = ix
    return (", " if full or lang == "en" else "，").join(parts)


def badge(item):
    css = "pc-badge pc-" + item["kind"]
    if item.get("href"):
        return link(item["label"], item["href"], css, tip=item.get("title"))
    tip = f' title="{escape(item["title"], quote=True)}"' if "title" in item else ""
    return f'<span class="{css}"{tip}>{escape(item["label"])}</span>'


def card(record, lang, on_home):
    zh = lang == "zh"
    local = record[lang]
    key = record["id"]
    title = record["title"]
    title_attrs = ' lang="en" translate="no"' if zh else ''
    url = record.get("url")
    anchor = ("/zh" if zh else "") + "/publications/#" + key
    title_link = link(title, url or anchor) if url or on_home else escape(title)
    journal = next(b["label"] for b in local["badges"] if b["kind"] == "journal")
    if url:
        img = record["image"]
        image_label = ("阅读：" if zh else "Read: ") + title
        media = (
            f'<a class="pc-media-link" href="{escape(url, quote=True)}" target="_blank" rel="noopener" '
            f'aria-label="{escape(image_label, quote=True)}">'
            '<picture>'
            f'<source type="image/webp" srcset="{escape(img["srcset"], quote=True)}" '
            'sizes="(max-width: 600px) 220px, (max-width: 1000px) 175px, 220px">'
            f'<img src="{escape(img["src"], quote=True)}" alt="{escape(local["alt"], quote=True)}" '
            f'width="{img["width"]}" height="{img["height"]}" loading="lazy" decoding="async">'
            '</picture></a>'
        )
    else:
        genre = record["articleType"][lang]
        media = f'<div class="journal-label"><strong lang="en">{escape(journal)}</strong><small>{escape(genre)}</small></div>'
    lines = [
        f'<article class="pub-card pub-item" id="{key}" data-status="{record["status"]}">',
        f'  <div class="pc-media">{media}</div>',
        '  <div class="pc-body">',
        f'    <h3 class="pc-title"{title_attrs}>{title_link}</h3>',
    ]
    lines.append(f'    <p class="pc-authors">{byline(record["authors"], lang)}</p>')
    order = {"journal": 0, "if": 1, "status": 2, "publisher": 3, "tier": 4, "honor": 5, "award": 6}
    lines.append('    <div class="pc-badges">' + ' '.join(badge(b) for b in sorted(local["badges"], key=lambda b: order[b["kind"]])) + '</div>')
    actions = []
    if url:
        label = ("预印本" if zh else "Preprint") if record["status"] == "preprint" else ("阅读原文" if zh else "Article")
        actions.append(link(label, url, "pc-link"))
        actions.append(link("PDF", record["pdf"], "pc-link pc-pdf pdf-link", download=record.get("download")))
    lines.append('    <div class="pc-actions">' + ' '.join(actions) + '</div>')
    lines += [
        '    <details class="pc-details">',
        '      <summary>' + ("完整署名与研究简介" if zh else "Full authors and study details") + '</summary>',
        f'      <p class="authors">{byline(record["authors"], lang, full=True)}</p>',
    ]
    if local.get("citation"):
        lines.append(f'      <p class="pc-citation">{escape(local["citation"])}</p>')
    # Only these two fields are curated inline HTML, retained for source links and author symbols.
    lines.append(f'      <p class="summary">{local["summaryHtml"]}</p>')
    for note in local.get("notesHtml", []):
        lines.append(f'      <p class="pc-note">{note}</p>')
    links = []
    if local.get("identifierText"):
        links.append(link(local["identifierText"], url, "pc-id"))
    links.extend(link(v["label"], v["href"]) for v in local.get("extraLinks", []))
    if links:
        lines.append('      <p class="pc-sources">' + ' · '.join(links) + '</p>')
    lines += ['    </details>', '  </div>', '</article>']
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    check = parser.parse_args().check
    records = json.loads((ROOT / "data/publications.json").read_text(encoding="utf-8"))
    ids = [rec["id"] for rec in records]
    if len(ids) != len(set(ids)) or not all(re.fullmatch(r"paper-[a-z0-9-]+", k) for k in ids):
        raise ValueError("Duplicate or invalid publication anchor")
    stale = []
    for lang in ("en", "zh"):
        for home in (True, False):
            file = ROOT / ("" if lang == "en" else "zh") / ("" if home else "publications") / "index.html"
            source = file.read_bytes()
            nl = "\r\n" if b"\r\n" in source else "\n"
            original = source.decode("utf-8")
            if original.count(BEGIN) != 1 or original.count(END) != 1:
                raise ValueError(f"Ambiguous or missing generated region: {file}")
            before, after_begin = original.split(BEGIN)
            _, after = after_begin.split(END)
            cards = "\n".join(card(r, lang, home) for r in records)
            region = '\n<div class="pub-list pc-list">\n' + cards + '\n</div>\n'
            rendered = before + BEGIN + region.replace("\n", nl) + END + after
            if rendered != original:
                if check:
                    stale.append(str(file.relative_to(ROOT)))
                else:
                    file.write_bytes(rendered.encode("utf-8"))
    if stale:
        sys.exit("Stale publication cards: " + ", ".join(stale))
    print(f"Verified {len(records)} records on four pages." if check else f"Rendered {len(records)} records on four pages.")


if __name__ == "__main__":
    main()
