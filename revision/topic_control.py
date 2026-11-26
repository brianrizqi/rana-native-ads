"""
Topic-controlled accuracy (R1 minor 1: topic and category bias on the withheld publisher). CPU only.

    python revision/topic_control.py --ids revision/splits/main/ids_hashes.csv --out revision/report/topic_control.csv \
        --runs "revision/release/predictions/*/test_xsource*.csv" "revision/results/tfidf__masked/test_xsource.jsonl"

Withholding a publisher removes outlet identity, but not topic: within the withheld publisher the share of
Native Ads still differs by content category (sports is mostly Pure News, lifestyle mostly Native Ads), so a
model can gain accuracy from a topic prior learned elsewhere. Two figures quantify that:

  category_prior_ceiling  accuracy of the best possible category-only rule on the test set itself (majority
                          label of each category, fitted on the test articles): what topic alone could give.
  cat_balanced_acc        accuracy after reweighting every article so that, within each content category, the two
                          classes carry equal weight; a topic-only rule scores exactly 50% on this measure.
                          Categories holding only one class are left out, since they carry no within-topic signal.
Categories are the fixed URL rules of category_table.py.
"""

import argparse
import csv
import glob
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from category_table import RULES
from common import NATIVE, NEWS, read_jsonl


def category(host, section):
    parts = [x for x in (section or "", (host or "").split(".")[0]) if x]
    for cat, keys in RULES:
        if any(p == k or p.startswith(k) for p in parts for k in keys):
            return cat
    return "Other"


def load(path):
    if path.endswith(".csv"):
        with open(path, encoding="utf-8") as f:
            return list(csv.DictReader(f))
    return read_jsonl(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", required=True, help="ids_hashes.csv (host and section per article)")
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.ids, encoding="utf-8") as f:
        meta = {r["id"]: category(r["host"], r["section"]) for r in csv.DictReader(f)}

    out = []
    for pat in a.runs:
        for path in sorted(glob.glob(pat)):
            rows = load(path)
            cells = defaultdict(list)
            for r in rows:
                cat = meta.get(str(r["id"])) or category(r.get("host"), r.get("section"))
                cells[(cat, r["label_gold"])].append(r.get("label_pred") == r["label_gold"])
            cats = sorted({c for c, _ in cells})
            n_mixed, cb, ceiling = 0, 0.0, 0
            for c in cats:
                na, pn = cells.get((c, NATIVE), []), cells.get((c, NEWS), [])
                ceiling += max(len(na), len(pn))
                if na and pn:
                    n = len(na) + len(pn)
                    n_mixed += n
                    cb += n * (sum(na) / len(na) + sum(pn) / len(pn)) / 2
            acc = sum(r.get("label_pred") == r["label_gold"] for r in rows) / len(rows)
            out.append({"run": path, "n": len(rows), "accuracy": round(acc, 6),
                        "cat_balanced_acc": round(cb / n_mixed, 6) if n_mixed else "",
                        "gap": round(acc - cb / n_mixed, 6) if n_mixed else "",
                        "category_prior_ceiling": round(ceiling / len(rows), 6), "n_in_mixed_categories": n_mixed})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    for r in out:
        print(f"{r['run'][-70:]:70s} acc={100 * r['accuracy']:6.2f} topic-balanced={100 * float(r['cat_balanced_acc'] or 0):6.2f} "
              f"(topic-only ceiling {100 * r['category_prior_ceiling']:.2f})")


if __name__ == "__main__":
    main()
