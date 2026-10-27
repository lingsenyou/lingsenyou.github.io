"""Validate homepage image variants and optionally compare content with a Git ref.

Run: python scripts/verify-homepage-performance.py --baseline-ref <commit>
Requires Pillow, also used by optimize-homepage-images.py.
"""

import argparse
from html.parser import HTMLParser
from pathlib import Path
import subprocess
from urllib.parse import urlsplit

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


class Homepage(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.images = []
        self.sources = []
        self.links = []
        self.text = []
        self.hidden = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"):
            self.hidden += 1
        if tag == "img":
            self.images.append(attrs)
        if tag == "source":
            self.sources.append(attrs)
        if tag == "a":
            self.links.append(attrs)

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.text.extend(data.split())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref")
    args = parser.parse_args()
    page = Homepage((ROOT / "index.html").read_text(encoding="utf-8"))
    assert len(page.images) == len(page.sources) == 12
    small_bytes = large_bytes = original_bytes = 0
    for image, source in zip(page.images, page.sources):
        original = ROOT / urlsplit(image["src"]).path
        original_bytes += original.stat().st_size
        assert image.get("alt"), original.name
        assert int(image["width"]) > 0 and int(image["height"]) > 0
        assert source["type"] == "image/webp"
        variants = [part.strip().split() for part in source["srcset"].split(",")]
        assert len(variants) == 2
        for index, (path, descriptor) in enumerate(variants):
            asset = ROOT / path
            with Image.open(asset) as decoded:
                decoded.load()
                assert decoded.format == "WEBP"
                assert decoded.width == int(descriptor[:-1])
                expected_height = decoded.width * int(image["height"]) / int(image["width"])
                assert abs(decoded.height - expected_height) <= 0.51, asset.name
            if index == 0:
                small_bytes += asset.stat().st_size
            else:
                large_bytes += asset.stat().st_size
        if "profile-img" in image["class"]:
            assert image.get("fetchpriority") == "high"
            assert image.get("loading") != "lazy"
        else:
            assert image.get("loading") == "lazy"
            assert image.get("decoding") == "async"
    with Image.open(ROOT / "assets/optimized/favicon-32.png") as favicon:
        assert favicon.size == (32, 32)
    for link in page.links:
        if link.get("download"):
            assert (ROOT / urlsplit(link["href"]).path).is_file()
    if args.baseline_ref:
        baseline_html = subprocess.check_output(
            ["git", "show", f"{args.baseline_ref}:index.html"], cwd=ROOT
        ).decode("utf-8")
        baseline = Homepage(baseline_html)
        assert page.text == baseline.text, "Homepage text changed"
        assert page.links == baseline.links, "Link attributes changed"
        assert [i["alt"] for i in page.images] == [i["alt"] for i in baseline.images]
        assert [i["src"] for i in page.images] == [i["src"] for i in baseline.images]
        print("PASS: text, all link attributes, image descriptions and original fallbacks unchanged")
    print("PASS: all 12 responsive image pairs, dimensions, priority and local downloads")
    print(f"Full image set: original={original_bytes:,} B; small={small_bytes:,} B; retina={large_bytes:,} B")
    print(f"Image payload savings: small={1-small_bytes/original_bytes:.1%}; retina={1-large_bytes/original_bytes:.1%}")


if __name__ == "__main__":
    main()
