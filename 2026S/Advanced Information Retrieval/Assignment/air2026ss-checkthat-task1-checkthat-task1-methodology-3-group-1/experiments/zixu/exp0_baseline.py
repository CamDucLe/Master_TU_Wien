"""
Experiment 0 — Competitive Baseline
=====================================
Reproduces the reference baseline from task1/CT26_Task1_baseline.ipynb.

Pipeline:
  tweet text  ──[multilingual-e5-large]──> embedding
  title + abstract ──[multilingual-e5-large]──> embedding
  rank by cosine similarity

This is the fixed comparison point for all Track 3 experiments.

Usage:
    python exp0_baseline.py
    python exp0_baseline.py --split dev --lang en
    python exp0_baseline.py --split dev --lang de
    python exp0_baseline.py --split dev --lang fr
"""

import argparse
import numpy as np
from utils import (
    load_data, get_model, embed_texts, retrieve,
    save_tsv_submission, evaluate, print_metrics, save_run, BASELINE_MODEL
)


def build_doc_texts(collection: list[dict]) -> list[str]:
    """Concatenate title and abstract as the document representation."""
    return [f"{doc['title']}. {doc['abstract']}" for doc in collection]


def run_baseline(split: str = "dev", lang: str = "en"):
    print(f"\n{'='*50}")
    print(f"  EXP 0 — Competitive Baseline | split={split} lang={lang}")
    print(f"{'='*50}")

    # 1. Load data
    queries, collection, qrels = load_data(split=split, language=lang)
    print(f"Loaded {len(queries)} queries, {len(collection)} documents")

    # 2. Load Stage 1 model
    model = get_model(BASELINE_MODEL)

    # 3. Embed
    query_texts = [q["tweet_text"] for q in queries]
    doc_texts = build_doc_texts(collection)

    print("Embedding queries...")
    query_embs = embed_texts(model, query_texts, prefix="query: ")

    print("Embedding documents...")
    doc_embs = embed_texts(model, doc_texts, prefix="passage: ")

    # 4. Dense retrieval — top 100 candidates
    print("Retrieving top 100 candidates...")
    final_results = retrieve(query_embs, doc_embs, queries, collection, top_k=100)

    # 5. Evaluate at k=1 and k=5 (MRR@5 is the competition metric)
    metrics = None
    if qrels:
        metrics = evaluate(final_results, qrels, k_values=[1, 5])
        print_metrics(metrics, label=f"Baseline (Reranked) | {lang} {split}")

    # 6. Save
    run_name = f"exp0_baseline_{lang}_{split}"
    save_run(final_results, run_name)

    # Save the TSV format ONLY if evaluating on the test split (for official submission)
    # Or remove the if-statement if you just want to generate it every time to check the formatting
    if split == "test":
        save_tsv_submission(final_results, lang)

    return final_results, metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["train", "dev", "test"])
    parser.add_argument("--lang", default="en", choices=["en", "de", "fr"])
    args = parser.parse_args()

    run_baseline(split=args.split, lang=args.lang)
