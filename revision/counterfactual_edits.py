"""
Counterfactual input edits that remove one signal of promotional framing (R2-4). API calls + CPU.

    # 1. write the edited articles (OpenRouter; key from OPENROUTER_API_KEY), one test file per edit
    python revision/counterfactual_edits.py make --test-file revision/splits/main/test.jsonl \
        --out-dir revision/splits/counterfactual --n 150
    # 2. GPU: score every edited file with RANA exactly like a test set (queue_round2.sh does this)
    python revision/infer.py --model revision/models/gemma3-12b__reasoning_first \
        --test-file revision/splits/counterfactual/cf_single_perspective.jsonl \
        --out revision/results/gemma3-12b__reasoning_first/cf_single_perspective__norag.jsonl
    # 3. a human check of a sample of the edits, then the summary
    python revision/counterfactual_edits.py sheet --out-dir revision/splits/counterfactual --per-edit 30
    python revision/counterfactual_edits.py analyze --out-dir revision/splits/counterfactual \
        --base revision/results/gemma3-12b__reasoning_first/test__norag.jsonl \
        --edited "revision/results/gemma3-12b__reasoning_first/cf_*__norag.jsonl" --report revision/report/counterfactual

Source articles are test articles labeled Native Ads whose four annotated signals are all present. Each edit
rewrites the article window the model reads (the first --max-chars characters) and should remove exactly one
signal while keeping every fact, the length, and the other three signals:

  cf_single_perspective  add an attributed independent or critical viewpoint in place of one minor sentence
  cf_positive_tone       make evaluative wording neutral
  cf_persuasive          remove calls to action, superlatives and appeals to benefit
  cf_brand_promotion     replace the promoted brand, product or organization by a generic description
  cf_paraphrase          control: paraphrase with no change to any signal

Under the codebook each of the first four edits should turn the article into Pure News. The output-side
interventions of the first revision forced the assessments; these edits change the input, and test whether
the model notices the targeted signal and whether its label follows.
"""

import argparse
import csv
import glob
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NATIVE, NEWS, SIGNALS, label_from_signals, read_jsonl, write_json, write_jsonl

EDITS = {
    "single_perspective": ("Add one short, attributed independent or critical viewpoint (for example an analyst, a consumer "
                           "group, a competitor or an official who raises a doubt or a limitation) by replacing one minor "
                           "sentence, so that the article no longer presents a single perspective."),
    "positive_tone": "Rewrite the evaluative wording in a neutral, factual tone: no praise, no enthusiasm, no positive adjectives.",
    "persuasive": ("Remove persuasive language: calls to action, superlatives, appeals to benefit, exclamations and "
                   "promises addressed to the reader. Keep the information."),
    "brand_promotion": ("Replace every name of the promoted brand, product, company or institution by a generic description "
                        "(for example 'the company', 'the product', 'the regional government') and remove slogans."),
    "paraphrase": "Paraphrase the article sentence by sentence. Do not change its tone, viewpoint, persuasiveness or any name.",
}
KEEP = ("Keep every fact, number and the order of the content. Change nothing that the instruction does not ask for. "
        "Keep the language of the article ({lang}). Keep the length within 10% of the original. "
        "Return only JSON: {{\"text\": \"<edited article>\"}}")
PROMPT = "You edit news articles for a controlled experiment.\nInstruction: {edit}\n{keep}\n\nARTICLE:\n{text}"


def cmd_make(a):
    from judge import call_openrouter
    rows = [r for r in read_jsonl(a.test_file) if r["label"] == NATIVE and all(r["signals"][s] == "ya" for s in SIGNALS)]
    rng = random.Random(a.seed)
    rng.shuffle(rows)
    rows = rows[: a.n]
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, edit in EDITS.items():
        path = out / f"cf_{name}.jsonl"
        done = {r["id"] for r in read_jsonl(path)} if path.exists() else set()
        for r in rows:
            if r["id"] in done:
                continue
            window = r["text"][: a.max_chars]
            prompt = PROMPT.format(edit=edit, keep=KEEP.format(lang="Indonesian" if r["lang"] == "id" else "English"),
                                   text=window)
            text = None
            for _ in range(2):
                raw = call_openrouter(a.model, prompt)
                try:
                    cand = json.loads(raw)["text"].strip()
                except Exception:
                    continue
                if 0.75 * len(window) <= len(cand) <= 1.15 * len(window):
                    text = cand
                    break
            if text is None:
                print(f"   {name} {r['id']}: no valid edit, skipped")
                continue
            rec = {**r, "text": text, "text_original_window": window, "edit": name, "edit_model": a.model}
            rec.pop("text_raw", None)
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"✅ {path} ({sum(1 for _ in open(path, encoding='utf-8'))} edits)")
    write_json(out / "edit_config.json", {"model": a.model, "n_sources": len(rows), "seed": a.seed,
                                          "max_chars": a.max_chars, "edits": EDITS, "keep": KEEP})


def cmd_sheet(a):
    """Validation sheet: a sample of edits per type, for a human to confirm the targeted change and nothing else."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    out = Path(a.out_dir)
    wb = Workbook()
    ws = wb.active
    ws.title = "validasi_edit"
    head = ["item", "edit_instruction", "original", "edited", "target_removed (1/0)", "other_signals_unchanged (1/0)",
            "facts_preserved (1/0)", "comment"]
    ws.append(head)
    key, n = [], 0
    rng = random.Random(a.seed)
    for name in EDITS:
        rows = read_jsonl(out / f"cf_{name}.jsonl")
        for r in rng.sample(rows, min(a.per_edit, len(rows))):
            n += 1
            ws.append([n, EDITS[name], r["text_original_window"], r["text"], "", "", "", ""])
            key.append({"item": n, "id": r["id"], "edit": name})
    for j, w in enumerate((6, 40, 70, 70, 12, 12, 12, 30), 1):
        ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = w
        ws.cell(row=1, column=j).font = Font(bold=True)
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(out / "edit_validation.xlsx")
    write_json(out / "edit_validation.key.json", key)
    print(f"✅ {out / 'edit_validation.xlsx'} ({n} edits)")


def cmd_analyze(a):
    import numpy as np
    base = {r["id"]: r for r in read_jsonl(a.base)}
    res = {}
    for f in sorted(glob.glob(a.edited)):
        name = Path(f).stem.split("__")[0].replace("cf_", "")
        rows = [r for r in read_jsonl(f) if r["id"] in base and base[r["id"]].get("signals_pred") and r.get("signals_pred")]
        if not rows:
            continue
        target = name if name in SIGNALS else None
        b = [base[r["id"]] for r in rows]
        d = {"n": len(rows),
             "base_label_native": float(np.mean([x["label_pred"] == NATIVE for x in b])),
             "edited_label_native": float(np.mean([r["label_pred"] == NATIVE for r in rows])),
             "label_changed_native_to_news": float(np.mean([x["label_pred"] == NATIVE and r["label_pred"] == NEWS
                                                            for x, r in zip(b, rows)])),
             "label_follows_rule_over_new_signals": float(np.mean([r["label_pred"] == label_from_signals(r["signals_pred"])
                                                                   for r in rows]))}
        for s in SIGNALS:
            d[f"{s}_yes_before"] = float(np.mean([x["signals_pred"][s] == "ya" for x in b]))
            d[f"{s}_yes_after"] = float(np.mean([r["signals_pred"][s] == "ya" for r in rows]))
        if target:
            had = [(x, r) for x, r in zip(b, rows) if x["signals_pred"][target] == "ya"]
            d["target_removed_given_present"] = float(np.mean([r["signals_pred"][target] != "ya" for _, r in had])) if had else None
            d["off_target_changed"] = float(np.mean([any(r["signals_pred"][s] != x["signals_pred"][s] for s in SIGNALS if s != target)
                                                     for x, r in zip(b, rows)]))
            d["label_changed_when_target_removed"] = float(np.mean(
                [r["label_pred"] != x["label_pred"] for x, r in had if r["signals_pred"][target] != "ya"])) \
                if any(r["signals_pred"][target] != "ya" for _, r in had) else None
        res[name] = d
    Path(a.report).mkdir(parents=True, exist_ok=True)
    write_json(Path(a.report) / "counterfactual_summary.json", res)
    v = Path(a.out_dir) / "edit_validation.xlsx"
    if v.exists():
        from openpyxl import load_workbook
        key = {k["item"]: k for k in json.load(open(Path(a.out_dir) / "edit_validation.key.json"))}
        vals = list(load_workbook(v, read_only=True).active.iter_rows(values_only=True))[1:]
        agg = {}
        for row in vals:
            if row[0] is None or row[4] in (None, ""):
                continue
            e = key[int(row[0])]["edit"]
            agg.setdefault(e, []).append([float(row[4] or 0), float(row[5] or 0), float(row[6] or 0)])
        res["human_validation"] = {e: dict(zip(("target_removed", "others_unchanged", "facts_preserved"),
                                                np.mean(x, 0).round(3).tolist()), n=len(x)) for e, x in agg.items()}
        write_json(Path(a.report) / "counterfactual_summary.json", res)
    print(json.dumps(res, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--test-file", required=True)
    m.add_argument("--out-dir", required=True)
    m.add_argument("--n", type=int, default=150)
    m.add_argument("--max-chars", type=int, default=1500)
    m.add_argument("--model", default="openai/gpt-4o")
    m.add_argument("--seed", type=int, default=11)
    s = sub.add_parser("sheet")
    s.add_argument("--out-dir", required=True)
    s.add_argument("--per-edit", type=int, default=30)
    s.add_argument("--seed", type=int, default=12)
    z = sub.add_parser("analyze")
    z.add_argument("--out-dir", required=True)
    z.add_argument("--base", required=True, help="Predictions of the same model and condition on the unedited test set")
    z.add_argument("--edited", required=True, help="Glob of predictions on the cf_*.jsonl files")
    z.add_argument("--report", required=True)
    a = ap.parse_args()
    {"make": cmd_make, "sheet": cmd_sheet, "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
