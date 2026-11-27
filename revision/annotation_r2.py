"""
Source-blinded re-annotation and inter-annotator agreement (R1 minor 2, R2-5, R2-2). CPU.

    # 1. sheets: a stratified sample of the corpus plus the new English set, sources hidden
    python revision/annotation_r2.py build --split-dir revision/splits/main --new revision/splits/en_ext/pool.jsonl \
        --n-id 150 --n-en 100 --annotators A1 A2 A3 --out-dir revision/annotation_r2
    # 2. after the annotators return their files
    python revision/annotation_r2.py analyze --out-dir revision/annotation_r2 --write-gold revision/splits/en_ext/test_en_ext.jsonl

Blinding: annotators see only the article text with outlet datelines, wire names and URLs removed (the same
cleaning every model input receives). They never see the URL, outlet, section, publication channel, original
label or any model output. Each annotator gets the items in a different random order. Sentences are numbered,
so annotators can name the sentences that support each signal they mark present (optional evidence columns,
used to compare with the occlusion attributions of faithfulness_occlusion.py).

analyze reports, overall and per stratum (Indonesian corpus, English corpus, new English publishers):
  Fleiss' kappa and Krippendorff's alpha (nominal) for each signal and the label, with 95% bootstrap intervals
  over items; agreement of the blind majority with the original corpus annotation (percent and Cohen's kappa);
  for the new English set, agreement of the blind majority label with the publisher's own disclosure; and the
  share of corpus articles labeled Native Ads by the all-four rule applied to the blind majority signals.
With --write-gold the new English articles are written as a test set whose label and signals are the blind
majority (positive tone: plurality; a three-way tie is recorded as netral and flagged).
"""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NATIVE, NEWS, SIGNALS, SIGNAL_VALUES, label_from_signals, read_jsonl, split_sentences, write_json, write_jsonl
from sheet_guides import add_guide, data_rows

FIELDS = list(SIGNALS) + ["label"]
CHOICES = {**{s: list(SIGNAL_VALUES[s]) for s in SIGNALS}, "label": [NATIVE, NEWS]}


def numbered(text):
    return "\n".join(f"[{i}] {s}" for i, s in enumerate(split_sentences(text), 1))


def cmd_build(a):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    rng = random.Random(a.seed)
    d = Path(a.split_dir)
    items = []
    test, xs = read_jsonl(d / "test.jsonl"), read_jsonl(d / "test_xsource.jsonl")
    def strat(rows, n, key):
        groups = {}
        for r in rows:
            groups.setdefault(key(r), []).append(r)
        for g in groups.values():
            rng.shuffle(g)
        out, ks = [], sorted(groups)
        while len(out) < n and any(groups.values()):
            for k in ks:
                if groups[k] and len(out) < n:
                    out.append(groups[k].pop())
        return out
    id_rows = strat([r for r in test if r["lang"] == "id"], a.n_id - a.n_id // 3, lambda r: (r["host"].split(".")[-2], r["label"]))
    id_rows += strat(xs, a.n_id // 3, lambda r: r["label"])
    en_rows = strat([r for r in test if r["lang"] == "en"], a.n_en, lambda r: r["label"])
    for r in id_rows:
        items.append({**r, "stratum": "corpus_id"})
    for r in en_rows:
        items.append({**r, "stratum": "corpus_en"})
    for f in a.new or []:
        for r in read_jsonl(f):
            items.append({**r, "stratum": "new_en"})
    rng.shuffle(items)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    header = ["item", "article"] + FIELDS + [f"evidence_{s}" for s in SIGNALS] + ["confidence", "comment"]
    widths = {"item": 6, "article": 90, "comment": 30}
    key = [{"item": n, "id": r["id"], "stratum": r["stratum"], "lang": r["lang"],
            "original_label": r.get("label"), "original_signals": r.get("signals"), "disclosed": r.get("disclosed"),
            "host": r.get("host")} for n, r in enumerate(items, 1)]
    for ann in a.annotators:
        order = items[:]
        random.Random(f"{a.seed}-{ann}").shuffle(order)
        pos = {r["id"]: i for i, r in enumerate(order)}
        wb = Workbook()
        ws = wb.active
        ws.title = "anotasi"
        ws.append(header)
        rows_sorted = sorted(enumerate(items, 1), key=lambda t: pos[t[1]["id"]])
        for n, r in rows_sorted:
            ws.append([n, numbered(r["text"][: a.max_chars])] + [""] * (len(header) - 2))
        last = len(items) + 1
        fill = PatternFill("solid", fgColor="FFF4CC")
        for j, name in enumerate(header, 1):
            col = ws.cell(row=1, column=j).column_letter
            ws.cell(row=1, column=j).font = Font(bold=True)
            ws.column_dimensions[col].width = widths.get(name, 15)
            if name in CHOICES:
                dv = DataValidation(type="list", formula1='"' + ",".join(CHOICES[name]) + '"', allow_blank=True,
                                    showErrorMessage=True, error="Pilih dari daftar.")
                ws.add_data_validation(dv)
                dv.add(f"{col}2:{col}{last}")
            if name == "confidence":
                dv = DataValidation(type="whole", operator="between", formula1="1", formula2="5", allow_blank=True)
                ws.add_data_validation(dv)
                dv.add(f"{col}2:{col}{last}")
            if name != "article" and name != "item":
                for i in range(2, last + 1):
                    ws.cell(row=i, column=j).fill = fill
        for row in ws.iter_rows(min_row=1, max_row=last):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "C2"
        add_guide(wb, "anotasi")
        wb.save(out / f"annotator_{ann}.xlsx")
    write_json(out / "key.json", {"annotators": a.annotators, "items": key, "max_chars": a.max_chars, "seed": a.seed})
    print(f"✅ {len(items)} items ({Counter(r['stratum'] for r in items)}) for {len(a.annotators)} annotators -> {out}")


def fleiss(table):
    """table: items x categories counts (each row sums to the number of raters of that item)."""
    t = np.asarray(table, float)
    t = t[t.sum(1) >= 2]
    if len(t) == 0:
        return float("nan")
    n = t.sum(1)
    p_i = ((t * (t - 1)).sum(1)) / (n * (n - 1))
    p_j = t.sum(0) / t.sum()
    pe = (p_j ** 2).sum()
    return float((p_i.mean() - pe) / (1 - pe)) if pe < 1 else float("nan")


def cohen(x, y):
    cats = sorted(set(x) | set(y))
    if len(x) == 0:
        return float("nan")
    po = np.mean([a == b for a, b in zip(x, y)])
    pe = sum((x.count(c) / len(x)) * (y.count(c) / len(y)) for c in cats)
    return float((po - pe) / (1 - pe)) if pe < 1 else float("nan")


def cmd_analyze(a):
    from judge import kalpha
    out = Path(a.out_dir)
    K = json.load(open(out / "key.json", encoding="utf-8"))
    anns = K["annotators"]
    sheets = {}
    for ann in anns:
        vals = data_rows(out / f"annotator_{ann}.xlsx", "anotasi")
        h = vals[0]
        sheets[ann] = {int(v[0]): {k: (str(x).strip().lower() if x is not None else "") for k, x in zip(h, v)}
                       for v in vals[1:] if v[0] is not None}
    items = K["items"]
    rng = np.random.default_rng(0)
    res = {"n_items": len(items), "annotators": anns}

    def values(field, subset):
        return [[sheets[x].get(it["item"], {}).get(field, "") for x in anns] for it in subset]

    def kappa_block(subset):
        blk = {}
        for f in FIELDS:
            V = values(f, subset)
            cats = CHOICES[f]
            table = [[sum(v == c for v in row) for c in cats] for row in V]
            k = fleiss(table)
            boots = []
            for _ in range(1000):
                idx = rng.integers(0, len(table), len(table))
                boots.append(fleiss([table[i] for i in idx]))
            codes = {c: i for i, c in enumerate(cats)}
            M = np.array([[codes.get(v, np.nan) for v in row] for row in V], float).T
            blk[f] = {"fleiss_kappa": k, "ci95": [float(np.nanquantile(boots, .025)), float(np.nanquantile(boots, .975))],
                      "kripp_alpha": kalpha(M, "nominal"), "n": len(table)}
        return blk

    strata = sorted({it["stratum"] for it in items})
    res["agreement"] = {"all": kappa_block(items), **{s: kappa_block([it for it in items if it["stratum"] == s]) for s in strata}}

    # blind majority
    major = {}
    for it in items:
        m = {}
        for f in FIELDS:
            vs = [v for v in (sheets[x].get(it["item"], {}).get(f, "") for x in anns) if v]
            c = Counter(vs).most_common()
            tie = len(c) > 1 and c[0][1] == c[1][1]
            m[f] = ("netral" if f == "positive_tone" else None) if (not c or tie) else c[0][0]
            m[f"{f}_tie"] = tie
        major[it["item"]] = m
    comp = {}
    for s in strata:
        sub = [it for it in items if it["stratum"] == s]
        d = {}
        if s.startswith("corpus"):
            for f in FIELDS:
                orig = [it["original_label"] if f == "label" else (it["original_signals"] or {}).get(f) for it in sub]
                blind = [major[it["item"]][f] for it in sub]
                ok = [(o, b) for o, b in zip(orig, blind) if o and b]
                d[f] = {"percent_agreement": float(np.mean([o == b for o, b in ok])) if ok else None,
                        "cohen_kappa": cohen([o for o, _ in ok], [b for _, b in ok]), "n": len(ok)}
            d["blind_all_four_rule_matches_original_label"] = float(np.mean(
                [label_from_signals({f: major[it["item"]][f] for f in SIGNALS}) == it["original_label"] for it in sub
                 if all(major[it["item"]][f] for f in SIGNALS)]))
        else:
            disc = [(it["disclosed"], major[it["item"]]["label"]) for it in sub if it.get("disclosed") is not None]
            if disc:
                d["blind_label_vs_disclosure"] = {
                    "percent_native_among_disclosed": float(np.mean([b == NATIVE for x, b in disc if int(x) == 1])),
                    "percent_native_among_editorial": float(np.mean([b == NATIVE for x, b in disc if int(x) == 0])),
                    "cohen_kappa": cohen([NATIVE if int(x) == 1 else NEWS for x, _ in disc], [b for _, b in disc]),
                    "n": len(disc)}
        comp[s] = d
    res["blind_majority_vs_reference"] = comp
    write_json(out / "agreement.json", res)
    # evidence sentences for the occlusion comparison
    ev = {it["id"]: {s: {x: sheets[x].get(it["item"], {}).get(f"evidence_{s}", "") for x in anns} for s in SIGNALS}
          for it in items}
    write_json(out / "evidence_sentences.json", ev)
    if a.write_gold:
        new_ids = {it["id"]: it for it in items if it["stratum"] == "new_en"}
        rows = []
        for f in a.new_files or []:
            for r in read_jsonl(f):
                if r["id"] in new_ids:
                    m = major[new_ids[r["id"]]["item"]]
                    if m["label"] is None:
                        continue
                    rows.append({**r, "label": m["label"], "signals": {s: m[s] or "tidak" for s in SIGNALS},
                                 "gold_from": "blind majority of 3", "ties": [f for f in FIELDS if m[f"{f}_tie"]]})
        write_jsonl(a.write_gold, rows)
        print(f"✅ gold test set ({len(rows)} articles) -> {a.write_gold}")
    print(json.dumps(res, indent=2)[:4000])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--split-dir", required=True)
    b.add_argument("--new", nargs="*", default=[], help="JSONL from collect_en.py (new English publishers)")
    b.add_argument("--n-id", type=int, default=150, help="Indonesian corpus articles; a third from the withheld publisher")
    b.add_argument("--n-en", type=int, default=100, help="English corpus articles")
    b.add_argument("--annotators", nargs="+", required=True)
    b.add_argument("--max-chars", type=int, default=6000)
    b.add_argument("--out-dir", required=True)
    b.add_argument("--seed", type=int, default=31)
    z = sub.add_parser("analyze")
    z.add_argument("--out-dir", required=True)
    z.add_argument("--write-gold", default=None)
    z.add_argument("--new-files", nargs="*", default=[])
    a = ap.parse_args()
    {"build": cmd_build, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
