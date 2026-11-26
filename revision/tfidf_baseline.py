"""
TF-IDF + logistic regression with per-article predictions (R2-1, R2-6). CPU only, about a minute.

    python revision/tfidf_baseline.py --split-dir revision/splits/main --out-dir revision/results/tfidf__masked
    python revision/tfidf_baseline.py --split-dir revision/splits/main --out-dir revision/results/tfidf__masked_1500 \
        --max-chars 1500

Same model as shortcut_probe.py (word 1-2 grams, min_df 2, 200k features, sublinear tf, C = 4), but it
writes one prediction file per test set in the infer.py schema, so stats.py, seed_stats.py and
topic_control.py score it exactly like the language models. --max-chars 1500 gives it the same article
window that every language model reads, which separates the effect of context length from that of the
model. --extra-train adds labeled articles from another file to training (target-publisher adaptation).
Logistic regression with lbfgs is deterministic, so one run per configuration suffices.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NATIVE, read_jsonl, write_json, write_jsonl


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--field", default="text", choices=("text", "text_raw"), help="text = source cues removed")
    ap.add_argument("--max-chars", type=int, default=3000)
    ap.add_argument("--C", type=float, default=4.0)
    ap.add_argument("--extra-train", nargs="*", default=[], help="JSONL files added to the training set")
    ap.add_argument("--tests", nargs="*", default=["test", "test_xsource"],
                    help="Test sets: names inside --split-dir or paths to JSONL files")
    args = ap.parse_args()

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression

    d, out = Path(args.split_dir), Path(args.out_dir)
    train = read_jsonl(d / "train.jsonl")
    for f in args.extra_train:
        train += read_jsonl(f)
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=200_000, sublinear_tf=True)
    X = vec.fit_transform([r[args.field][: args.max_chars] for r in train])
    clf = LogisticRegression(max_iter=2000, C=args.C).fit(X, [r["label"] for r in train])
    native_col = list(clf.classes_).index(NATIVE)
    cond = {"model": "tfidf_lr", "method": "tfidf_lr", "field": args.field, "max_chars": args.max_chars,
            "C": args.C, "n_train": len(train), "extra_train": args.extra_train}
    for t in args.tests:
        f = Path(t) if t.endswith(".jsonl") else d / f"{t}.jsonl"
        if not f.exists():
            print(f"skip {f} (missing)")
            continue
        rows = read_jsonl(f)
        Xt = vec.transform([r[args.field][: args.max_chars] for r in rows])
        prob = clf.predict_proba(Xt)[:, native_col]
        pred = clf.predict(Xt)
        name = f.stem
        write_jsonl(out / f"{name}.jsonl", (
            {"id": r["id"], "lang": r["lang"], "host": r["host"], "section": r["section"],
             "label_gold": r["label"], "signals_gold": r["signals"], "label_pred": str(p),
             "prob_native": round(float(q), 6), "parse_ok": True, "label_source": "classifier", "condition": cond}
            for r, p, q in zip(rows, pred, prob)))
        acc = sum(str(p) == r["label"] for p, r in zip(pred, rows)) / len(rows)
        print(f"{name:20s} n={len(rows):5d} acc={100 * acc:.2f}")
    write_json(out / "run_config.json", {**cond, "tests": args.tests})


if __name__ == "__main__":
    main()
