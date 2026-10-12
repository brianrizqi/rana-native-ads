"""Partition and duplicate-cluster statistics from the frozen split files, and the public release table.

Splits frozen before manifest.json and ids_hashes.csv existed still carry cluster_id in every record,
so both are rebuilt here from the JSONL files. ids_hashes.csv holds no URL and no text.

    python revision/split_stats.py --split-dir revision/splits/main
"""

import argparse
import collections
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import normalize_for_hash, read_jsonl, sha256, write_json

SPLITS = ("train", "val", "test", "test_xsource")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split-dir", default="revision/splits/main")
    a = ap.parse_args()
    d = Path(a.split_dir)
    rows = []
    for sp in SPLITS:
        f = d / f"{sp}.jsonl"
        if f.exists():
            for r in read_jsonl(f):
                r["split"] = sp
                rows.append(r)

    counts = collections.Counter((r["split"], r["lang"], r["label"]) for r in rows)
    for k in sorted(counts):
        print(*k, counts[k])

    clusters = collections.defaultdict(list)
    for r in rows:
        clusters[r.get("cluster_id", r["id"])].append(r)
    multi = [v for v in clusters.values() if len(v) > 1]
    stats = {
        "articles": len(rows),
        "clusters": len(clusters),
        "multi_member_clusters": len(multi),
        "articles_in_multi_member_clusters": sum(map(len, multi)),
        "largest_cluster": max(map(len, clusters.values())),
        "cross_language_clusters": sum(len({r["lang"] for r in v}) > 1 for v in multi),
        "conflicting_label_clusters": sum(len({r["label"] for r in v}) > 1 for v in multi),
        "clusters_spanning_splits": sum(len({r["split"] for r in v}) > 1 for v in clusters.values()),
        "counts": {f"{s}/{l}/{y}": n for (s, l, y), n in sorted(counts.items())},
    }
    for k, v in stats.items():
        if k != "counts":
            print(k, v)

    with open(d / "ids_hashes.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "split", "cluster_id", "text_sha256", "lang", "label", "host", "section"])
        for r in sorted(rows, key=lambda r: (r["split"], str(r["id"]))):
            h = r.get("text_sha256") or sha256(normalize_for_hash(r["text"]))
            w.writerow([r["id"], r["split"], r.get("cluster_id", ""), h, r["lang"], r["label"],
                        r.get("host", ""), r.get("section", "")])
    write_json(d / "split_stats.json", stats)
    print(f"✅ {d / 'ids_hashes.csv'} and {d / 'split_stats.json'} (no URLs, no text)")


if __name__ == "__main__":
    main()
