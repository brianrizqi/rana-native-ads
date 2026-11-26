#!/usr/bin/env bash
# Second-revision queue (Access-2026-55039). Same rules as queue_all.sh / queue_extra.sh: one job at a time,
# never starts a job that cannot finish before DEADLINE, safe to rerun in a new reservation (finished
# adapters are skipped, fine-tunes resume from checkpoints, inference resumes from the last article).
#
#   DEADLINE="2026-12-05 18:00" nohup bash revision/queue_round2.sh >> revision/logs/queue_round2.log 2>&1 &
#   ONLY="seeds lopo" DEADLINE=... bash revision/queue_round2.sh      # run only some blocks
#
# Blocks, in priority order (estimates in hours on one A100 40 GB, from the measured first-revision runs):
#   cpu        derived partitions, TF-IDF variants, topic control, reproducibility check          < 0.5
#   index      bge-m3 indexes for the derived partitions                                          ~1
#   encseeds   IndoBERT, XLM-R, mBERT with seeds 3407 and 2024; SENADA with seeds 42 and 2024     ~4
#   repro      RANA from the public Hugging Face adapter, 300 test articles, vs released preds    ~0.5
#   occlusion  sentence occlusion on 250 test + 250 withheld-publisher articles (R2-4)            ~6
#   cf         counterfactual edits, if revision/splits/counterfactual/cf_*.jsonl exist (R2-4)    ~1.5
#   enext      new English set, if revision/splits/en_ext/test_en_ext.jsonl exists (R2-2)                ~13
#   adapt      target-publisher examples added to the index, RANA 3 seeds (R2-1)                  ~8
#   balanced   RANA trained on outlet-balanced data (R2-1)                                        ~11
#   seeds      seeds 42 and 2024 for DeepSeek-R1-8B, Qwen3.5 9B, Gemma 2 9B, Qwen3 8B (R2-6)      ~88
#   lopo       RANA withholding viva.co.id, then sindonews.com (R2-1)                             ~27
#   encderived encoders and SENADA on the derived partitions (R2-1)                               ~6
#   adapttrain RANA retrained with 200 target-publisher articles (R2-1)                           ~9
#   sizematch  size-matched control for the outlet-balanced run (R2-1)                            ~11
#   stats      every table of the second revision                                                 < 0.5
cd "$(dirname "$0")/.."
LOG=revision/logs
mkdir -p "$LOG"
: "${DEADLINE:?set DEADLINE, e.g. DEADLINE=\"2026-12-05 18:00\"}"
DEADLINE_S=$(date -d "$DEADLINE" +%s) || exit 1
BUFFER_H=${BUFFER_H:-1}
ONLY=${ONLY:-"cpu index encseeds repro occlusion cf enext adapt balanced seeds lopo encderived adapttrain sizematch stats"}
SPLIT=revision/splits/main
INDEX=revision/index/bge-m3
RANA=gemma3-12b
FMT=reasoning_first
SEED_MODELS="deepseek-r1-llama-8b qwen3.5-9b gemma2-9b qwen3-8b"
ENCODERS="indobenchmark/indobert-base-p1 xlm-roberta-base bert-base-multilingual-cased"

want() { [[ " $ONLY " == *" $1 "* ]]; }
run() {  # run <name> <estimated hours> <command...>
  local name=$1 est=$2; shift 2
  local now; now=$(date +%s)
  if (( now + (est + BUFFER_H) * 3600 > DEADLINE_S )); then
    echo "[$(date '+%F %T')] SKIP  $name (needs ~${est} h, not enough time before $DEADLINE)"; return
  fi
  echo "[$(date '+%F %T')] START $name (~${est} h)"
  if "$@" > "$LOG/$name.log" 2>&1; then echo "[$(date '+%F %T')] OK    $name"
  else echo "[$(date '+%F %T')] FAIL  $name (see $LOG/$name.log)"; fi
}
infer_pair() {  # infer_pair <adapter dir> <result dir> <test file> <name> : Non-RAG and RAG
  python revision/infer.py --model "$1" --test-file "$3" --out "$2/${4}__norag.jsonl" || return 1
  python revision/infer.py --model "$1" --test-file "$3" --out "$2/${4}__rag_k5.jsonl" --rag --k 5
}
ft_and_infer() {  # ft_and_infer <model> <tag> <seed> <split dir> <index dir> <ft h> <infer h> <tests...>
  local m=$1 tag=$2 seed=$3 split=$4 index=$5 fth=$6 inh=$7; shift 7
  local ad="revision/models/${m}__${FMT}${tag}" res="revision/results/${m}__${FMT}${tag}"
  if [ ! -f "$ad/run_config.json" ]; then
    run "ft_${m}${tag}" "$fth" python revision/finetune.py --model "$m" --split-dir "$split" --index-dir "$index" \
        --rag --format $FMT --seed "$seed" --out "$ad"
  fi
  [ -f "$ad/run_config.json" ] || return
  job() { for t in "$@"; do infer_pair "$ad" "$res" "$split/$t.jsonl" "$t" || return 1; done; }
  run "infer_${m}${tag}" "$inh" job "$@"
}

while pgrep -f "revision/(infer|finetune|encoder_baselines|senada_baseline)\.py" > /dev/null; do sleep 300; done
echo "[$(date '+%F %T')] GPU free, round-2 queue starts (deadline $DEADLINE; blocks: $ONLY)"

if want cpu; then
  python revision/make_splits_r2.py --main $SPLIT --out-root revision/splits > "$LOG/r2_splits.log" 2>&1
  for v in "masked text 3000" "masked_1500 text 1500" "raw text_raw 3000"; do
    set -- $v
    python revision/tfidf_baseline.py --split-dir $SPLIT --out-dir "revision/results/tfidf__$1" --field "$2" --max-chars "$3"
  done > "$LOG/r2_tfidf.log" 2>&1
  for d in outlet_balanced size_matched lopo_viva lopo_sindonews; do
    python revision/tfidf_baseline.py --split-dir "revision/splits/$d" --out-dir "revision/results/tfidf__masked__$d" \
      --tests test test_xsource test_cnn
  done >> "$LOG/r2_tfidf.log" 2>&1
  python revision/tfidf_baseline.py --split-dir $SPLIT --out-dir revision/results/tfidf__masked__adapt_0 \
    --tests revision/splits/adapt_eval.jsonl >> "$LOG/r2_tfidf.log" 2>&1
  for n in 50 100 200 400; do
    python revision/tfidf_baseline.py --split-dir "revision/splits/adapt_$n" --out-dir "revision/results/tfidf__masked__adapt_$n" \
      --tests test_xsource
  done >> "$LOG/r2_tfidf.log" 2>&1
  python revision/repro_check.py --pred-dir revision/release/predictions --report-dir revision/report > "$LOG/r2_repro_check.log" 2>&1
  echo "[$(date '+%F %T')] OK    cpu block"
fi

if want index; then
  for d in outlet_balanced size_matched lopo_viva lopo_sindonews adapt_100 adapt_200 adapt_400; do
    [ -f "revision/index/$d/info.json" ] || run "index_$d" 1 python revision/build_index.py --split-dir "revision/splits/$d" \
      --model BAAI/bge-m3 --out-dir "revision/index/$d"
  done
fi

if want encseeds; then
  for s in 3407 2024; do
    for e in $ENCODERS; do
      o="revision/results/encoders__${e##*/}_s$s"
      [ -f "$o/run_config.json" ] || run "enc_${e##*/}_s$s" 1 python revision/encoder_baselines.py --model "$e" \
        --split-dir $SPLIT --out-dir "$o" --seed "$s"
    done
  done
  for s in 42 2024; do
    o="revision/results/encoders__senada_s$s"
    [ -f "$o/run_config.json" ] || run "senada_s$s" 1 python revision/senada_baseline.py --split-dir $SPLIT --out-dir "$o" --seed "$s"
  done
fi

if want repro; then  # the public adapter must reproduce the released predictions
  run repro_hf 1 python revision/infer.py --model brianrizqi/rana-gemma3-12b-lora --format $FMT --rag --k 5 \
    --index-dir $INDEX --test-file $SPLIT/test.jsonl --out revision/results/repro_hf/test__rag_k5.jsonl --max-samples 300
fi

if want occlusion; then
  A="revision/models/${RANA}__$FMT"
  for t in test test_xsource; do
    run "occlusion_$t" 3 python revision/faithfulness_occlusion.py --model "$A" --test-file "$SPLIT/$t.jsonl" \
      --out "revision/results/faithfulness/occlusion_$t.jsonl" --max-samples 250
  done
fi

if want cf && ls revision/splits/counterfactual/cf_*.jsonl > /dev/null 2>&1; then
  A="revision/models/${RANA}__$FMT" R="revision/results/${RANA}__$FMT"
  cfjob() { for f in revision/splits/counterfactual/cf_*.jsonl; do infer_pair "$A" "$R" "$f" "$(basename "$f" .jsonl)" || return 1; done; }
  run cf_infer 2 cfjob
fi

if want enext && [ -f revision/splits/en_ext/test_en_ext.jsonl ]; then
  E=revision/splits/en_ext/test_en_ext.jsonl
  enjob() {
    for d in revision/models/*__${FMT}{,_s42,_s2024}; do
      [ -f "$d/run_config.json" ] && infer_pair "$d" "revision/results/$(basename "$d")" "$E" en_ext
    done
    python revision/tfidf_baseline.py --split-dir $SPLIT --out-dir revision/results/tfidf__masked --tests "$E"
    for e in $ENCODERS; do  # encoders are retrained (minutes) because their weights were not kept
      python revision/encoder_baselines.py --model "$e" --split-dir $SPLIT --out-dir "revision/results/encoders__${e##*/}__en_ext" \
        --tests "$E"
    done
    python revision/senada_baseline.py --split-dir $SPLIT --out-dir revision/results/encoders__senada__en_ext --extra-tests "$E"
  }
  run enext 14 enjob
fi

if want adapt; then  # same RANA weights, the labeled target-publisher articles only enter the retrieval index
  adjob() {
    local s=$1 n=$2 A="revision/models/${RANA}__$FMT$1" R="revision/results/${RANA}__$FMT$1"
    python revision/infer.py --model "$A" --test-file "revision/splits/adapt_$n/test_xsource.jsonl" --rag --k 5 \
      --index-dir "revision/index/adapt_$n" --out "$R/adapt_eval__rag_k5_index+$n.jsonl"
  }
  for s in "" _s42 _s2024; do run "adapt_index400$s" 2 adjob "$s" 400; done
  run adapt_index100 2 adjob "" 100
  for n in 100 400; do
    python revision/knn_baseline.py --index-dir "revision/index/adapt_$n" --split-dir "revision/splits/adapt_$n" \
      --out-dir "revision/results/knn/adapt_$n" > "$LOG/knn_adapt_$n.log" 2>&1
  done
fi

if want balanced; then
  ft_and_infer $RANA __outlet_balanced 3407 revision/splits/outlet_balanced revision/index/outlet_balanced 4 7 test test_xsource
fi

if want seeds; then
  for m in $SEED_MODELS; do
    for s in 42 2024; do
      ft_and_infer "$m" "_s$s" "$s" $SPLIT $INDEX 5 6 test test_xsource
    done
  done
fi

if want lopo; then
  for o in viva sindonews; do
    ft_and_infer $RANA "__lopo_$o" 3407 "revision/splits/lopo_$o" "revision/index/lopo_$o" 5 9 test_xsource test_cnn test
  done
fi

if want encderived; then
  for d in outlet_balanced lopo_viva lopo_sindonews adapt_200 adapt_400; do
    for e in $ENCODERS; do
      o="revision/results/encoders__${e##*/}__$d"
      [ -f "$o/run_config.json" ] || run "enc_${e##*/}__$d" 1 python revision/encoder_baselines.py --model "$e" \
        --split-dir "revision/splits/$d" --out-dir "$o" --tests test test_xsource test_cnn
    done
    o="revision/results/encoders__senada__$d"
    [ -f "$o/run_config.json" ] || run "senada__$d" 1 python revision/senada_baseline.py --split-dir "revision/splits/$d" \
      --out-dir "$o" --cache-dir "revision/cache/senada" --extra-tests test_cnn
  done
fi

if want adapttrain; then
  ft_and_infer $RANA __adapt_200 3407 revision/splits/adapt_200 revision/index/adapt_200 6 3 test_xsource
fi

if want sizematch; then
  ft_and_infer $RANA __size_matched 3407 revision/splits/size_matched revision/index/size_matched 4 7 test test_xsource
fi

if want stats; then
  bash revision/stats_round2.sh > "$LOG/stats_round2.log" 2>&1 && echo "[$(date '+%F %T')] OK    stats" \
    || echo "[$(date '+%F %T')] FAIL  stats (see $LOG/stats_round2.log)"
fi
echo "[$(date '+%F %T')] ROUND-2 QUEUE DONE"
