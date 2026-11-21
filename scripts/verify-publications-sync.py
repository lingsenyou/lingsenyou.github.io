"""Audit static bilingual publication cards against their pre-redesign Git revision.

Requires BeautifulSoup and Pillow. Run from any directory; no network or writes.
"""
import argparse
import json
from pathlib import Path
import subprocess
from urllib.parse import urljoin, urlsplit, unquote

from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://lingsenyou.com"
ROUTES = ("/", "/publications/", "/zh/", "/zh/publications/")
ACCEPTED = "paper-gpnmb-restenosis"
PREPRINT = "paper-2609-14709"


def load(route, ref=None):
    path = (route + "index.html").lstrip("/")
    raw = (subprocess.check_output(["git", "show", f"{ref}:{path}"], cwd=ROOT)
           if ref else (ROOT / path).read_bytes())
    return BeautifulSoup(raw.decode("utf-8"), "html.parser")


def contents(node):
    return " ".join(node.get_text().split()) if node else ""


def texts(node, selector):
    return [contents(n) for n in node.select(selector)]


def required(node, selector, key):
    matches = node.select(selector)
    assert len(matches) == 1, (key, selector, len(matches))
    return matches[0]


def absolute(route, href):
    return urljoin(BASE + route, href)


def local_asset(route, href):
    url = urlsplit(absolute(route, href))
    assert url.netloc == "lingsenyou.com", href
    return ROOT / unquote(url.path).lstrip("/")


def links(card, route):
    return {absolute(route, a["href"]) for a in card.select("a[href]")}


def old_cards(page):
    return page.select(".pub-item") or page.select(".pub-list > article")


def graph(page):
    return json.loads(required(page, 'script[type="application/ld+json"]', "JSON-LD").string)["@graph"]


def verify_image(media, old, route, old_route, key):
    pic = required(media, "picture", key)
    img = required(pic, "img", key)
    assert img["alt"].strip() and img.get("loading") == "lazy" and img.get("decoding") == "async", key
    assert absolute(route, img["src"]) == absolute(old_route, old.img["src"]), (key, "image")
    assert (img["width"], img["height"]) == (old.img["width"], old.img["height"]), key
    assert local_asset(route, img["src"]).is_file(), key
    src = required(pic, 'source[type="image/webp"]', key)
    variants = [s.strip().split() for s in src["srcset"].split(",")]
    assert src.get("sizes") and [w for _, w in variants] == ["320w", "640w"], key
    for path, width in variants:
        with Image.open(local_asset(route, path)) as im:
            im.load()
            assert im.format == "WEBP" and im.width == int(width[:-1]), (key, path)
            assert abs(im.height - im.width * int(img["height"]) / int(img["width"])) <= 0.51, (key, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="8717f0d")
    args = parser.parse_args()
    old = {r: load(r, args.baseline_ref) for r in ROUTES}
    expected = {r: old_cards(p) for r, p in old.items()}
    ids = [c["id"] for c in expected["/zh/"]]
    assert len(ids) == len(set(ids)) == 12 and ids[0] == ACCEPTED and ids[-1] == PREPRINT, ids
    now = {r: load(r) for r in ROUTES}
    for route, page in now.items():
        zh = route.startswith("/zh/")
        home, listing = ("/zh/", "/zh/publications/") if zh else ("/", "/publications/")
        canonical_english = now["/"].select(".pc-list > article.pub-card")
        cards = page.select(".pub-list.pc-list > article.pub-card.pub-item")
        assert [c.get("id") for c in cards] == ids and len(old_cards(page)) == len(cards), (route, "identity/order")
        before_graph, new_graph = graph(old[route]), graph(page)
        for record in before_graph:
            # The old EN JSON-LD had a truncated/incorrect month for Research. The
            # Chinese record already carried the full date; all four should now agree.
            if record.get("@id") == "https://doi.org/10.34133/research.0974" and record.get("datePublished") == "2025-01":
                record["datePublished"] = "2025-10-29"
            # The homepages now cite their biographical sources separately from
            # publication cards. Keep these intentional changes narrow and visible.
            if route == home and record.get("@id") == BASE + home + "#webpage":
                record["dateModified"] = "2026-11-21"
                record["citation"] = [
                    "https://doi.org/10.1093/eurheartj/ehag783",
                    "https://shmc.fudan.edu.cn/news/2026/0529/c1893a149384/page.htm",
                ]
                intro = required(page, "#physician-profile", route)
                if intro.name != "section":
                    intro = intro.find_parent("section")
                assert intro and set(record["citation"]) <= links(intro, route), route
            if route == "/zh/" and record.get("@id") == BASE + "/#person":
                record["jobTitle"] = ["心内科医师" if t == "Physician" else t for t in record["jobTitle"]]
        assert before_graph == new_graph, (route, "unrelated JSON-LD changes")
        nodes = {n["@id"]: n for n in new_graph if "@id" in n}
        counters = {"local": 0, "official": 0, "accepted": 0}
        item_uris = []
        for i, card in enumerate(cards):
            pid = ids[i]
            key = f"{route}#{pid}"
            lead = expected[home][i]
            detail = expected[listing][i]
            body = required(card, ":scope > .pc-body", key)
            media = required(card, ":scope > .pc-media", key)
            child_classes = [n.get("class", [""])[0] for n in body.find_all(recursive=False)]
            assert child_classes == (["pc-title"] + (["pc-subtitle"] if zh else []) +
                                     ["pc-authors", "pc-badges", "pc-actions", "pc-details"]), (key, child_classes)
            title = required(body, "h3.pc-title", key)
            assert contents(title) in {contents(c.select_one(".pc-title,.pub-title,h3")) for c in (lead, detail)}, (key, "title")
            if zh:
                assert contents(required(body, ".pc-subtitle[lang=en]", key)) == contents(canonical_english[i].h3), (key, "subtitle")
            folded = required(body, "details.pc-details:not([open])", key)
            assert contents(required(folded, "summary", key)), key
            full = contents(required(folded, ".authors", key))
            assert full and full == contents(required(detail, ".authors", key)), (key, "full authors and their order")
            assert contents(required(folded, ".summary", key)) == contents(required(detail, ".summary", key)), (key, "study summary")
            byline = required(body, ".pc-authors", key)
            assert contents(required(byline, "strong", key)) == ("游凌森" if zh else "L. You"), (key, "highlighted author")
            if pid == PREPRINT:
                assert card["data-status"] == "preprint" and contents(byline).startswith("T. Cui") and contents(byline).endswith("Y. Wu"), key
            elif pid != ACCEPTED:
                assert card["data-status"] == "published", key
            badge_groups = (("journal", ".badge-journal"), ("if", ".badge-if"), ("status", ".badge-status"),
                            ("publisher", ".badge-publisher"), ("honor", ".badge-wcj"),
                            ("tier", ".badge-tier"), ("award", ".badge-highlight"))
            for group, legacy in badge_groups:
                new_selector = ".pc-badges > .pc-" + group
                assert sorted(texts(body, new_selector)) == sorted(texts(lead, legacy + "," + new_selector)), (key, group)
            actions = required(body, ".pc-actions", key)
            current = links(card, route)
            for old_route, ref in [(home, lead), (listing, detail)]:
                missing = links(ref, old_route) - current
                if pid == ACCEPTED and route == listing:
                    missing.discard(absolute(home, listing + "#" + pid))  # detail page does not link to itself
                assert not missing, (key, "missing links", sorted(missing))
            if pid == ACCEPTED:
                counters["accepted"] += 1
                assert card["data-status"] == "accepted" and not actions.select("a") and not media.select("img"), key
                assert contents(required(media, ".journal-label strong", key)) == "Genes & Diseases", key
                assert contents(byline) == ("游凌森，…，葛均波" if zh else "L. You, …, J.B. Ge"), key
                if route == listing:
                    assert not title.a, key
                else:
                    assert absolute(route, title.a["href"]) == absolute(route, listing + "#" + pid), key
                uri = BASE + "/publications/#" + pid
                record = nodes[uri]
                assert record["creativeWorkStatus"] == "Accepted" and not any(
                    f in record for f in ("datePublished", "identifier", "volumeNumber", "issueNumber")), key
                people = [n if "name" in n else nodes[n["@id"]] for n in record["author"]]
                marked = full.split(", ")
                assert len(people) == len(marked) == 13 and all(
                    name.rstrip("#*") in [person["name"], *person.get("alternateName", [])]
                    for name, person in zip(marked, people)), (key, "contributions")
                assert [n[:-1] for n in marked if n.endswith("#")] == ["Lingsen You", "Hanxiao Du", "Wentong Wang"], key
                assert [n[:-1] for n in marked if n.endswith("*")] == ["Ning Jiang", "Li Shen", "Junbo Ge"], key
                assert all("doi.org/" not in u and not urlsplit(u).path.lower().endswith(".pdf") for u in current), key
            else:
                verify_image(media, lead, route, home, key)
                uri = required(title, "a[href]", key)["href"]
                media_link = required(media, "a.pc-media-link[href]", key)
                assert media_link.picture and media_link["href"] in current, (key, "linked cover")
                assert required(actions, "a.pc-link:not(.pc-pdf)", key)["href"] == uri and uri.startswith("https://"), key
                pdf = required(actions, "a.pc-link.pc-pdf.pdf-link", key)
                old_pdf = required(lead, ".pdf-link", key)
                assert absolute(route, pdf["href"]) == absolute(home, old_pdf["href"]), (key, "PDF URL")
                assert pdf.get("download") == old_pdf.get("download"), (key, "PDF download name")
                if pdf.has_attr("download"):
                    with local_asset(route, pdf["href"]).open("rb") as f:
                        assert f.read(5) == b"%PDF-", key
                    counters["local"] += 1
                else:
                    assert pdf.get("target") == "_blank" and "noopener" in pdf.get("rel", []), key
                    counters["official"] += 1
            item_uris.append(uri)
        assert counters == {"local": 7, "official": 4, "accepted": 1}, (route, counters)
        if route == listing:
            collection = next(n["mainEntity"] for n in new_graph if n["@type"] == "CollectionPage")
            items = collection["itemListElement"]
            assert collection["numberOfItems"] == len(items) == 12, route
            assert [n["position"] for n in items] == list(range(1, 13)), (route, "schema positions")
            assert [n["item"]["@id"] for n in items] == item_uris, (route, "schema order")
        print(f"PASS {route}: 12 uniform cards; 7 local PDFs, 4 publisher PDFs, 1 accepted without paper link.")


if __name__ == "__main__":
    main()
