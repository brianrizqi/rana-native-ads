"""Appendix tables: per-class metrics (Appendix A) and accuracy per content category (Appendix B).

Both are computed from released files only: report/baselines/metrics.csv for the per-class metrics, and
the per-article predictions in release/predictions with splits/main/ids_hashes.csv for the categories.
Categories use the same outlet-subdomain and URL-section rules as category_table.py (Table 3).

    python revision/appendix_tables.py --out-dir ieee/tables
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from category_table import RULES
from stats import wilson

HERE = Path(__file__).resolve().parent
MODELS = [("RANA", "gemma3-12b__reasoning_first", "{s}__rag_k5"),
          ("XLM-RoBERTa", "encoders__xlm-roberta-base", "{s}"),
          ("Multilingual BERT", "encoders__bert-base-multilingual-cased", "{s}"),
          ("IndoBERT", "encoders__indobert-base-p1", "{s}"),
          ("SENADA", "encoders__senada", "{s}"),
          ("kNN, bge-m3, weighted $k=5$", "knn/bge-m3", "{s}__weighted_k5")]
SETS = [("Test", "test"), ("Withheld", "test_xsource")]


def category(host, section):
    parts = [x for x in (section or "", (host or "").split(".")[0]) if x]
    for cat, keys in RULES:
        if any(part == k or part.startswith(k) for part in parts for k in keys):
            return cat
    return "Other"


def pc(v):
    return f"{100 * float(v):.2f}"


def table(env, caption, label, header, rows, colspec, size="\\footnotesize", colsep=None):
    lines = [f"\\begin{{{env}}}[t]", "\\renewcommand{\\tblwidth}{\\textwidth}%", size, "\\centering"]
    if colsep:
        lines.append(f"\\setlength{{\\tabcolsep}}{{{colsep}}}")
    lines += [
             f"\\caption{{{caption}}}\\label{{{label}}}",
             f"\\begin{{tabular*}}{{\\tblwidth}}{{@{{\\extracolsep{{\\fill}}}}{colspec}@{{}}}}", "\\toprule",
             " & ".join(h if "$" in h else f"\\textbf{{{h}}}" for h in header) + " \\\\", "\\midrule"]
    lines += [r if isinstance(r, str) else " & ".join(r) + " \\\\" for r in rows]
    lines += ["\\bottomrule", "\\end{tabular*}", f"\\end{{{env}}}"]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report-dir", default=str(HERE / "report"))
    ap.add_argument("--pred-dir", default=str(HERE / "release/predictions"))
    ap.add_argument("--ids", default=str(HERE / "splits/main/ids_hashes.csv"))
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    out = Path(a.out_dir)

    # Appendix A: per-class precision, recall, F1 and balanced accuracy
    met = {r["run"]: r for r in csv.DictReader(open(Path(a.report_dir) / "baselines/metrics.csv", encoding="utf-8"))}
    rows = []
    for i, (set_name, split) in enumerate(SETS):
        if i:
            rows.append("\\midrule")
        for name, run, cond in MODELS:
            m = met.get(f"{run}/{cond.format(s=split)}")
            if not m:
                continue
            rows.append([name, set_name] + [pc(m[f"{p}_{c}"]) for c in ("native_ads", "berita_murni")
                                            for p in ("precision", "recall", "f1")] + [pc(m["balanced_accuracy"])])
    (out / "tbl_appendix_class.tex").write_text(table(
        "table*", "Per-class precision, recall, and F1 (\\%) for Native Ads (NA) and Pure News (PN), and balanced "
        "accuracy, on the test partition and the withheld publisher.", "tbl_app_class",
        ["Model", "Set", "Prec. NA", "Rec. NA", "F1 NA", "Prec. PN", "Rec. PN", "F1 PN", "Bal. acc."], rows,
        "LLRRRRRRR"))

    # Appendix B: accuracy per content category with Wilson 95% intervals
    meta = {r["id"]: r for r in csv.DictReader(open(a.ids, encoding="utf-8"))}
    shown = MODELS[:3]
    acc = defaultdict(lambda: [0, 0])          # (set, category, model) -> [correct, n]
    for _, split in SETS:
        for name, run, cond in shown:
            for r in csv.DictReader(open(Path(a.pred_dir) / run / f"{cond.format(s=split)}.csv", encoding="utf-8")):
                m = meta[r["id"]]
                key = (split, category(m["host"], m["section"]), name)
                acc[key][0] += r["label_pred"] == r["label_gold"]
                acc[key][1] += 1
    cats = [c for c, _ in RULES] + ["Other"]
    rows = []
    for cat in cats:
        cells = [{"Branded content and press releases": "Branded, press rel."}.get(cat, cat.replace(" and ", ", "))]
        for _, split in SETS:
            n = acc[(split, cat, shown[0][0])][1]
            cells.append(f"{n:,}" if n else "--")
            for name, _, _ in shown:
                k, n = acc[(split, cat, name)]
                if n:
                    lo, hi = wilson(k, n)
                    cells.append(f"{100 * k / n:.1f} [{100 * lo:.1f}, {100 * hi:.1f}]")
                else:
                    cells.append("--")
        rows.append(cells)
    (out / "tbl_appendix_category.tex").write_text(table(
        "table*", "Accuracy (\\%) per content category (Table~\\ref{tbl2}) with Wilson 95\\% intervals for RANA, "
        "XLM-RoBERTa, and multilingual BERT on the test partition and the withheld publisher.", "tbl_app_cat",
        ["Category", "$n$ test", "RANA", "XLM-R", "mBERT", "$n$ withheld", "RANA", "XLM-R", "mBERT"], rows,
        "LRRRRRRRR", size="\\scriptsize", colsep="2pt"))
    print("written", out / "tbl_appendix_class.tex", out / "tbl_appendix_category.tex")


if __name__ == "__main__":
    main()
