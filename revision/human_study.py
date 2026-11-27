"""
Human studies of the second revision (R2-3 retrieval for human decisions, R2-7 larger model comparison). CPU.

Study R (does showing the retrieved articles help a person decide?), crossover design
    python revision/human_study.py build-retrieval --pred revision/results/gemma3-12b__reasoning_first/test__rag_k5.jsonl \
        revision/results/gemma3-12b__reasoning_first/test_xsource__rag_k5.jsonl \
        --split-dir revision/splits/main --n 96 --raters R1 R2 R3 E1 E2 E3 --exclude-key revision/judge/human_sheet.key.json \
        --out-dir revision/human/retrieval
    python revision/human_study.py analyze-retrieval --out-dir revision/human/retrieval

  Articles are split into two blocks A and B, stratified by test set, gold label and whether RANA is right.
  Raters in group 1 see block A with the five retrieved articles and block B without them; group 2 the reverse.
  Every rater sees every article once, in a random order that interleaves the two conditions, and every article
  is seen in both conditions by different raters. About a third of the articles are ones RANA gets wrong, so the
  study can measure whether retrieved precedents help a person catch a wrong label. Raters record their own
  decision (1 Native Ads, 0 Pure News), whether they accept RANA's label (1/0), their confidence (1-5) and,
  optionally, the minutes spent.

Study M (which model's output is more useful?), within-article design
    python revision/human_study.py build-models --pred-glob "revision/results/{m}__reasoning_first/test__rag_k5.jsonl" \
        --models gemma3-12b qwen3-8b gemma2-9b deepseek-r1-llama-8b --split-dir revision/splits/main --n 60 \
        --raters E1 E2 E3 R1 R2 R3 --exclude-key revision/judge/human_sheet.key.json --out-dir revision/human/models
    python revision/human_study.py analyze-models --out-dir revision/human/models

  Each article appears once, with the outputs of all four models below it in a random order labeled A-D, so model
  differences are measured on the same articles. Per output, raters accept or reject the label and each of the
  four assessments (1/0) and rate editorial usefulness (1-5).

Existing 120-article study of the first revision, with intervals and tests added
    python revision/human_study.py analyze-legacy --key revision/judge/human_sheet.key.json \
        --raters revision/judge/rater_A.xlsx revision/judge/rater_B.xlsx revision/judge/rater_C.xlsx \
        --out revision/report/human_legacy.json

Intervals are two-way cluster bootstraps (articles and raters resampled together); tests are paired over
articles. Holm correction within each family.
"""

import argparse
import csv
import glob
import itertools
import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NATIVE, NEWS, SIGNALS, read_jsonl, write_json
from sheet_guides import add_guide, data_rows
from stats import holm

LAB_ID = {NATIVE: "Native Ads", NEWS: "Pure News"}
VAL = {"ya": "yes", "netral": "neutral", "tidak": "no"}
SIG_NAME = {"positive_tone": "Positive tone", "persuasive": "Persuasive language",
            "brand_promotion": "Brand promotion", "single_perspective": "Single perspective"}


def readable_output(p):
    sig = p.get("signals_pred") or {}
    lines = [f"{SIG_NAME[s]}: {VAL.get(sig.get(s), '-')}" for s in SIGNALS]
    return "\n".join(lines + [f"LABEL: {LAB_ID.get(p.get('label_pred'), 'invalid')}"])


def readable_neighbors(p, train_text, chars=300):
    return "\n\n".join(f"[{i}] {LAB_ID.get(n.get('label_shown'), n.get('label_shown'))}: "
                       f"{' '.join(train_text.get(n['id'], '').split())[:chars]}..."
                       for i, n in enumerate(p.get("neighbors") or [], 1))


def excluded_ids(paths):
    out = set()
    for p in paths or []:
        out |= {str(k["id"]) for k in json.load(open(p, encoding="utf-8"))}
    return out


def texts(split_dir):
    d = Path(split_dir)
    t = {}
    for f in ("test", "test_xsource", "train"):
        if (d / f"{f}.jsonl").exists():
            t[f] = {r["id"]: r["text"] for r in read_jsonl(d / f"{f}.jsonl")}
    return t


def save_xlsx(path, header, rows, widths, binary=(), scale=(), choice=(), guide=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    wb = Workbook()
    ws = wb.active
    ws.title = "penilaian"
    ws.append(header)
    for r in rows:
        ws.append(r)
    last = len(rows) + 1
    dvs = {"bin": DataValidation(type="whole", operator="between", formula1="0", formula2="1", allow_blank=True,
                                 error="Isi 1 atau 0.", showErrorMessage=True),
           "scale": DataValidation(type="whole", operator="between", formula1="1", formula2="5", allow_blank=True,
                                   error="Isi angka bulat 1 sampai 5.", showErrorMessage=True)}
    for dv in dvs.values():
        ws.add_data_validation(dv)
    fill = PatternFill("solid", fgColor="FFF4CC")
    for j, name in enumerate(header, 1):
        col = ws.cell(row=1, column=j).column_letter
        ws.cell(row=1, column=j).font = Font(bold=True)
        ws.column_dimensions[col].width = widths.get(name, 14)
        kind = "bin" if name in binary else "scale" if name in scale else None
        if kind:
            dvs[kind].add(f"{col}2:{col}{last}")
        if kind or name in choice:
            for i in range(2, last + 1):
                ws.cell(row=i, column=j).fill = fill
    for row in ws.iter_rows(min_row=1, max_row=last):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "B2"
    if guide:
        add_guide(wb, guide)
    wb.save(path)


def read_sheet(path):
    vals = data_rows(path, "penilaian")
    return {int(float(r[0])): {h: r[j] for j, h in enumerate(vals[0])} for r in vals[1:] if r[0] is not None}


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def cluster_boot(M, fn, n_boot=2000, seed=0):
    """M: raters x items array (nan = not rated). Resample raters and items with replacement."""
    rng = np.random.default_rng(seed)
    R, I = M.shape
    out = []
    for _ in range(n_boot):
        ri, ii = rng.integers(0, R, R), rng.integers(0, I, I)
        v = fn(M[np.ix_(ri, ii)])
        if not np.isnan(v):
            out.append(v)
    return [float(np.quantile(out, .025)), float(np.quantile(out, .975))] if out else [None, None]


def signflip_p(d, n_perm=20000, seed=0):
    d = np.asarray([x for x in d if not np.isnan(x)])
    if len(d) == 0 or np.all(d == 0):
        return 1.0
    rng = np.random.default_rng(seed)
    obs = abs(d.mean())
    flips = rng.choice([-1, 1], size=(n_perm, len(d)))
    return float(((np.abs((flips * d).mean(1)) >= obs - 1e-12).sum() + 1) / (n_perm + 1))


# ---------------------------------------------------------------- Study R

def cmd_build_retrieval(a):
    rng = random.Random(a.seed)
    T = texts(a.split_dir)
    skip = excluded_ids(a.exclude_key)
    pool = []
    for f in a.pred:
        tset = "test_xsource" if "xsource" in Path(f).name else "test"
        for p in read_jsonl(f):
            if str(p["id"]) in skip or not p.get("signals_pred") or not p.get("neighbors"):
                continue
            pool.append({**p, "_set": tset, "_right": p["label_pred"] == p["label_gold"]})
    per_set = a.n // len(a.pred)
    chosen = []
    for tset in sorted({p["_set"] for p in pool}):
        for right, share in ((False, a.error_share), (True, 1 - a.error_share)):
            for gold in (NATIVE, NEWS):
                cell = [p for p in pool if p["_set"] == tset and p["_right"] == right and p["label_gold"] == gold]
                rng.shuffle(cell)
                chosen += cell[: round(per_set * share / 2)]
    rng.shuffle(chosen)
    # blocks A / B stratified by (set, right, gold): alternate within each stratum
    seen = {}
    for p in chosen:
        k = (p["_set"], p["_right"], p["label_gold"])
        p["_block"] = "AB"[seen.get(k, 0) % 2]
        seen[k] = seen.get(k, 0) + 1
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    header = ["item", "article", "assistant_output", "retrieved_examples", "your_decision_native (1/0)",
              "accept_model_label (1/0)", "confidence (1-5)", "minutes", "comment"]
    widths = {"item": 6, "article": 80, "assistant_output": 28, "retrieved_examples": 60, "comment": 30}
    key = {"items": [], "raters": {}}
    for ri, rater in enumerate(a.raters):
        group = 1 + ri % 2
        order = chosen[:]
        random.Random(f"{a.seed}-{rater}").shuffle(order)
        rows = []
        for n, p in enumerate(order, 1):
            with_ret = (p["_block"] == "A") == (group == 1)
            rows.append([n, T[p["_set"]][p["id"]][:3000], readable_output(p),
                         readable_neighbors(p, T["train"]) if with_ret else "(not shown for this article)",
                         "", "", "", "", ""])
            key["items"].append({"rater": rater, "item": n, "id": p["id"], "set": p["_set"], "block": p["_block"],
                                 "with_retrieval": with_ret, "gold": p["label_gold"], "model_label": p["label_pred"]})
        key["raters"][rater] = group
        save_xlsx(out / f"rater_{rater}.xlsx", header, rows, widths,
                  binary=("your_decision_native (1/0)", "accept_model_label (1/0)"), scale=("confidence (1-5)",),
                  choice=("minutes", "comment"), guide="studi_r")
    write_json(out / "key.json", key)
    print(f"✅ {len(chosen)} articles, {len(a.raters)} raters -> {out} (key.json stays with the authors)")


def cmd_analyze_retrieval(a):
    out = Path(a.out_dir)
    key = json.load(open(out / "key.json", encoding="utf-8"))
    raters = sorted(key["raters"])
    sheets = {r: read_sheet(out / f"rater_{r}.xlsx") for r in raters}
    ids = sorted({k["id"] for k in key["items"]})
    col = {i: j for j, i in enumerate(ids)}
    shape = (len(raters), len(ids))
    M = {c: {w: np.full(shape, np.nan) for w in (True, False)} for c in ("correct", "accept", "conf", "minutes")}
    meta = {}
    for k in key["items"]:
        row = sheets[k["rater"]].get(k["item"], {})
        ri, j, w = raters.index(k["rater"]), col[k["id"]], k["with_retrieval"]
        dec = num(row.get("your_decision_native (1/0)"))
        if not np.isnan(dec):
            M["correct"][w][ri, j] = float((dec == 1) == (k["gold"] == NATIVE))
        M["accept"][w][ri, j] = num(row.get("accept_model_label (1/0)"))
        M["conf"][w][ri, j] = num(row.get("confidence (1-5)"))
        M["minutes"][w][ri, j] = num(row.get("minutes"))
        meta[k["id"]] = {"model_right": k["model_label"] == k["gold"], "set": k["set"]}
    model_right = np.array([meta[i]["model_right"] for i in ids])
    res = {"n_articles": len(ids), "n_raters": len(raters)}
    tests = []
    def summarize(name, mats, mask=None):
        mk = np.ones(len(ids), bool) if mask is None else mask
        d = {}
        for w in (True, False):
            m = mats[w][:, mk]
            d["with" if w else "without"] = {"mean": float(np.nanmean(m)), "ci95": cluster_boot(m, np.nanmean),
                                             "n_ratings": int((~np.isnan(m)).sum())}
        diff_art = np.nanmean(mats[True][:, mk], 0) - np.nanmean(mats[False][:, mk], 0)
        d["diff_with_minus_without"] = float(np.nanmean(diff_art))
        d["p_signflip_over_articles"] = signflip_p(diff_art)
        tests.append((name, d))
        res[name] = d
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    summarize("decision_accuracy", M["correct"])
    summarize("decision_accuracy_when_model_wrong", M["correct"], ~model_right)
    summarize("decision_accuracy_when_model_right", M["correct"], model_right)
    summarize("accepts_wrong_model_label", M["accept"], ~model_right)
    summarize("accepts_correct_model_label", M["accept"], model_right)
    summarize("confidence", M["conf"])
    if np.isfinite(np.nanmean(M["minutes"][True])):
        summarize("minutes", M["minutes"])
    for (name, d), h in zip(tests, holm([d["p_signflip_over_articles"] for _, d in tests])):
        d["p_holm"] = h
    try:  # mixed-effects logistic regression, if statsmodels is installed
        import pandas as pd
        from statsmodels.genmod.bayes_mixed_glm import BinomialBayesMixedGLM
        recs = [{"y": M["correct"][w][r, j], "with": int(w), "rater": raters[r], "article": ids[j]}
                for w in (True, False) for r in range(shape[0]) for j in range(shape[1]) if not np.isnan(M["correct"][w][r, j])]
        df = pd.DataFrame(recs)
        fit = BinomialBayesMixedGLM.from_formula("y ~ with", {"rater": "0 + C(rater)", "article": "0 + C(article)"}, df).fit_vb()
        res["mixed_logit_with_retrieval"] = {"coef": float(fit.fe_mean[1]), "sd": float(fit.fe_sd[1])}
    except Exception as e:
        res["mixed_logit_with_retrieval"] = f"not run ({type(e).__name__})"
    write_json(out / "analysis.json", res)
    print(json.dumps(res, indent=2))


# ---------------------------------------------------------------- Study M

def cmd_build_models(a):
    rng = random.Random(a.seed)
    T = texts(a.split_dir)
    skip = excluded_ids(a.exclude_key)
    preds = {m: {p["id"]: p for p in read_jsonl(a.pred_glob.format(m=m))} for m in a.models}
    common_ids = sorted(set.intersection(*[set(v) for v in preds.values()]) - skip)
    common_ids = [i for i in common_ids if all(preds[m][i].get("signals_pred") for m in a.models)]
    # half the articles where at least two models disagree on the label, so the comparison is informative
    split = [i for i in common_ids if len({preds[m][i]["label_pred"] for m in a.models}) > 1]
    agree = [i for i in common_ids if i not in set(split)]
    rng.shuffle(split)
    rng.shuffle(agree)
    chosen = split[: a.n // 2] + agree[: a.n - min(len(split), a.n // 2)]
    rng.shuffle(chosen)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    header = ["item", "output", "article", "retrieved_examples", "assistant_output", "label_ok"] + \
             [f"{s}_ok" for s in SIGNALS] + ["editorial_usefulness", "comment"]
    widths = {"item": 6, "output": 7, "article": 70, "retrieved_examples": 45, "assistant_output": 28, "comment": 25}
    key = []
    rows = []
    for n, i in enumerate(chosen, 1):
        order = a.models[:]
        rng.shuffle(order)
        for letter, m in zip("ABCD", order):
            p = preds[m][i]
            first = letter == "A"
            rows.append([n, letter, T["test"][i][:3000] if first else "(same article as above)",
                         readable_neighbors(p, T["train"]) if first else "(same as above)", readable_output(p),
                         "", "", "", "", "", "", ""])
            key.append({"item": n, "output": letter, "id": i, "model": m, "gold": p["label_gold"],
                        "label_pred": p["label_pred"], "signals_pred": p["signals_pred"], "signals_gold": p["signals_gold"]})
    for r in a.raters:
        save_xlsx(out / f"rater_{r}.xlsx", header, rows, widths,
                  binary=["label_ok"] + [f"{s}_ok" for s in SIGNALS], scale=("editorial_usefulness",), choice=("comment",), guide="studi_m")
    write_json(out / "key.json", {"models": a.models, "raters": a.raters, "items": key})
    print(f"✅ {len(chosen)} articles x {len(a.models)} outputs, {len(a.raters)} raters -> {out}")


def kalpha_nominal_or_interval(m, metric):
    from judge import kalpha
    return kalpha(m, metric)


def cmd_analyze_models(a):
    from scipy.stats import chi2, friedmanchisquare
    out = Path(a.out_dir)
    K = json.load(open(out / "key.json", encoding="utf-8"))
    models, raters = K["models"], K["raters"]
    rows_by_rater = {}  # the four outputs of an article share its item number, so rows are keyed by (item, output)
    for r in raters:
        vals = data_rows(out / f"rater_{r}.xlsx", "penilaian")
        h = vals[0]
        rows_by_rater[r] = {(int(float(v[0])), v[1]): dict(zip(h, v)) for v in vals[1:] if v[0] is not None}
    items = sorted({k["item"] for k in K["items"]})
    cols = ["label_ok"] + [f"{s}_ok" for s in SIGNALS] + ["editorial_usefulness"]
    X = {m: {c: np.full((len(raters), len(items)), np.nan) for c in cols} for m in models}
    for k in K["items"]:
        for ri, r in enumerate(raters):
            row = rows_by_rater[r].get((k["item"], k["output"]), {})
            for c in cols:
                X[k["model"]][c][ri, items.index(k["item"])] = num(row.get(c))
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    res = {"n_articles": len(items), "n_raters": len(raters), "per_model": {}, "agreement": {}}
    for m in models:
        res["per_model"][m] = {c: {"mean": float(np.nanmean(X[m][c])), "ci95": cluster_boot(X[m][c], np.nanmean)}
                               for c in ("label_ok", "editorial_usefulness")}
        res["per_model"][m]["signals_ok"] = {"mean": float(np.nanmean([np.nanmean(X[m][f"{s}_ok"]) for s in SIGNALS]))}
    for c in cols:
        stacked = np.concatenate([X[m][c] for m in models], axis=1)
        res["agreement"][f"alpha_{c}"] = kalpha_nominal_or_interval(stacked, "nominal" if c.endswith("_ok") else "interval")
    # omnibus tests over articles (article-level mean over raters)
    art = {m: {c: np.nanmean(X[m][c], 0) for c in cols} for m in models}
    lab = np.vstack([art[m]["label_ok"] for m in models]).T  # articles x models, proportion of raters accepting
    lab_bin = (lab >= 0.5).astype(float)
    ok = ~np.isnan(lab).any(1)
    k_ = len(models)
    T_, C_ = lab_bin[ok].sum(1), lab_bin[ok].sum(0)
    q_den = (k_ * T_.sum() - (T_ ** 2).sum())
    Q = (k_ - 1) * (k_ * (C_ ** 2).sum() - T_.sum() ** 2) / q_den if q_den else 0.0
    res["cochran_q_label_majority"] = {"Q": float(Q), "df": k_ - 1, "p": float(chi2.sf(Q, k_ - 1))}
    use = np.vstack([art[m]["editorial_usefulness"] for m in models]).T
    okk = ~np.isnan(use).any(1)
    res["friedman_usefulness"] = dict(zip(("stat", "p"), map(float, friedmanchisquare(*use[okk].T))))
    pairs = []
    ref = models[0]
    for m in models[1:]:
        for c in ("label_ok", "editorial_usefulness"):
            d = art[ref][c] - art[m][c]
            pairs.append({"A": ref, "B": m, "measure": c, "diff": float(np.nanmean(d)), "p": signflip_p(d)})
    for p, h in zip(pairs, holm([p["p"] for p in pairs])):
        p["p_holm"] = h
    res["pairwise_vs_first_model"] = pairs
    write_json(out / "analysis.json", res)
    print(json.dumps(res, indent=2))


def cmd_analyze_legacy(a):
    """First-revision study: different articles per model, so model comparisons are between articles."""
    key = json.load(open(a.key, encoding="utf-8"))
    sheets = [read_sheet(f) for f in a.raters]
    res = {"per_model": {}, "pairwise_vs_rana": []}
    import warnings
    warnings.filterwarnings("ignore", category=RuntimeWarning)
    by_model = {}
    for k in key:
        m = Path(k["run"]).parent.name
        vals = {c: [num(s.get(k["item"], {}).get(c)) for s in sheets] for c in ("label_ok", "editorial_usefulness")}
        by_model.setdefault(m, []).append(vals)
    for m, items in by_model.items():
        d = {}
        for c in ("label_ok", "editorial_usefulness"):
            M = np.array([v[c] for v in items]).T  # raters x items
            d[c] = {"mean": float(np.nanmean(M)), "ci95": cluster_boot(M, np.nanmean), "n_items": M.shape[1]}
        res["per_model"][m] = d
    ref = next(m for m in by_model if m.startswith("gemma3-12b"))
    rng = np.random.default_rng(0)
    for m in by_model:
        if m == ref:
            continue
        for c in ("label_ok", "editorial_usefulness"):
            x = np.array([np.nanmean(v[c]) for v in by_model[ref]])
            y = np.array([np.nanmean(v[c]) for v in by_model[m]])
            obs = np.nanmean(x) - np.nanmean(y)
            allv = np.concatenate([x, y])
            perm = []
            for _ in range(20000):
                rng.shuffle(allv)
                perm.append(np.nanmean(allv[: len(x)]) - np.nanmean(allv[len(x):]))
            p = float((np.sum(np.abs(perm) >= abs(obs) - 1e-12) + 1) / (len(perm) + 1))
            res["pairwise_vs_rana"].append({"model": m, "measure": c, "diff_rana_minus_model": float(obs), "p_permutation": p})
    for p, h in zip(res["pairwise_vs_rana"], holm([p["p_permutation"] for p in res["pairwise_vs_rana"]])):
        p["p_holm"] = h
    write_json(a.out, res)
    print(json.dumps(res, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-retrieval")
    b.add_argument("--pred", nargs="+", required=True, help="RANA RAG predictions (test and test_xsource)")
    b.add_argument("--split-dir", required=True)
    b.add_argument("--n", type=int, default=96)
    b.add_argument("--error-share", type=float, default=1 / 3)
    b.add_argument("--raters", nargs="+", required=True, help="Even number: alternate raters go to groups 1 and 2")
    b.add_argument("--exclude-key", nargs="*", default=[])
    b.add_argument("--out-dir", required=True)
    b.add_argument("--seed", type=int, default=21)
    r = sub.add_parser("analyze-retrieval")
    r.add_argument("--out-dir", required=True)
    m = sub.add_parser("build-models")
    m.add_argument("--pred-glob", required=True, help="Path with {m} for the model key")
    m.add_argument("--models", nargs="+", required=True, help="First model is the reference for pairwise tests")
    m.add_argument("--split-dir", required=True)
    m.add_argument("--n", type=int, default=60)
    m.add_argument("--raters", nargs="+", required=True)
    m.add_argument("--exclude-key", nargs="*", default=[])
    m.add_argument("--out-dir", required=True)
    m.add_argument("--seed", type=int, default=22)
    z = sub.add_parser("analyze-models")
    z.add_argument("--out-dir", required=True)
    g = sub.add_parser("analyze-legacy")
    g.add_argument("--key", required=True)
    g.add_argument("--raters", nargs="+", required=True)
    g.add_argument("--out", required=True)
    a = ap.parse_args()
    {"build-retrieval": cmd_build_retrieval, "analyze-retrieval": cmd_analyze_retrieval, "build-models": cmd_build_models,
     "analyze-models": cmd_analyze_models, "analyze-legacy": cmd_analyze_legacy}[a.cmd](a)


if __name__ == "__main__":
    main()
