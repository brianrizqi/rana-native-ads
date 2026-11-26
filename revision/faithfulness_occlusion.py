"""
Input-side faithfulness of the stated assessments: sentence occlusion (R2-4). GPU, about 1 s per generation.

    python revision/faithfulness_occlusion.py --model revision/models/gemma3-12b__reasoning_first \
        --test-file revision/splits/main/test.jsonl --out revision/results/faithfulness/occlusion_test.jsonl --max-samples 250
    python revision/faithfulness_occlusion.py --report revision/results/faithfulness/occlusion_*.jsonl \
        --out-dir revision/report/occlusion

The signal interventions of the first revision alter the model's OUTPUT (forced assessments). This script
alters the INPUT. For each article, the visible window (the first max_chars characters, as in training) is
split into sentences with common.split_sentences, and the model is rerun with:

  base           the full window
  drop_i         sentence i removed, for every i                      -> per-sentence attribution
  top_k / keep_k the k most influential sentences removed / kept only  (ERASER comprehensiveness / sufficiency)
  rand_k         k random sentences removed, --n-random draws          (baseline for top_k)

For every variant it records the regenerated assessments and label, and two probabilities of Native Ads,
each the two-way normalized likelihood of the label strings after '"label": "':
  p_native        given the assessments the model regenerated for that variant;
  p_native_fixed  given the assessments of the BASE output, forced into the answer.
If the four assessments mediated the decision completely, p_native_fixed would not move when a sentence
is removed; its movement is the part of the input's effect on the label that bypasses the assessments.
No retrieval is used by default, so the input text is the only thing that changes (--rag keeps the base
article's five neighbors fixed for every variant).
"""

import argparse
import glob
import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NATIVE, NEWS, SIGNALS, append_jsonl, label_from_signals, read_json, read_jsonl, split_sentences


def run(a):
    import os
    os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")
    import _server_compat  # noqa: F401
    from unsloth import FastLanguageModel
    import torch
    from prompts import LABEL_TEXT, apply_chat, build_prompt, forced_signal_prefix, parse_output
    from retrieval import Retriever

    cfg = read_json(Path(a.model) / "run_config.json")
    fmt = cfg["format"]
    assert fmt == "reasoning_first", "occlusion needs a reasoning_first adapter"
    max_chars, ref_chars = cfg.get("max_chars", 1500), cfg.get("neighbor_chars", 400)
    retriever = Retriever(cfg["index_dir"]) if a.rag else None

    rows = read_jsonl(a.test_file)[: a.max_samples]
    out = Path(a.out)
    done = {r["id"] for r in read_jsonl(out)} if out.exists() else set()
    todo = [r for r in rows if r["id"] not in done]
    print(f"{len(rows)} articles, {len(todo)} to run")
    if not todo:
        return
    model, tokenizer = FastLanguageModel.from_pretrained(model_name=a.model, max_seq_length=4096, dtype=None,
                                                         load_in_4bit=True, token=os.environ.get("HF_TOKEN"))
    FastLanguageModel.for_inference(model)
    tok = getattr(tokenizer, "tokenizer", tokenizer)
    tok.padding_side = "left"
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    @torch.no_grad()
    def generate(prompts):
        outs = []
        for s in range(0, len(prompts), a.batch_size):
            enc = tok(prompts[s:s + a.batch_size], return_tensors="pt", padding=True, add_special_tokens=False).to(model.device)
            gen = model.generate(**enc, max_new_tokens=128, do_sample=False, pad_token_id=tok.pad_token_id)
            outs += [tok.decode(g[enc["input_ids"].shape[1]:], skip_special_tokens=True) for g in gen]
        return outs

    @torch.no_grad()
    def logprob(contexts, continuations):
        """Sum of log-probabilities of each continuation given its context (teacher forcing)."""
        res = []
        for s in range(0, len(contexts), a.batch_size):
            ctx, cont = contexts[s:s + a.batch_size], continuations[s:s + a.batch_size]
            full_ids = [tok(c + x, add_special_tokens=False)["input_ids"] for c, x in zip(ctx, cont)]
            ctx_ids = [tok(c, add_special_tokens=False)["input_ids"] for c in ctx]
            starts = []
            for f, c in zip(full_ids, ctx_ids):  # first position where the joint tokenization departs from the context
                k = 0
                while k < min(len(f), len(c)) and f[k] == c[k]:
                    k += 1
                starts.append(min(k, len(f) - 1))
            L = max(map(len, full_ids))
            ids = torch.full((len(full_ids), L), tok.pad_token_id, dtype=torch.long)
            att = torch.zeros_like(ids)
            for i, f in enumerate(full_ids):  # left padding, as in generation
                ids[i, L - len(f):] = torch.tensor(f)
                att[i, L - len(f):] = 1
            logits = model(input_ids=ids.to(model.device), attention_mask=att.to(model.device)).logits.float()
            lp = torch.log_softmax(logits, -1)
            for i, f in enumerate(full_ids):
                off = L - len(f)
                tot = 0.0
                for pos in range(starts[i], len(f)):
                    tot += float(lp[i, off + pos - 1, f[pos]])
                res.append(tot)
        return res

    def p_native(prompts, signal_sets, lang):
        ctxs, conts = [], []
        for p, sig in zip(prompts, signal_sets):
            ctx = p + forced_signal_prefix(sig, lang) + '"label": "'
            for lab in (NATIVE, NEWS):
                ctxs.append(ctx)
                conts.append(LABEL_TEXT[lang][lab] + '"}')
        lps = logprob(ctxs, conts)
        return [1 / (1 + math.exp(lps[2 * i + 1] - lps[2 * i])) for i in range(len(prompts))]

    for r in todo:
        lang = "en" if r["lang"] == "en" else "id"
        sents = split_sentences(r["text"][:max_chars])[: a.max_sentences]
        nbs = None
        if retriever:
            nbs = retriever.search(retriever.query_vector(r), 5, query_lang=r["lang"], exclude_ids=[r["id"]],
                                   exclude_clusters=[r["cluster_id"]])

        def prompt_of(keep):
            text = " ".join(s for i, s in enumerate(sents) if i in keep)
            return apply_chat(tokenizer, build_prompt(text, lang, fmt, False, nbs, max_chars=max_chars, ref_chars=ref_chars))

        n = len(sents)
        variants = [("base", list(range(n)))] + [(f"drop_{i}", [j for j in range(n) if j != i]) for i in range(n)] if n > 1 \
            else [("base", list(range(n)))]
        prompts = [prompt_of(set(k)) for _, k in variants]
        raws = generate(prompts)
        parsed = [parse_output(x, fmt) for x in raws]
        base = parsed[0]
        if not base["signals"] or not base["label"]:
            append_jsonl(out, {"id": r["id"], "lang": r["lang"], "n_sentences": n, "base_valid": False, "raw": raws[0]})
            continue
        sig_now = [p["signals"] or base["signals"] for p in parsed]
        pn = p_native(prompts, sig_now, lang)
        pn_fixed = p_native(prompts, [base["signals"]] * len(prompts), lang)
        recs = [{"variant": v, "kept": k, "label": p["label"], "signals": p["signals"], "p_native": q, "p_native_fixed": qf}
                for (v, k), p, q, qf in zip(variants, parsed, pn, pn_fixed)]

        # ERASER-style deletion curves, ranked by the drop in probability of the base label
        sign = 1 if base["label"] == NATIVE else -1
        attr = sorted(range(n), key=lambda i: -sign * (recs[0]["p_native"] - recs[1 + i]["p_native"])) if n > 1 else []
        extra = []
        rng = random.Random(int(r["id"]) if str(r["id"]).isdigit() else 0)
        for kk in a.ks:
            if kk >= n:
                continue
            top = set(attr[:kk])
            extra.append((f"top_{kk}", [j for j in range(n) if j not in top]))
            extra.append((f"keep_{kk}", sorted(top)))
            for d in range(a.n_random):
                rem = set(rng.sample(range(n), kk))
                extra.append((f"rand_{kk}_{d}", [j for j in range(n) if j not in rem]))
        if extra:
            ep = [prompt_of(set(k)) for _, k in extra]
            er = [parse_output(x, fmt) for x in generate(ep)]
            eq = p_native(ep, [p["signals"] or base["signals"] for p in er], lang)
            eqf = p_native(ep, [base["signals"]] * len(ep), lang)
            recs += [{"variant": v, "kept": k, "label": p["label"], "signals": p["signals"], "p_native": q, "p_native_fixed": qf}
                     for (v, k), p, q, qf in zip(extra, er, eq, eqf)]
        append_jsonl(out, {"id": r["id"], "lang": r["lang"], "label_gold": r["label"], "signals_gold": r["signals"],
                           "n_sentences": n, "sentences": sents, "base_valid": True, "attribution_order": attr,
                           "variants": recs, "rag": bool(a.rag), "model": a.model})
        print(f"{r['id']}: {n} sentences, {len(recs)} variants")


def report(a):
    import csv
    import numpy as np
    rows = [x for p in a.report for f in sorted(glob.glob(p)) for x in read_jsonl(f)]
    valid = [x for x in rows if x.get("base_valid")]
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    res = {"n_articles": len(rows), "n_valid_base": len(valid)}
    drops = [(x, v) for x in valid for v in x["variants"] if v["variant"].startswith("drop_")]
    base = {x["id"]: x["variants"][0] for x in valid}
    lab_change = [(x, v) for x, v in drops if v["label"] and v["label"] != base[x["id"]]["label"]]
    res["single_sentence_removals"] = len(drops)
    res["label_changed"] = len(lab_change)
    res["label_changed_with_any_signal_change"] = sum(
        1 for x, v in lab_change if v["signals"] and any(v["signals"][s] != base[x["id"]]["signals"][s] for s in SIGNALS))
    res["label_after_follows_rule_over_new_signals"] = float(np.mean(
        [v["label"] == label_from_signals(v["signals"]) for _, v in drops if v["signals"] and v["label"]]))
    for s in SIGNALS:
        res[f"signal_changed_{s}"] = float(np.mean([bool(v["signals"]) and v["signals"][s] != base[x["id"]]["signals"][s]
                                                    for x, v in drops]))
    # mediated vs unmediated effect of removing a sentence on p(base label)
    def pb(x, v, key):
        p = v[key]
        return p if base[x["id"]]["label"] == NATIVE else 1 - p
    tot = [abs(pb(x, v, "p_native") - pb(x, base[x["id"]], "p_native")) for x, v in drops]
    fixed = [abs(pb(x, v, "p_native_fixed") - pb(x, base[x["id"]], "p_native_fixed")) for x, v in drops]
    res["mean_abs_effect_total"] = float(np.mean(tot))
    res["mean_abs_effect_with_assessments_fixed"] = float(np.mean(fixed))
    res["share_of_effect_not_through_assessments"] = float(np.sum(fixed) / np.sum(tot)) if np.sum(tot) else None
    # ERASER comprehensiveness / sufficiency versus random removal
    for k in a.ks:
        for kind in ("top", "keep", "rand"):
            vals = []
            for x in valid:
                b = pb(x, base[x["id"]], "p_native")
                vs = [v for v in x["variants"] if v["variant"] == f"{kind}_{k}" or v["variant"].startswith(f"{kind}_{k}_")]
                if vs:
                    vals.append(float(np.mean([b - pb(x, v, "p_native") for v in vs])))
            if vals:
                rng = np.random.default_rng(0)
                bs = [np.mean(rng.choice(vals, len(vals))) for _ in range(2000)]
                res[f"{ {'top': 'comprehensiveness', 'keep': 'sufficiency', 'rand': 'random_removal'}[kind] }_k{k}"] = \
                    {"mean": float(np.mean(vals)), "ci95": [float(np.quantile(bs, .025)), float(np.quantile(bs, .975))],
                     "n": len(vals)}
    with open(out / "occlusion_summary.json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    with open(out / "occlusion_per_article.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "lang", "label_gold", "base_label", "n_sentences", "n_label_changes"])
        for x in valid:
            w.writerow([x["id"], x["lang"], x["label_gold"], base[x["id"]]["label"], x["n_sentences"],
                        sum(1 for v in x["variants"] if v["variant"].startswith("drop_") and v["label"] != base[x["id"]]["label"])])
    print(json.dumps(res, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model")
    ap.add_argument("--test-file")
    ap.add_argument("--out")
    ap.add_argument("--max-samples", type=int, default=250)
    ap.add_argument("--max-sentences", type=int, default=20)
    ap.add_argument("--ks", type=int, nargs="+", default=[1, 3])
    ap.add_argument("--n-random", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--rag", action="store_true", help="Keep the base article's neighbors fixed in every variant")
    ap.add_argument("--report", nargs="+", default=None, help="Summarize occlusion files instead of running")
    ap.add_argument("--out-dir", default="revision/report/occlusion")
    a = ap.parse_args()
    if a.report:
        report(a)
    else:
        if not (a.model and a.test_file and a.out):
            ap.error("--model, --test-file and --out are required to run")
        run(a)


if __name__ == "__main__":
    main()
