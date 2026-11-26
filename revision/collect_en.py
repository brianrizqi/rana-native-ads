"""
Build the additional English evaluation set from independent publishers (R2-2). CPU + network.

    python revision/collect_en.py --urls revision/splits/en_ext/urls.csv --split-dir revision/splits/main \
        --out revision/splits/en_ext/pool.jsonl

urls.csv columns: url, publisher, disclosed (1 = the publisher marks the article as sponsored, paid, partner or
branded content; 0 = editorial), topic (free text used to match topics across the two groups; optional).

Each page is fetched once (trafilatura if installed, otherwise the <p> text of the page), cleaned with the same
mask_source_cues every model input receives, and checked against the corpus: an article whose normalized-text
hash equals a corpus article, or whose word five-gram Jaccard similarity with a training article reaches 0.7,
is dropped, so a syndicated press release cannot appear in training and in this set at once. Labels and
signals are left empty: they come from the source-blinded annotation (annotation_r2.py), and the disclosure flag
is kept only to compare with them afterwards. Pages are cached in --cache so a rerun does not refetch them.
"""

import argparse
import csv
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import mask_source_cues, normalize_for_hash, parse_url, read_jsonl, sha256, write_jsonl
from prepare_data import shingles


def fetch(url, cache: Path):
    f = cache / (hashlib.sha1(url.encode()).hexdigest() + ".txt")
    if f.exists():
        return f.read_text(encoding="utf-8")
    import requests
    html = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (research corpus builder)"}).text
    text = None
    try:
        import trafilatura
        text = trafilatura.extract(html, include_comments=False, include_tables=False)
    except ImportError:
        pass
    if not text:
        from html.parser import HTMLParser

        class P(HTMLParser):
            def __init__(self):
                super().__init__()
                self.inp, self.buf, self.out = False, [], []

            def handle_starttag(self, tag, attrs):
                if tag == "p":
                    self.inp, self.buf = True, []

            def handle_endtag(self, tag):
                if tag == "p" and self.inp:
                    s = " ".join("".join(self.buf).split())
                    if len(s) > 40:
                        self.out.append(s)
                    self.inp = False

            def handle_data(self, data):
                if self.inp:
                    self.buf.append(data)
        p = P()
        p.feed(html)
        text = "\n".join(p.out)
    cache.mkdir(parents=True, exist_ok=True)
    f.write_text(text or "", encoding="utf-8")
    time.sleep(1.0)  # be polite to the publisher
    return text or ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--urls", required=True)
    ap.add_argument("--split-dir", required=True, help="Main partition, for the duplicate check against training")
    ap.add_argument("--ids", default=None, help="ids_hashes.csv (default: <split-dir>/ids_hashes.csv)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache", default="revision/cache/en_ext_pages")
    ap.add_argument("--min-chars", type=int, default=400)
    ap.add_argument("--jaccard", type=float, default=0.7)
    a = ap.parse_args()

    d = Path(a.split_dir)
    with open(a.ids or d / "ids_hashes.csv", encoding="utf-8") as f:
        corpus_hashes = {r["text_sha256"] for r in csv.DictReader(f)}
    train_sh = [shingles(r["text_raw"]) for r in read_jsonl(d / "train.jsonl")] if (d / "train.jsonl").exists() else []
    with open(a.urls, encoding="utf-8") as f:
        src = list(csv.DictReader(f))
    rows, dropped = [], {"short": 0, "hash": 0, "near_dup": 0, "fetch": 0}
    for n, s in enumerate(src, 1):
        try:
            raw = fetch(s["url"], Path(a.cache))
        except Exception as e:
            print(f"fetch failed {s['url']}: {e}")
            dropped["fetch"] += 1
            continue
        if len(raw) < a.min_chars:
            dropped["short"] += 1
            continue
        h = sha256(normalize_for_hash(raw))
        if h in corpus_hashes:
            dropped["hash"] += 1
            continue
        sh = shingles(raw)
        if any(len(sh & t) / max(1, len(sh | t)) >= a.jaccard for t in train_sh if t):
            dropped["near_dup"] += 1
            continue
        u = parse_url(s["url"])
        rid = f"en2_{n:05d}"
        rows.append({"id": rid, "lang": "en", "label": None, "signals": None, "url": s["url"], **u,
                     "publisher": s.get("publisher") or u["outlet"], "disclosed": int(s["disclosed"]),
                     "topic": s.get("topic", ""), "text_raw": raw, "text": mask_source_cues(raw),
                     "text_sha256": h, "cluster_id": f"x{rid}", "split": "test_en_ext"})
    write_jsonl(a.out, rows)
    by_pub = {}
    for r in rows:
        by_pub.setdefault(r["publisher"], [0, 0])[r["disclosed"]] += 1
    print(json.dumps({"kept": len(rows), "dropped": dropped, "editorial/disclosed per publisher": by_pub}, indent=2))


if __name__ == "__main__":
    main()
