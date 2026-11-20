# Lingsen You (游凌森)

Official academic profile: [lingsenyou.com](https://lingsenyou.com/)

Interventional cardiology, panvascular intervention, device-vessel suitcordance, flexible electronics, artificial intelligence and translational medicine at Zhongshan Hospital, Fudan University.

## English and Simplified Chinese versions

The English site remains at the original URLs. The Simplified Chinese edition is maintained under `/zh/` on the same domain; it does not replace or redirect the English site.

| Page | English | Simplified Chinese |
| --- | --- | --- |
| Profile | `/` | `/zh/` |
| Publications | `/publications/` | `/zh/publications/` |
| Scientific profile | `/scientific/` | `/zh/scientific/` |
| Panvascular Radar | `/panvascular/` | `/zh/panvascular/` |
| Suitcordance Bench | `/suitcordance/` | `/zh/suitcordance/` |

### Maintenance rules

- Treat each pair as two language versions of the same page. Preserve the publication order, author identities, source links, reported data, study limitations and publication status across both versions. English paper titles may be retained alongside Chinese explanations for reliable identification.
- Update the Chinese HTML whenever the corresponding English content changes. Translate visible interface text, image alternative text, metadata and dynamic labels, not only headings. Shared images, PDFs and model/data assets should remain shared where possible.
- Keep every page's canonical URL self-referencing. Each English and Chinese page must link to both versions using `hreflang="en"` and `hreflang="zh-Hans"`, with `hreflang="x-default"` pointing to its English counterpart. Do not canonicalize Chinese pages to English pages.
- Keep the visible language switch pointing to the corresponding page, not always the homepage. The homepage switch is directly beneath the name so it remains prominent on mobile.
- Maintain the five pairs in `sitemap.xml`, with reciprocal `xhtml:link` language alternates. The existing `/medeng/` entry has no Chinese counterpart and remains an independent entry. Change `lastmod` only when the page or its metadata changes.
- Some English modules may be served from separate source repositories. Check the source that actually serves `/scientific/` and `/panvascular/` before updating their reciprocal language links; editing an old local redirect is not a substitute for updating the live module.
- Before deployment, check all local links and assets, JSON-LD parsing, JavaScript syntax and mobile layouts. For Suitcordance Bench, also verify that translation has not altered the embedded model, computational functions, research-only warning or negative findings. Do not expose draft `noindex` settings in the published Chinese edition.
- Keep the Chinese pages readable as HTML without requiring JavaScript for their core profile, publication descriptions and study caveats. Language metadata, crawlable text and sitemaps improve discoverability, but do not guarantee inclusion or citation by any search engine or language model.
