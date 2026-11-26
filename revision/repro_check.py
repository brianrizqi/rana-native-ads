"""
Recompute reported numbers from the released per-article predictions (R2-8). CPU only, seconds.

    python revision/repro_check.py --pred-dir revision/release/predictions --report-dir revision/report \
        --tables ../ieee/tables

1. For every released prediction file, recompute accuracy, macro-F1 and MCC with stats.py's own
   functions and compare them with every metrics.csv row of the same run in --report-dir.
2. For the main results table (tbl_main.tex), parse each printed accuracy and compare it with the
   value recomputed from the released predictions.
Exit status 1 if any number differs by more than half a unit in its last printed digit.
"""

import argparse
import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LABELS, SIGNALS
from stats import mcc, prf

TBL_MAIN = {  # display name in tbl_main.tex -> released run directory
    "Gemma 3 12B (RANA)": "gemma3-12b__reasoning_first", "Gemma 3 4B": "gemma3-4b__reasoning_first",
    "Gemma 3 1B": "gemma3-1b__reasoning_first", "Gemma 3 270M": "gemma3-270m__reasoning_first",
    "Gemma 2 9B": "gemma2-9b__reasoning_first", "Qwen3 8B": "qwen3-8b__reasoning_first",
    "Qwen3.5 9B": "qwen3.5-9b__reasoning_first", "Qwen3.5 2B": "qwen3.5-2b__reasoning_first",
    "Qwen2.5 14B": "qwen2.5-14b__reasoning_first", "Llama 3.2 1B": "llama3.2-1b__reasoning_first",
    "DeepSeek-R1-Distill-Llama-8B": "deepseek-r1-llama-8b__reasoning_first",
}
TBL_MAIN_COLS = ((1, "test__norag"), (2, "test__rag_k5"), (5, "test_xsource__norag"), (6, "test_xsource__rag_k5"))


def score(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    gold = [r["label_gold"] for r in rows]
    pred = [r["label_pred"] if r["label_pred"] in LABELS else next(l for l in LABELS if l != g)
            for g, r in zip(gold, rows)]
    _, macro = prf(gold, pred, LABELS)
    return {"n": len(rows), "accuracy": sum(g == p for g, p in zip(gold, pred)) / len(rows),
            "macro_f1": macro, "mcc": mcc(gold, pred)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pred-dir", required=True)
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--tables", default=None)
    ap.add_argument("--compare", nargs=2, metavar=("RERUN", "RELEASED"), default=None,
                    help="Per-article agreement of a rerun (JSONL or CSV) with a released prediction file")
    a = ap.parse_args()

    if a.compare:
        def rows(p):
            if p.endswith(".csv"):
                with open(p, encoding="utf-8") as f:
                    return {r["id"]: r for r in csv.DictReader(f)}
            from common import read_jsonl
            return {str(r["id"]): {"label_pred": r.get("label_pred") or "",
                                   **{f"{s}_pred": (r.get("signals_pred") or {}).get(s, "") for s in SIGNALS}}
                    for r in read_jsonl(p)}
        x, y = rows(a.compare[0]), rows(a.compare[1])
        ids = sorted(set(x) & set(y))
        same_label = sum(x[i]["label_pred"] == y[i]["label_pred"] for i in ids)
        same_all = sum(all(x[i][k] == y[i][k] for k in ["label_pred"] + [f"{s}_pred" for s in SIGNALS]) for i in ids)
        print(f"{len(ids)} articles in both | identical label {same_label} ({100 * same_label / len(ids):.2f}%) | "
              f"identical label and four assessments {same_all} ({100 * same_all / len(ids):.2f}%)")
        return

    recomputed = {}
    for f in sorted(Path(a.pred_dir).glob("*/*.csv")):
        recomputed[f"{f.parent.name}/{f.stem}"] = score(f)
    print(f"recomputed {len(recomputed)} released prediction files")

    bad, checked = [], 0
    for m in sorted(Path(a.report_dir).glob("*/metrics.csv")):
        with open(m, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                run = row["run"]
                key = run if run in recomputed else run.replace("encoders__", "encoders__", 1)
                if key not in recomputed:
                    continue
                for metric in ("accuracy", "macro_f1", "mcc"):
                    checked += 1
                    if abs(float(row[metric]) - recomputed[key][metric]) > 5e-6:
                        bad.append(f"{m.parent.name}: {run} {metric} report={row[metric]} recomputed={recomputed[key][metric]:.6f}")
    print(f"metrics.csv: {checked} values compared, {len(bad)} differ")

    if a.tables:
        tex = (Path(a.tables) / "tbl_main.tex").read_text(encoding="utf-8")
        n_tab = 0
        for line in tex.splitlines():
            cells = [c.strip() for c in line.rstrip("\\ ").split("&")]
            if cells[0] in TBL_MAIN:
                for col, cond in TBL_MAIN_COLS:
                    key = f"{TBL_MAIN[cells[0]]}/{cond}"
                    printed = float(re.sub(r"[^\d.]", "", cells[col]))
                    n_tab += 1
                    if key not in recomputed:
                        bad.append(f"tbl_main: no released predictions for {key}")
                    elif abs(printed - 100 * recomputed[key]["accuracy"]) > 0.005 + 1e-9:
                        bad.append(f"tbl_main: {cells[0]} {cond} printed={printed} recomputed={100 * recomputed[key]['accuracy']:.3f}")
        print(f"tbl_main.tex: {n_tab} accuracies compared")

    for b in bad:
        print("  ✗", b)
    if bad:
        sys.exit(1)
    print("✅ every compared number is reproduced from the released predictions")


if __name__ == "__main__":
    main()
