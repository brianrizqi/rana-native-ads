#!/usr/bin/env bash
# Every table of the second revision, from whatever results exist (missing ones are skipped). CPU, minutes.
#   bash revision/stats_round2.sh
cd "$(dirname "$0")/.."
R=revision/results
OUT=revision/report/round2
mkdir -p "$OUT"
FMT=reasoning_first
have() { compgen -G "$1" > /dev/null; }

# 1. Seeds (R2-6, R1 minor 3): every configuration with its seeds; RANA against every competitor, per test set
for t in test__rag_k5 test__norag test_xsource__rag_k5 test_xsource__norag; do
  base=${t%%__*}  # encoders, SENADA and TF-IDF have one prediction file per test set
  args=(--group "RANA=$R/gemma3-12b__$FMT{,_s42,_s2024}/$t.jsonl")
  for m in deepseek-r1-llama-8b qwen3.5-9b gemma2-9b qwen3-8b; do
    args+=(--group "$m=$R/${m}__$FMT{,_s42,_s2024}/$t.jsonl" --compare "RANA:$m")
  done
  for e in indobert-base-p1 xlm-roberta-base bert-base-multilingual-cased; do
    args+=(--group "$e=$R/encoders__$e{,_s3407,_s2024}/$base.jsonl" --compare "RANA:$e")
  done
  args+=(--group "senada=$R/encoders__senada{,_s42,_s2024}/$base.jsonl" --compare "RANA:senada")
  args+=(--group "tfidf=$R/tfidf__masked/$base.jsonl" --compare "RANA:tfidf")
  python revision/seed_stats.py --out-dir "$OUT/seeds/$t" "${args[@]}"
done

# 2. Topic control on the withheld publisher (R1 minor 1)
python revision/topic_control.py --ids revision/splits/main/ids_hashes.csv --out "$OUT/topic_control.csv" \
  --runs "$R/*/test_xsource*.jsonl"

# 3. Source-independent training, leave-one-publisher-out, target-publisher adaptation (R2-1)
runs=()
for p in "$R/*__outlet_balanced/*.jsonl" "$R/*__size_matched/*.jsonl" "$R/*__lopo_*/*.jsonl" "$R/*__adapt_200/*.jsonl" \
         "$R/gemma3-12b__$FMT*/adapt_eval__*.jsonl" "$R/tfidf__masked__*/*.jsonl" "$R/encoders__*__*/*.jsonl" \
         "$R/knn/adapt_*/*.jsonl"; do
  have "$p" && runs+=("$p")
done
[ ${#runs[@]} -gt 0 ] && python revision/stats.py --runs "${runs[@]}" --out-dir "$OUT/xpublisher"
# adaptation: every N against N = 0 on the same evaluation articles (seed_stats intersects article ids)
if have "$R/gemma3-12b__$FMT/adapt_eval__rag_k5_index+400.jsonl"; then
  python revision/seed_stats.py --out-dir "$OUT/adapt" --restrict revision/splits/adapt_eval.jsonl \
    --group "RANA index+0=$R/gemma3-12b__$FMT{,_s42,_s2024}/test_xsource__rag_k5.jsonl" \
    --group "RANA index+400=$R/gemma3-12b__$FMT{,_s42,_s2024}/adapt_eval__rag_k5_index+400.jsonl" \
    --group "RANA index+100=$R/gemma3-12b__$FMT/adapt_eval__rag_k5_index+100.jsonl" \
    --group "TF-IDF +0=$R/tfidf__masked__adapt_0/adapt_eval.jsonl" \
    --group "TF-IDF +400=$R/tfidf__masked__adapt_400/test_xsource.jsonl" \
    --compare "RANA index+400:RANA index+0" --compare "RANA index+100:RANA index+0" --compare "TF-IDF +400:TF-IDF +0" \
    --compare "RANA index+400:TF-IDF +400"
fi

# 4. Faithfulness (R2-4)
have "$R/faithfulness/occlusion_*.jsonl" && python revision/faithfulness_occlusion.py \
  --report "$R/faithfulness/occlusion_test.jsonl" --out-dir "$OUT/occlusion_test"
have "$R/faithfulness/occlusion_test_xsource.jsonl" && python revision/faithfulness_occlusion.py \
  --report "$R/faithfulness/occlusion_test_xsource.jsonl" --out-dir "$OUT/occlusion_test_xsource"
for c in norag rag_k5; do
  have "$R/gemma3-12b__$FMT/cf_*__$c.jsonl" && python revision/counterfactual_edits.py analyze \
    --out-dir revision/splits/counterfactual --base "$R/gemma3-12b__$FMT/test__$c.jsonl" \
    --edited "$R/gemma3-12b__$FMT/cf_*__$c.jsonl" --report "$OUT/counterfactual_$c"
done

# 5. New English publishers (R2-2)
runs=()
for p in "$R/*/en_ext__*.jsonl" "$R/*/test_en_ext.jsonl" "$R/encoders__*__en_ext/*.jsonl"; do have "$p" && runs+=("$p"); done
[ ${#runs[@]} -gt 0 ] && python revision/stats.py --runs "${runs[@]}" --out-dir "$OUT/en_ext"

# 6. Reproducibility (R2-8)
python revision/repro_check.py --pred-dir revision/release/predictions --report-dir revision/report --tables revision/report/latex \
  > "$OUT/repro_check.txt" 2>&1
have "$R/repro_hf/test__rag_k5.jsonl" && python revision/repro_check.py --pred-dir x --report-dir x \
  --compare "$R/repro_hf/test__rag_k5.jsonl" "$R/gemma3-12b__$FMT/test__rag_k5.jsonl" >> "$OUT/repro_check.txt"
echo "✅ round-2 reports in $OUT"
