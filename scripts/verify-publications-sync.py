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


def image_key(card):
    return Path(urlsplit(card.img["src"]).path).name


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
    assert len(cards) == len(home_cards) == 11
    assert [image_key(c) for c in cards] == [image_key(c) for c in home_cards]
    assert [h["id"] for h in page.select("main > section > h2")] == ["selected-title", "themes-title"]
    assert len(page.select(".pdf-link")) == 11
    small_bytes = retina_bytes = original_bytes = local_pdfs = 0
    for card, reference in zip(cards, home_cards):
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
    data = json.loads(page.select_one('script[type="application/ld+json"]').string)
    collection = next(n for n in data["@graph"] if n["@type"] == "CollectionPage")
    items = collection["mainEntity"]["itemListElement"]
    assert collection["mainEntity"]["numberOfItems"] == len(cards)
    assert [i["position"] for i in items] == list(range(1, 12))
    assert [i["item"]["@id"] for i in items] == [c.h3.a["href"] for c in cards]
    if args.baseline_ref:
        original = subprocess.check_output(["git", "show", f"{args.baseline_ref}:publications/index.html"], cwd=ROOT).decode("utf-8")
        baseline = BeautifulSoup(original, "html.parser")
        old_cards = {image_key(c): c for c in baseline.select(".pub-list > article")}
        for card in cards:
            old = old_cards[image_key(card)]
            for selector in ("h3", ".authors", ".summary"):
                assert text(card.select_one(selector)) == text(old.select_one(selector)), (image_key(card), selector)
            assert {a["href"] for a in old.select("a[href]")} <= {a["href"] for a in card.select("a[href]")}
        print("PASS: all 11 titles, full author lists, summaries and existing article links preserved")
    print("PASS: homepage order, all 11 responsive images, journal labels, PDF targets and structured order")
    print(f"PDF buttons: {local_pdfs} local downloads, {len(cards)-local_pdfs} official publisher destinations")
    print(f"Image payload: original={original_bytes:,} B; small={small_bytes:,} B; retina={retina_bytes:,} B")
    print(f"Savings: small={1-small_bytes/original_bytes:.1%}; retina={1-retina_bytes/original_bytes:.1%}")


if __name__ == "__main__":
    main()
