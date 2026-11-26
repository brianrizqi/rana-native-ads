"""
Accuracy across training seeds and seed-aware model comparisons (R2-6, R1 minor 3). CPU only.

    python revision/seed_stats.py --out-dir revision/report/seeds_r2 \
        --group "RANA=revision/results/gemma3-12b__reasoning_first{,_s42,_s2024}/test_xsource__rag_k5.jsonl" \
        --group "Qwen3.5 9B=revision/results/qwen3.5-9b__reasoning_first{,_s42,_s2024}/test_xsource__rag_k5.jsonl" \
        --group "TF-IDF=revision/results/tfidf__masked/test_xsource.jsonl" --compare RANA:TF-IDF

A group is one model configuration evaluated on one test set, given as one or more prediction files
(one per seed; brace patterns and globs are expanded). Prediction files are infer.py JSONL or released CSV.

Per group: number of seeds, mean, standard deviation, minimum and maximum of accuracy and macro-F1.
Per --compare A:B (all pairs if none given): the difference of mean accuracy, with a 95% interval from a
paired bootstrap over articles (each resample averages every seed of a group on the same articles), a
two-sided bootstrap p-value, and how many of the seed-by-seed McNemar tests are significant at 0.05.
Holm correction is applied over the --compare family. A deterministic model has one file and SD 0.
"""

import argparse
import csv
import glob
import itertools
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LABELS, read_jsonl
from stats import holm, prf


def expand(pattern):
    m = re.search(r"\{([^{}]*)\}", pattern)
    if m:
        return [p for alt in m.group(1).split(",") for p in expand(pattern[:m.start()] + alt + pattern[m.end():])]
    hits = sorted(glob.glob(pattern))
    return hits


def load(path):
    if path.endswith(".csv"):
        with open(path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        rows = read_jsonl(path)
    return {str(r["id"]): (r["label_gold"], r.get("label_pred") or "") for r in rows}


def mcnemar_p(b, c):
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--group", action="append", required=True, help='"NAME=pattern[,pattern...]"')
    ap.add_argument("--compare", action="append", default=[], help="A:B")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--restrict", default=None, help="JSONL whose article ids every group is restricted to")
    a = ap.parse_args()
    keep = {str(r["id"]) for r in read_jsonl(a.restrict)} if a.restrict else None

    groups = {}
    for g in a.group:
        name, pats = g.split("=", 1)
        files = [f for p in pats.split(";") for f in expand(p)]
        if not files:
            sys.exit(f"group {name}: no files match {pats}")
        runs = [(f, load(f)) for f in files]
        if keep is not None:
            runs = [(f, {i: v for i, v in r.items() if i in keep}) for f, r in runs]
        groups[name] = runs

    summary = []
    for name, runs in groups.items():
        ids = sorted(set.intersection(*[set(r) for _, r in runs]))
        accs, f1s = [], []
        for _, r in runs:
            gold = [r[i][0] for i in ids]
            pred = [r[i][1] if r[i][1] in LABELS else next(l for l in LABELS if l != r[i][0]) for i in ids]
            accs.append(float(np.mean([g == p for g, p in zip(gold, pred)])))
            f1s.append(prf(gold, pred, LABELS)[1])
        sd = float(np.std(accs, ddof=1)) if len(accs) > 1 else 0.0
        summary.append({"group": name, "n_seeds": len(runs), "n_articles": len(ids),
                        "acc_mean": np.mean(accs), "acc_sd": sd, "acc_min": min(accs), "acc_max": max(accs),
                        "macro_f1_mean": np.mean(f1s), "macro_f1_sd": float(np.std(f1s, ddof=1)) if len(f1s) > 1 else 0.0,
                        "per_seed_acc": [round(x, 6) for x in accs], "files": [f for f, _ in runs]})

    pairs = [tuple(c.split(":", 1)) for c in a.compare] or list(itertools.combinations(groups, 2))
    rng = np.random.default_rng(a.seed)
    comps = []
    for A, B in pairs:
        ids = sorted(set.intersection(*[set(r) for _, r in groups[A] + groups[B]]))
        def correct(runs):
            return np.array([[r[i][1] == r[i][0] for i in ids] for _, r in runs], dtype=float)
        ca, cb = correct(groups[A]), correct(groups[B])
        da = ca.mean(0) - cb.mean(0)  # per-article difference of seed-averaged correctness
        diff = float(da.mean())
        S = rng.integers(0, len(ids), size=(a.bootstrap, len(ids)))
        boots = da[S].mean(1)
        p = float(min(1.0, 2 * min((boots <= 0).mean(), (boots >= 0).mean())))
        sig = []
        for (_, ra), (_, rb) in itertools.product(groups[A], groups[B]):
            b = sum(ra[i][1] == ra[i][0] and rb[i][1] != rb[i][0] for i in ids)
            c = sum(ra[i][1] != ra[i][0] and rb[i][1] == rb[i][0] for i in ids)
            sig.append(mcnemar_p(b, c) < 0.05)
        comps.append({"A": A, "B": B, "n_articles": len(ids), "diff_mean_acc": diff,
                      "ci_low": float(np.quantile(boots, .025)), "ci_high": float(np.quantile(boots, .975)),
                      "p_bootstrap": max(p, 1 / a.bootstrap), "seed_pairs": len(sig),
                      "seed_pairs_mcnemar_p05": int(sum(sig))})
    for c, h in zip(comps, holm([c["p_bootstrap"] for c in comps])):
        c["p_holm"] = h

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "seed_summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[k for k in summary[0] if k != "files"])
        w.writeheader()
        for s in summary:
            w.writerow({k: (json.dumps(v) if isinstance(v, list) else v) for k, v in s.items() if k != "files"})
    if comps:
        with open(out / "seed_compare.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(comps[0]))
            w.writeheader()
            w.writerows(comps)
    with open(out / "seed_report.md", "w", encoding="utf-8") as f:
        f.write("| group | seeds | accuracy mean ± SD | range | macro-F1 mean |\n|---|---|---|---|---|\n")
        for s in summary:
            f.write(f"| {s['group']} | {s['n_seeds']} | {100 * s['acc_mean']:.2f} ± {100 * s['acc_sd']:.2f} | "
                    f"{100 * s['acc_min']:.2f}–{100 * s['acc_max']:.2f} | {100 * s['macro_f1_mean']:.2f} |\n")
        if comps:
            f.write("\n| A | B | Δ mean acc | 95% CI | p (Holm) | seed pairs McNemar p<.05 |\n|---|---|---|---|---|---|\n")
            for c in comps:
                f.write(f"| {c['A']} | {c['B']} | {100 * c['diff_mean_acc']:+.2f} | [{100 * c['ci_low']:+.2f}, "
                        f"{100 * c['ci_high']:+.2f}] | {c['p_holm']:.3g} | {c['seed_pairs_mcnemar_p05']}/{c['seed_pairs']} |\n")
    print(open(out / "seed_report.md", encoding="utf-8").read())


if __name__ == "__main__":
    main()
