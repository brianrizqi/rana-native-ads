"""Category distribution of the corpus (manuscript Table 3), derived from each article's URL.

The source files carry no category field, so the category is mapped from the outlet subdomain and
URL section with the fixed rules below. Branded-content channels (biz.kompas.com, viva siaran-pers,
thestar GlobeNewswire) form their own row, since they are labeled by channel rather than topic.

    python revision/category_table.py --xlsx native_ads_dataset.xlsx
"""
import argparse
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import norm_label, parse_url

RULES = [  # (category, keywords matched against host and section), first match wins
    ("Branded content and press releases", ["biz", "globenewswire", "siaran-pers"]),
    ("Sports", ["sport", "olahraga", "bola"]),
    ("Economy and business", ["ekonomi", "finance", "bisnis", "business", "ekbis", "money", "properti", "homey"]),
    ("Technology and science", ["tekno", "teknologi", "inet", "digital", "sains"]),
    ("Automotive", ["otomotif", "oto"]),
    ("Lifestyle and health", ["gaya", "lifestyle", "food", "health", "travel", "wolipop", "life"]),
    ("Entertainment", ["hiburan", "hot", "seleb", "showbiz", "entertainment"]),
    ("International", ["internasional", "international", "dunia", "global"]),
    ("Education", ["edukasi", "skola", "edu"]),
    ("National and regional news", ["nasional", "news", "berita", "megapolitan", "regional", "daerah", "politics"]),
]


def category(url):
    p = parse_url(url)
    parts = [x for x in (p.get("section") or "", (p.get("host") or "").split(".")[0]) if x]
    for cat, keys in RULES:
        if any(part == k or part.startswith(k) for part in parts for k in keys):
            return cat
    return "Other"


def main():
    import pandas as pd
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default="native_ads_dataset.xlsx")
    a = ap.parse_args()
    df = pd.read_excel(a.xlsx)
    c = collections.Counter((category(r["url"]), norm_label(r["label"])) for _, r in df.iterrows())
    cats = [r[0] for r in RULES] + ["Other"]
    for cat in cats:
        na, pn = c[(cat, "native ads")], c[(cat, "berita murni")]
        print(f"{cat:38s} {na + pn:6d} {na:6d} {pn:6d}")
    print(f"{'Total':38s} {sum(c.values()):6d}")


if __name__ == "__main__":
    main()
