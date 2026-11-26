"""
Rebuild the frozen partition from the article files and ids_hashes.csv, without rerunning
deduplication (R2-8, reproducibility). CPU only, about a minute.

    python revision/rebuild_split.py --xlsx native_ads_dataset.xlsx \
        --ids revision/splits/main/ids_hashes.csv --out-dir revision/splits/rebuilt \
        --expect revision/release/run_configs/gemma3-12b__reasoning_first.json

Every article is assigned the partition and duplicate cluster recorded in ids_hashes.csv, and its
normalized-text SHA-256 is checked against the recorded hash. Files are written exactly as
prepare_data.py writes them (same record fields, same order, same shuffle), so with --expect the
SHA-256 of each rebuilt file is compared with the hash stored in a run_config.json: a match means the
rebuilt train/val/test/test_xsource files are byte-identical to the ones every reported model used.
"""

import argparse
import csv
import hashlib
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import normalize_for_hash, read_json, sha256, write_jsonl
from prepare_data import load_records

SPLITS = ("train", "val", "test")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xlsx", required=True)
    ap.add_argument("--json", default=None, help="Optional: first-submission JSON, only for the row-alignment check")
    ap.add_argument("--ids", default=str(Path(__file__).resolve().parent / "splits" / "main" / "ids_hashes.csv"))
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=42, help="Shuffle seed used by prepare_data.py")
    ap.add_argument("--expect", default=None, help="run_config.json whose split_manifest hashes the files must match")
    args = ap.parse_args()

    with open(args.ids, encoding="utf-8") as f:
        ids = {r["id"]: r for r in csv.DictReader(f)}
    records = load_records(args.xlsx, args.json, mask_cues=True, min_chars=100)
    by_id = {r["id"]: r for r in records}

    missing = sorted(set(ids) - set(by_id))
    mismatch = []
    for i, meta in ids.items():
        r = by_id.get(i)
        if r is None:
            continue
        r["text_sha256"] = sha256(normalize_for_hash(r["text_raw"]))
        if r["text_sha256"] != meta["text_sha256"]:
            mismatch.append(i)
        r["cluster_id"] = meta["cluster_id"]
        r["split"] = meta["split"]
    print(f"{len(ids)} ids in manifest | {len(missing)} missing from the article file | {len(mismatch)} hash mismatches")
    if missing or mismatch:
        sys.exit(f"cannot rebuild: missing {missing[:10]}, mismatched {mismatch[:10]}")

    out = Path(args.out_dir)
    rows = [by_id[i] for i in ids]
    parts = {s: sorted((r for r in rows if r["split"] == s), key=lambda r: r["id"]) for s in SPLITS}
    rng = random.Random(args.seed)  # one generator, consumed train -> val -> test, as in prepare_data.py
    files = {}
    for s in SPLITS:
        rng.shuffle(parts[s])
        files[s] = out / f"{s}.jsonl"
        write_jsonl(files[s], parts[s])
    xs = sorted((r for r in rows if r["split"] == "test_xsource"), key=lambda r: r["id"])
    if xs:
        files["test_xsource"] = out / "test_xsource.jsonl"
        write_jsonl(files["test_xsource"], xs)
    excluded = [r for r in rows if r["split"] == "excluded"]
    if excluded:
        write_jsonl(out / "excluded.jsonl", excluded)

    got = {k: hashlib.sha256(p.read_bytes()).hexdigest() for k, p in files.items()}
    for k, h in got.items():
        print(f"{k:13s} n={sum(1 for _ in open(files[k], encoding='utf-8')):5d} sha256={h}")
    if args.expect:
        want = read_json(args.expect).get("split_manifest") or read_json(args.expect).get("split_file_sha256")
        want = {k.replace(".jsonl", ""): v for k, v in want.items()}
        bad = [k for k in got if k in want and want[k] != got[k]]
        if bad:
            sys.exit(f"❌ rebuilt files differ from the ones used in training: {bad}")
        print(f"✅ all {len(got)} rebuilt files are byte-identical to those recorded in {args.expect}")


if __name__ == "__main__":
    main()
