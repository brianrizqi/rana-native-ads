"""Exports per-article predictions of every reported run for public release, without article text.

Each row keeps the article id, gold and predicted label, the four predicted signals, whether the
output parsed, and the ids and shown labels of the retrieved neighbors. Raw model output is left
out so that no copied article text can leak into the release.

    python revision/export_predictions.py --results revision/results --out revision/release/predictions

The run_config.json of every adapter (hyperparameters, seed, split hashes, package versions) is copied
to revision/release/run_configs/ without the per-step training log.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import SIGNALS, read_jsonl

COLUMNS = ["id", "lang", "label_gold", "label_pred", "parse_ok"] + [f"{s}_pred" for s in SIGNALS] + \
          ["neighbor_ids", "neighbor_labels_shown"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="revision/results")
    ap.add_argument("--out", default="revision/release/predictions")
    ap.add_argument("--models", default="revision/models")
    ap.add_argument("--configs-out", default="revision/release/run_configs")
    a = ap.parse_args()
    src, dst = Path(a.results), Path(a.out)
    n_files = 0
    for f in sorted(src.glob("*__*/*.jsonl")):
        rows = [r for r in read_jsonl(f) if "label_pred" in r]
        if not rows:
            continue
        out = dst / f.parent.name / (f.stem + ".csv")
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(COLUMNS)
            for r in rows:
                sig = r.get("signals_pred") or {}
                nb = r.get("neighbors") or []
                w.writerow([r["id"], r.get("lang", ""), r.get("label_gold"), r.get("label_pred"), r.get("parse_ok")]
                           + [sig.get(s, "") for s in SIGNALS]
                           + [";".join(str(n["id"]) for n in nb), ";".join(str(n.get("label_shown", "")) for n in nb)])
        n_files += 1
    print(f"✅ {n_files} prediction files -> {dst} (ids, labels and signals only; no text)")
    n_cfg = 0
    for f in sorted(Path(a.models).glob("*/run_config.json")):
        cfg = json.loads(f.read_text())
        cfg.pop("log_history", None)
        out = Path(a.configs_out) / f"{f.parent.name}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
        n_cfg += 1
    print(f"✅ {n_cfg} run configs -> {a.configs_out}")


if __name__ == "__main__":
    main()
