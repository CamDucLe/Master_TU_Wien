# CLEF CheckThat! 2026 — Task 1: Source Retrieval for Scientific Web Claims
## Team: TUWien-Track3 — Methodology 3, Group 1

This repository contains our system for **CLEF CheckThat! 2026 Task 1**, working on
**Track 3 — Translation & Rewriting**. Given a tweet (in EN/DE/FR) containing a scientific
claim, we retrieve the corresponding scientific paper from a shared 10k-paper corpus.

---

## System Overview

Our pipeline transforms the **query side** before retrieval, keeping the retrieval model
(`intfloat/multilingual-e5-large`) fixed:
- **Cleaning** (regex): strips URLs, @-mentions, hashtag symbols, "26/n Fact" numbering,
  emoji/special chars. Ablation showed emoji removal is the dominant component.
- **Translation** (FR/DE only): Gemma3-1B (via Ollama) outperforms specialized
  Helsinki-NLP/opus-mt models on this domain (technical/biomedical).
- **Retrieval**: `multilingual-e5-large`, cosine similarity over normalized embeddings.
- **Reranking**: cross-encoder reranker on top-K candidates (see `experiments/`).

---

## Results (dev MRR@5)

| Lang | Baseline | + Cleaning | + Gemma3 trans | + Reranker (final) |
|------|----------|------------|----------------|--------------------|
| EN   | 0.499    | **0.503**  | 0.502          | TBD                |
| FR   | 0.458    | 0.462      | **0.497**      | 0.528              |
| DE   | 0.376    | 0.380      | **0.397**      | 0.443              |

---

## Repository Structure
---

## How to Reproduce

### 1. Environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For Mac M-series: PyTorch will use MPS automatically. For NVIDIA: CUDA.

### 2. Hugging Face Authentication

Each team member must request access individually on the
[dataset page](https://huggingface.co/datasets/sschellhammer/CT26_Task1_SourceRetrievalForScientificWebClaims).
Then:

```bash
hf auth login
```

### 3. Local LLM (optional, for transformation experiments)

```bash
brew install ollama
brew services start ollama
ollama pull gemma3:1b
```

### 4. Run experiments

Each notebook in `experiments/ekin/` is self-contained. Execute cells top-to-bottom.
First-time corpus embedding (~1h47m on M3) is cached in `experiments/ekin/cache/`.

- `exp1_clean.ipynb` — rule-based cleaning (FR)
- `exp2_pivot.ipynb` — pivot translation FR→EN (opus-mt)
- `exp3_claim.ipynb` — LLM claim extraction (Qwen2.5-1.5B) — **negative result**
- `exp4_en.ipynb`, `exp5_de.ipynb` — cleaning on EN, DE
- `exp7_ablation.ipynb` — cleaning component ablation
- `exp9_concat.ipynb`, `exp9b_concat_de.ipynb` — concat strategy
- `exp11_gemma3.ipynb` — Gemma3 translation comparison
- `exp12_test_gemma3.ipynb` — final test set runs

### 5. Evaluate on dev

```bash
python task1/scorer.py --run <run_file> --qrels <qrels_file>
```

---

## Key Findings

1. **Rule-based cleaning gives a consistent +0.004 MRR@5 across all 3 languages** — small
   but reproducible signal. Ablation: emoji/special character removal is the dominant
   contributor (+0.0043 standalone).
2. **Translation quality matters more than the act of translating.**
   `multilingual-e5-large` is already cross-lingual, so a noisy translator (opus-mt)
   benefits from concatenating the original. A high-quality translator (Gemma3-1B)
   makes the original redundant — replacement beats concatenation.
3. **Negative result documented**: small-LLM claim extraction (Qwen2.5-1.5B) hurts
   performance (-0.018 on FR dev) due to information loss and hallucination on
   technical/medical content.

---

## Team

See `team.toml` for member details. Track 3 — Methodology 3, Group 1.

