"""Majority-vote kNN over the same five bge-m3 neighbors that RANA receives (R1-C3).

Reads the released per-article predictions of RANA with retrieval, whose rows list the labels of
the five retrieved training articles, takes the majority label, and compares it with RANA by an
exact McNemar test. Nothing here needs the article text or a GPU.

    python revision/knn_majority.py --pred-dir revision/release/predictions --out revision/report/knn_majority.json
"""

import argparse
import csv
import json
from collections import Counter
from math import comb
from pathlib import Path


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred-dir", default="revision/release/predictions")
    ap.add_argument("--run", default="gemma3-12b__reasoning_first")
    ap.add_argument("--out", default="revision/report/knn_majority.json")
    a = ap.parse_args()
    report = {}
    for split in ("test", "test_xsource"):
        rows = list(csv.DictReader(open(Path(a.pred_dir) / a.run / f"{split}__rag_k5.csv", encoding="utf-8")))
        res = {"n": len(rows)}
        vote_ok, rana_ok, by_lang = [], [], {}
        for r in rows:
            labels = [x for x in r["neighbor_labels_shown"].split(";") if x]
            vote = Counter(labels).most_common(1)[0][0]
            ok_v, ok_r = vote == r["label_gold"], r["label_pred"] == r["label_gold"]
            vote_ok.append(ok_v)
            rana_ok.append(ok_r)
            by_lang.setdefault(r["lang"], []).append(ok_v)
        b = sum(r and not v for v, r in zip(vote_ok, rana_ok))   # only RANA right
        c = sum(v and not r for v, r in zip(vote_ok, rana_ok))   # only the vote right
        res.update({"accuracy_majority_vote": round(sum(vote_ok) / len(rows), 4),
                    "accuracy_rana": round(sum(rana_ok) / len(rows), 4),
                    "by_lang": {k: round(sum(v) / len(v), 4) for k, v in by_lang.items()},
                    "only_rana_correct": b, "only_vote_correct": c, "mcnemar_p": mcnemar_exact(b, c)})
        report[split] = res
        print(split, json.dumps(res))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
