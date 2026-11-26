"""
Derived partitions for the cross-publisher experiments of the second revision (R2-1). CPU, seconds.

Every derived partition is built from the frozen main partition, so the main test files are never
changed and every derived file is traceable to it. Duplicate clusters are never split.

    python revision/make_splits_r2.py --main revision/splits/main --out-root revision/splits

Writes:
  outlet_balanced/    train and val downsampled so that, within every outlet, both classes are equally
                      frequent: outlet identity no longer predicts the label. test and test_xsource are the
                      main files (copied byte for byte).
  size_matched/       control for outlet_balanced: a random subsample of train and val of the same sizes,
                      without balancing, so a change can be attributed to balancing rather than to less data.
  lopo_<outlet>/      leave-one-publisher-out: every article of <outlet> is removed from train and val (with
                      any article that shares a duplicate cluster with it); test = main test without <outlet>;
                      test_xsource = all articles of <outlet>; test_cnn = the main withheld publisher.
  adapt_pool.jsonl,   target-publisher adaptation: the main withheld publisher split by duplicate cluster into
  adapt_<N>/          a labeled pool (up to --pool articles, label-balanced) and a fixed evaluation set.
                      adapt_<N>/train.jsonl = main train + the first N pool articles (nested subsets);
                      adapt_<N>/test_xsource.jsonl = the evaluation set, identical for every N, so N = 0 is
                      the main model scored on the same articles.
Each directory gets a manifest.json with counts and SHA-256 of every file.
"""

import argparse
import hashlib
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import NATIVE, NEWS, read_jsonl, write_json, write_jsonl


def outlet_of(r):
    return r.get("outlet") or r["host"]


def manifest(d: Path, extra=None):
    files = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(d.glob("*.jsonl"))}
    counts = {}
    for f in sorted(d.glob("*.jsonl")):
        rows = read_jsonl(f)
        counts[f.stem] = {"n": len(rows), "by_lang_label": dict(sorted(Counter(f"{r['lang']}|{r['label']}" for r in rows).items())),
                          "by_outlet": dict(sorted(Counter(outlet_of(r) for r in rows).items()))}
    write_json(d / "manifest.json", {**(extra or {}), "counts": counts, "file_sha256": files})
    print(f"✅ {d}: " + ", ".join(f"{k}={v['n']}" for k, v in counts.items()))


def copy_main(main: Path, d: Path, names):
    for n in names:
        if (main / f"{n}.jsonl").exists():
            shutil.copyfile(main / f"{n}.jsonl", d / f"{n}.jsonl")


def balance_by_outlet(rows, rng):
    """Within each outlet keep min(#Native Ads, #Pure News) articles of each class, sampled at random."""
    groups = defaultdict(list)
    for r in rows:
        groups[(outlet_of(r), r["label"])].append(r)
    keep = []
    for o in sorted({k[0] for k in groups}):
        na, pn = groups.get((o, NATIVE), []), groups.get((o, NEWS), [])
        m = min(len(na), len(pn))
        keep += rng.sample(sorted(na, key=lambda r: r["id"]), m) + rng.sample(sorted(pn, key=lambda r: r["id"]), m)
    rng.shuffle(keep)
    return keep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--main", default="revision/splits/main")
    ap.add_argument("--out-root", default="revision/splits")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--lopo", default="viva.co.id,sindonews.com",
                    help="Outlets to withhold one at a time; both have enough articles of each class")
    ap.add_argument("--pool", type=int, default=400, help="Labeled target-publisher articles available for adaptation")
    ap.add_argument("--adapt-n", default="50,100,200,400")
    args = ap.parse_args()

    main_dir, root = Path(args.main), Path(args.out_root)
    train, val = read_jsonl(main_dir / "train.jsonl"), read_jsonl(main_dir / "val.jsonl")
    test, xs = read_jsonl(main_dir / "test.jsonl"), read_jsonl(main_dir / "test_xsource.jsonl")

    # 1. outlet-balanced training data, and its size-matched random control
    rng = random.Random(args.seed)
    d = root / "outlet_balanced"
    d.mkdir(parents=True, exist_ok=True)
    btr, bva = balance_by_outlet(train, rng), balance_by_outlet(val, rng)
    write_jsonl(d / "train.jsonl", btr)
    write_jsonl(d / "val.jsonl", bva)
    copy_main(main_dir, d, ("test", "test_xsource"))
    manifest(d, {"derived_from": str(main_dir), "rule": "per outlet, min(#NA, #PN) of each class", "seed": args.seed})

    d = root / "size_matched"
    d.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed + 1)
    write_jsonl(d / "train.jsonl", rng.sample(train, len(btr)))
    write_jsonl(d / "val.jsonl", rng.sample(val, len(bva)))
    copy_main(main_dir, d, ("test", "test_xsource"))
    manifest(d, {"derived_from": str(main_dir), "rule": "random subsample, same sizes as outlet_balanced",
                 "seed": args.seed + 1})

    # 2. leave-one-publisher-out
    everything = train + val + test
    for o in [x.strip() for x in args.lopo.split(",") if x.strip()]:
        held = [r for r in everything if outlet_of(r) == o]
        if not held:
            sys.exit(f"no articles from outlet {o}")
        clusters = {r["cluster_id"] for r in held}
        def keep(rows):
            return [r for r in rows if outlet_of(r) != o and r["cluster_id"] not in clusters]
        d = root / f"lopo_{o.split('.')[0]}"
        d.mkdir(parents=True, exist_ok=True)
        tr = keep(train)
        dropped_mates = sum(1 for r in train + val if outlet_of(r) != o and r["cluster_id"] in clusters)
        write_jsonl(d / "train.jsonl", tr)
        write_jsonl(d / "val.jsonl", keep(val))
        write_jsonl(d / "test.jsonl", keep(test))
        write_jsonl(d / "test_xsource.jsonl", sorted(held, key=lambda r: r["id"]))
        shutil.copyfile(main_dir / "test_xsource.jsonl", d / "test_cnn.jsonl")
        manifest(d, {"derived_from": str(main_dir), "withheld_outlet": o,
                     "dropped_cluster_mates_from_other_outlets": dropped_mates})

    # 3. target-publisher adaptation: split the withheld publisher by cluster into pool and evaluation set
    rng = random.Random(args.seed + 2)
    by_cluster = defaultdict(list)
    for r in xs:
        by_cluster[r["cluster_id"]].append(r)
    singles = {lab: sorted([c for c, m in by_cluster.items() if len(m) == 1 and m[0]["label"] == lab]) for lab in (NATIVE, NEWS)}
    for lab in singles:
        rng.shuffle(singles[lab])
    half = args.pool // 2
    pool_c = [c for pair in zip(singles[NATIVE][:half], singles[NEWS][:half]) for c in pair]  # interleaved: any prefix is balanced
    pool = [by_cluster[c][0] for c in pool_c]
    pool_ids = {r["id"] for r in pool}
    evalset = sorted([r for r in xs if r["id"] not in pool_ids], key=lambda r: r["id"])
    write_jsonl(root / "adapt_pool.jsonl", pool)
    write_jsonl(root / "adapt_eval.jsonl", evalset)
    for n in [int(x) for x in args.adapt_n.split(",")]:
        d = root / f"adapt_{n}"
        d.mkdir(parents=True, exist_ok=True)
        tr = train + pool[:n]
        random.Random(args.seed + 3).shuffle(tr)
        write_jsonl(d / "train.jsonl", tr)
        copy_main(main_dir, d, ("val", "test"))
        write_jsonl(d / "test_xsource.jsonl", evalset)
        manifest(d, {"derived_from": str(main_dir), "target_articles_added": n,
                     "pool_is_cluster_disjoint_from_eval": True})
    print(f"adaptation pool {len(pool)} (label-balanced prefixes), evaluation set {len(evalset)}")


if __name__ == "__main__":
    main()
