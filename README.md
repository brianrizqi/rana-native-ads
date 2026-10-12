# RANA: Retrieval-Augmented Native Advertisement Assessment

Code and released artifacts for the paper *RANA: Retrieval-Augmented Native Advertisement Assessment with Large Language Models for Explainable Detection of Promotional Framing in Indonesian and English News* (under review at IEEE Access).

RANA fine-tunes a language model to state four assessments of promotional framing (positive tone, persuasive language, brand promotion, single perspective) before its label, and shows the labeled training articles it retrieved. Every experiment in the paper uses a deduplicated, frozen partition and a publisher withheld from training.

## What this repository contains

| Path | Contents |
|---|---|
| `revision/*.py`, `revision/*.sh` | Full pipeline: partitioning and deduplication, retrieval index, fine-tuning, inference, baselines, statistics, tables |
| `revision/splits/main/ids_hashes.csv` | For every article: identifier, partition, duplicate-cluster identifier, SHA-256 of the cleaned text, language, label, outlet, section |
| `revision/splits/main/split_stats.json` | Partition sizes and duplicate-cluster statistics |
| `revision/release/predictions/` | Per-article predictions of every reported run: label, four assessments, retrieved neighbor ids (no text) |
| `revision/report/` | Metrics, McNemar tests and the LaTeX tables reported in the paper |

## Data availability

Article texts and URLs are **not** included, because the texts remain under the copyright of the originating publishers. They are available from the corresponding author for non-commercial research under a data use agreement. The Indonesian portion was published as the Native Ads Dataset (Darnoto et al., *Scientific Data*, doi:10.1038/s41597-024-04341-6). With a copy of the articles, `ids_hashes.csv` lets you verify that each text matches the one we used and rebuild the exact partition.

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
bash revision/run_all.sh ablation gemma3-12b
bash revision/run_all.sh stats
python revision/make_tables.py --report-dir revision/report --out-dir revision/report/latex
```

`revision/queue_all.sh` and `revision/queue_extra.sh` run the full set of experiments in the order used for the paper and can be resumed after an interruption. Decoding is greedy, the fine-tuning seed is 3407 (RANA was also trained with seeds 42 and 2024), and the LLM judge (`revision/judge.py`) reads its API key from the `OPENROUTER_API_KEY` environment variable.

## Model weights

LoRA adapter weights for RANA will be released on Hugging Face upon acceptance, subject to the license of the base model.
