"""Check the static /zh/ mirror and its language links. Optionally check production (--live).

Run: python scripts/verify-translations.py [--live]. Requires BeautifulSoup.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit, unquote
from urllib.request import urlopen, Request
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://lingsenyou.com"
ROUTES = ["/", "/publications/", "/suitcordance/", "/scientific/", "/panvascular/"]
PROJECTS = {"scientific", "panvascular", "medeng"}

def load(path, live):
    if live:
        with urlopen(Request(ORIGIN+path, headers={"User-Agent":"BilingualSiteQA/1.0"}), timeout=22) as response:
            assert response.status == 200 and urlsplit(response.url).path == path, response.url
            assert "noindex" not in response.headers.get("X-Robots-Tag","").lower(), path
            return response.read()
    file = ROOT / path.strip("/")
    return ((file / "index.html") if path.endswith("/") else file).read_bytes()

def absolute(path, link):
    return urljoin(ORIGIN + path, link)

def page(path, live):
    soup = BeautifulSoup(load(path, live).decode("utf-8"),"html.parser")
    zh = path.startswith("/zh/")
    en = path[3:] if zh else path
    alt = {"en":ORIGIN+en, "zh-Hans":ORIGIN+"/zh"+en, "x-default":ORIGIN+en}
    assert soup.html["lang"].lower().startswith("zh" if zh else "en"), path
    assert soup.title and soup.select_one('meta[name="description"]')["content"], path
    assert len(soup.select('link[rel="canonical"]')) == 1 and soup.select_one('link[rel="canonical"]')["href"] == ORIGIN + path, path
    assert {t["hreflang"]:t["href"] for t in soup.select('link[rel="alternate"][hreflang]')} == alt, path
    assert not any("noindex" in t.get("content","").lower() for t in soup.select('meta[name="robots"]')), path
    assert any(absolute(path,t["href"]) == alt["en" if zh else "zh-Hans"] and t.get_text(strip=True)
               for t in soup.body.select("a[href]")), path
    scripts = [json.loads(t.get_text()) for t in soup.select('script[type="application/ld+json"]')]
    assert scripts, path
    if zh:
        assert re.search(r"[\u4e00-\u9fff]",soup.h1.get_text()), path
        assert len(re.findall(r"[\u4e00-\u9fff]",soup.body.get_text())) > 80, path
        assert soup.select_one('meta[property="og:url"]')["content"] == ORIGIN+path, path
        assert not re.search(r"/zh/zh/|127\.0\.0\.1|localhost:",str(soup.head)), path
        for t in soup.select("img"):
            assert t.has_attr("alt"), (path, t.get("src"))
        if not live:
            urls = [(t.get("href") or t.get("src")) for t in soup.select("a[href],img[src],link[href],script[src]")]
            urls += [c.strip().split()[0] for t in soup.select("[srcset]") for c in t["srcset"].split(",")]
            for url in urls:
                parts = urlsplit(absolute(path,url))
                if parts.netloc != "lingsenyou.com":
                    continue
                rel = unquote(parts.path.strip("/"))
                if rel.split("/")[0] in PROJECTS:  # separate GitHub Pages projects
                    continue
                assert (ROOT/rel).exists(), (path, url)
        if en in ("/","/publications/"):
            assert "0000-0003-0794-5907" in str(soup), path
            assert len(soup.select(".pub-title-en[lang=en]")) == len(soup.select(".pdf-link")) == 11, path
            assert "https://lingsenyou.com/#person" in json.dumps(scripts), path
    return path

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    live = parser.parse_args().live
    assert "Allow: /" in load("/robots.txt",live).decode()
    sitemap = {n.text for n in ET.fromstring(load("/sitemap.xml",live)).iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")}
    paths = [variant for r in ROUTES for variant in (r,"/zh"+r)]
    assert {ORIGIN+p for p in paths} <= sitemap, "missing bilingual sitemap entries"
    if not live:
        paths = [p for p in paths if p.strip("/") not in PROJECTS]
    with ThreadPoolExecutor(max_workers=5) as workers:
        for path in workers.map(lambda p:page(p,live),paths):
            print("OK",path)

if __name__ == "__main__":
    main()
