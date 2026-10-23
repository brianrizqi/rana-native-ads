# RANA: Retrieval-Augmented Native Advertisement Assessment

Code and released artifacts for the paper *RANA: Retrieval-Augmented Native Advertisement Assessment with Large Language Models for Explainable Detection of Promotional Framing in Indonesian and English News* (under review at IEEE Access).

RANA fine-tunes a language model to state four assessments of promotional framing (positive tone, persuasive language, brand promotion, single perspective) before its label, and shows the labeled training articles it retrieved. Every experiment in the paper uses a deduplicated, frozen partition and a publisher withheld from training.

## What this repository contains

| Path | Contents |
|---|---|
| `revision/*.py`, `revision/*.sh` | Full pipeline: partitioning and deduplication, retrieval index, fine-tuning, inference, baselines, statistics, tables |
| `revision/splits/main/ids_hashes.csv` | For every article: identifier, partition, duplicate-cluster identifier, SHA-256 of the normalized article text, language, label, outlet, section, and the four signal annotations (`positive_tone`: ya/netral/tidak; `persuasive`, `brand_promotion`, `single_perspective`: ya/tidak). Labels: `native ads`, `berita murni` (Pure News). `figshare_id`: the row `id` of the identical text in `Dataset Native Ads.xlsx` of the public Native Ads Dataset on figshare (doi:10.6084/m9.figshare.25376206, version 4), matched by content hash; given for all 12,018 Indonesian articles, empty for English ones |
| `revision/splits/main/split_stats.json` | Partition sizes and duplicate-cluster statistics |
| `revision/release/predictions/` | Per-article predictions of every reported run: label, four assessments, retrieved neighbor ids (no text) |
| `revision/release/run_configs/` | Configuration of every fine-tuning run: base model, hyperparameters, seed, split-file hashes, best checkpoint and package versions |
| `revision/report/` | Metrics, McNemar tests and the LaTeX tables reported in the paper |

## Data availability

Article texts and URLs are **not** included in this repository. The texts of all 12,018 Indonesian articles are public in `Dataset Native Ads.xlsx` of the Native Ads Dataset on figshare (doi:10.6084/m9.figshare.25376206, version 4) and can be retrieved through `figshare_id`. The English texts remain under the copyright of the originating publisher and are available, together with all URLs, from the corresponding author for non-commercial research under a data use agreement. The Indonesian portion was published as the Native Ads Dataset (Darnoto et al., *Scientific Data*, doi:10.1038/s41597-024-04341-6). With a copy of the articles, `ids_hashes.csv` lets you verify that each text matches the one we used and rebuild the exact partition. The hash is `sha256(normalize_for_hash(text))` from `revision/common.py` (Unicode NFKC, lowercase, punctuation replaced by spaces, whitespace collapsed), computed on the article text before source cues are removed.

## Reproducing the experiments

Requirements: Python 3.10+, one NVIDIA GPU with 40 GB memory for the 12B models, and the packages `unsloth`, `transformers`, `datasets`, `torch`, `sentence-transformers`, `scikit-learn`, `scipy`, `numpy`, `pandas`, `openpyxl`, `requests`.

```bash
# 1. Partition (needs the article files obtained on request)
python revision/prepare_data.py --xlsx native_ads_dataset.xlsx --json llm_dataset_12k_refined_full.json \
    --out-dir revision/splits/main

# 2. Retrieval index over the training partition only
bash revision/run_all.sh index

# 3. Fine-tune and run inference (one shared configuration for every model)
bash revision/run_all.sh finetune gemma3-12b
bash revision/run_all.sh infer gemma3-12b

# 4. Baselines, controls, statistics and tables
bash revision/run_all.sh knn
bash revision/run_all.sh encoders
bash revision/run_all.sh senada        # SENADA retrained on the same partition
bash revision/run_all.sh ablation gemma3-12b
bash revision/run_all.sh stats
python revision/make_tables.py --report-dir revision/report --out-dir revision/report/latex
```

`revision/queue_all.sh` and `revision/queue_extra.sh` run the full set of experiments in the order used for the paper and can be resumed after an interruption. Decoding is greedy, the fine-tuning seed is 3407 (RANA was also trained with seeds 42 and 2024), and the LLM judge (`revision/judge.py`) reads its API key from the `OPENROUTER_API_KEY` environment variable.

## Model weights

LoRA adapter weights for RANA (Gemma 3 12B, seed 3407) are available at https://huggingface.co/brianrizqi/rana-gemma3-12b-lora, subject to the Gemma terms of use.
