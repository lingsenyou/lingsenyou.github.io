"""Check the publications page against the homepage and a pre-update Git ref.

Run: python scripts/verify-publications-sync.py --baseline-ref ca96d35
Requires BeautifulSoup and Pillow. Does not modify any files or use the network.
"""

import argparse
import json
from pathlib import Path
import subprocess
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://lingsenyou.com/"


def card_key(card):
    return Path(urlsplit(card.img["src"]).path).name if card.img else card["id"]


def text(node):
    return " ".join(node.stripped_strings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref")
    args = parser.parse_args()
    home = BeautifulSoup((ROOT / "index.html").read_text(encoding="utf-8"), "html.parser")
    page = BeautifulSoup((ROOT / "publications/index.html").read_text(encoding="utf-8"), "html.parser")
    cards = page.select(".pub-list > article")
    home_cards = home.select(".pub-item")
    card_order = [card_key(c) for c in cards]
    assert card_order and len(set(card_order)) == len(card_order)
    assert card_order == [card_key(c) for c in home_cards]
    assert [h["id"] for h in page.select("main > section > h2")] == ["selected-title", "themes-title"]
    data = json.loads(page.select_one('script[type="application/ld+json"]').string)
    articles = {n["@id"]: n for n in data["@graph"] if n["@type"] == "ScholarlyArticle"}
    home_data = json.loads(home.select_one('script[type="application/ld+json"]').string)
    home_articles = {n.get("@id"): n for n in home_data["@graph"] if n["@type"] == "ScholarlyArticle"}
    accepted = page.select('.pub-list > article[data-status="accepted"]')
    assert len(page.select(".pdf-link")) == len(cards) - len(accepted)
    small_bytes = retina_bytes = original_bytes = local_pdfs = 0
    for card, reference in zip(cards, home_cards):
        is_accepted = card.get("data-status") == "accepted"
        assert is_accepted == (reference.get("data-status") == "accepted")
        if is_accepted:
            item_id = urljoin(BASE, "publications/#" + card["id"])
            node = articles[item_id]
            assert node == home_articles[item_id]
            assert node["creativeWorkStatus"] == "Accepted"
            assert node["headline"] == text(card.h3) == text(reference.select_one(".pub-title"))
            assert urljoin(BASE, reference.select_one(".pub-title")["href"]) == item_id
            assert not any(field in node for field in ("datePublished", "identifier", "volumeNumber", "issueNumber"))
            assert not card.select_one(".doi, .pdf-link, img") and not reference.select_one(".pdf-link, img")
            assert text(reference.select_one(".badge-if")) == text(card.select_one(".metric-if"))
            assert "Accepted" in text(reference.select_one(".badge-status")) and "Accepted" in text(card.select_one(".venue"))
            if card["id"] == "paper-gpnmb-restenosis":
                assert card.select_one(".byline-brief").get_text() == reference.select_one(".pub-authors").get_text() == "L. You, …, J.B. Ge"
                details = card.select_one("details.author-credit:not([open])")
                assert details and details.summary and details.select_one(".authors")
                graph_names = [p.get("name") or next(n["name"] for n in data["@graph"] if n["@id"] == p["@id"]) for p in node["author"]]
                marked_names = details.select_one(".authors").get_text().split(", ")
                assert [n.rstrip("#*") for n in marked_names] == graph_names and len(marked_names) == 13
                assert [n[:-1] for n in marked_names if n.endswith("#")] == ["Lingsen You", "Hanxiao Du", "Wentong Wang"]
                assert [n[:-1] for n in marked_names if n.endswith("*")] == ["Ning Jiang", "Li Shen", "Junbo Ge"]
                assert node["creditText"] == "Lingsen You, Hanxiao Du and Wentong Wang contributed equally. Ning Jiang, Li Shen and Junbo Ge are corresponding authors."
                assert card.select_one(".journal-label strong").get_text() == reference.select_one(".journal-label strong").get_text() == "Genes & Diseases"
            continue
        img = card.img
        source = card.source
        assert img.get("alt") and img.get("loading") == "lazy" and img.get("decoding") == "async"
        assert img["width"] == reference.img["width"] and img["height"] == reference.img["height"]
        assert source["type"] == "image/webp"
        variants = [v.strip().split() for v in source["srcset"].split(",")]
        assert len(variants) == 2
        for index, (path, width) in enumerate(variants):
            asset = ROOT / "publications" / path
            with Image.open(asset) as image:
                image.load()
                assert image.format == "WEBP" and image.width == int(width[:-1])
                assert abs(image.height - image.width * int(img["height"]) / int(img["width"])) <= 0.51
            if index == 0:
                small_bytes += asset.stat().st_size
            else:
                retina_bytes += asset.stat().st_size
        original_bytes += (ROOT / "publications" / urlsplit(img["src"]).path).stat().st_size
        pdf = card.select_one(".pdf-link")
        ref_pdf = reference.select_one(".pdf-link")
        assert urljoin(BASE + "publications/", pdf["href"]) == urljoin(BASE, ref_pdf["href"])
        assert pdf.get("download") == ref_pdf.get("download")
        if pdf.has_attr("download"):
            asset = ROOT / "publications" / pdf["href"]
            with asset.open("rb") as stream:
                assert stream.read(5) == b"%PDF-"
            local_pdfs += 1
        else:
            assert pdf.get("target") == "_blank" and "noopener" in pdf.get("rel", [])
        metric = reference.select_one(".badge-if")
        if metric:
            assert text(metric) in text(card.select_one(".metric-if"))
        else:
            assert not card.select_one(".metric-if")
        if reference.select_one(".badge-wcj"):
            assert card.select_one(".wcj")
        for badge in reference.select(".badge-publisher, .badge-highlight"):
            assert text(badge) in text(card)
    collection = next(n for n in data["@graph"] if n["@type"] == "CollectionPage")
    items = collection["mainEntity"]["itemListElement"]
    assert collection["mainEntity"]["numberOfItems"] == len(cards)
    assert [i["position"] for i in items] == list(range(1, len(cards) + 1))
    assert [i["item"]["@id"] for i in items] == [c.h3.a["href"] if c.h3.a else urljoin(BASE, "publications/#" + c["id"]) for c in cards]
    if args.baseline_ref:
        original = subprocess.check_output(["git", "show", f"{args.baseline_ref}:publications/index.html"], cwd=ROOT).decode("utf-8")
        baseline = BeautifulSoup(original, "html.parser")
        new_cards = {card_key(c): c for c in cards}
        old_cards = {card_key(c): c for c in baseline.select(".pub-list > article")}
        assert old_cards.keys() <= new_cards.keys()
        assert list(old_cards) == [key for key in card_order if key in old_cards]
        for key, old in old_cards.items():
            card = new_cards[key]
            for selector in ("h3", ".authors", ".summary"):
                assert text(card.select_one(selector)) == text(old.select_one(selector)), (key, selector)
            assert {a["href"] for a in old.select("a[href]")} <= {a["href"] for a in card.select("a[href]")}
        print(f"PASS: {len(old_cards)} existing titles, full author lists, summaries and article links preserved")
    print(f"PASS: {len(cards)} entries match homepage/structured order; {len(accepted)} accepted without a public paper link")
    print(f"PDF buttons: {local_pdfs} local downloads, {len(cards)-len(accepted)-local_pdfs} official publisher destinations")
    print(f"Image payload: original={original_bytes:,} B; small={small_bytes:,} B; retina={retina_bytes:,} B")
    print(f"Savings: small={1-small_bytes/original_bytes:.1%}; retina={1-retina_bytes/original_bytes:.1%}")


if __name__ == "__main__":
    main()
