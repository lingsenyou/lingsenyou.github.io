"""Build responsive homepage thumbnails without altering source images.

Usage: python scripts/optimize-homepage-images.py
Requires Pillow with WebP support. Tested with Pillow 12.2.0.
The EHJ preview uses the same top-aligned 640:414 crop as the homepage CSS.
All other images preserve their complete original aspect ratio and contents.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageOps, features


SITE_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = SITE_ROOT / "assets" / "optimized"
PUBLICATION_IMAGES = (
    "ehj-occ-20-years-cover.png",
    "trends-molecular-medicine-suitcordance.jpg",
    "paper7.jpg",
    "paper6.jpg",
    "paper4.jpg",
    "csb-plla-ai-screening.jpg",
    "paper1.jpg",
    "paper2.jpg",
    "advanced-fiber-materials-v7-i4-cover.jpg",
    "paper5.jpg",
    "immune-world-model.png",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rgb_image(path: Path) -> Image.Image:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, "white")
            return Image.alpha_composite(background, rgba).convert("RGB")
        return image.convert("RGB")


def thumbnail(image: Image.Image, width: int, ehj_crop: bool = False) -> Image.Image:
    if ehj_crop:
        # Fractional crop coordinates match object-fit: cover at aspect-ratio 640/414.
        height = round(width * 414 / 640)
        box = (0, 0, image.width, image.width * 414 / 640)
        return image.resize((width, height), Image.Resampling.LANCZOS, box=box)
    height = round(width * image.height / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def main() -> None:
    if not features.check("webp"):
        raise RuntimeError("Pillow must include WebP encoding support")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for filename in (*PUBLICATION_IMAGES, "avatar.jpg"):
        source = SITE_ROOT / filename
        source_hash = sha256(source)
        image = rgb_image(source)
        variants = []
        widths = (200, 400) if filename == "avatar.jpg" else (320, 640)
        for width in widths:
            result = thumbnail(image, width, filename == "ehj-occ-20-years-cover.png")
            output = OUTPUT / f"{source.stem}-{width}.webp"
            result.save(output, "WEBP", quality=88, method=6)
            with Image.open(output) as check:
                check.load()
                assert check.size == result.size
            variants.append({
                "path": output.relative_to(SITE_ROOT).as_posix(),
                "width": result.width,
                "height": result.height,
                "bytes": output.stat().st_size,
                "sha256": sha256(output),
            })
        assert sha256(source) == source_hash, f"Original image changed: {filename}"
        manifest.append({
            "source": filename,
            "source_width": image.width,
            "source_height": image.height,
            "source_bytes": source.stat().st_size,
            "source_sha256": source_hash,
            "variants": variants,
        })
    favicon = thumbnail(rgb_image(SITE_ROOT / "avatar.jpg"), 32)
    favicon.save(OUTPUT / "favicon-32.png", "PNG", optimize=True)
    print(json.dumps({
        "images": manifest,
        "favicon": {"path": "assets/optimized/favicon-32.png", "width": 32,
                    "height": 32, "bytes": (OUTPUT / "favicon-32.png").stat().st_size},
        "original_total_bytes": sum(item["source_bytes"] for item in manifest),
        "small_variant_total_bytes": sum(item["variants"][0]["bytes"] for item in manifest),
        "retina_variant_total_bytes": sum(item["variants"][1]["bytes"] for item in manifest),
    }, indent=2))


if __name__ == "__main__":
    main()
