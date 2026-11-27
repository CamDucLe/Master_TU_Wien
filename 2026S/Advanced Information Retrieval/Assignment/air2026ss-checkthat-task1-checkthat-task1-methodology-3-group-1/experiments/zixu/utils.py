"""
Shared utilities for Track 3 experiments.
Used by all experiment scripts — handles data loading, embedding, scoring, and run-file I/O.
"""

import os
import csv
import json
import numpy as np
from pathlib import Path
from typing import Optional
from datasets import load_dataset
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import CrossEncoder

# ========= Config ===========================

DATASET_NAME = "sschellhammer/CT26_Task1_SourceRetrievalForScientificWebClaims"
BASELINE_MODEL = "intfloat/multilingual-e5-large"
RUNS_DIR = Path("../runs")
RUNS_DIR.mkdir(exist_ok=True)
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2" # Later change this to: "./runs/my_finetuned_reranker"

# ========= Reranking =========

def get_reranker(model_name: str = RERANKER_MODEL) -> CrossEncoder:
    """Load a SentenceTransformer CrossEncoder model."""
    print(f"Loading reranker: {model_name}")
    # We use max_length to truncate super long abstracts
    return CrossEncoder(model_name, max_length=512)

def rerank(
    reranker: CrossEncoder,
    query_texts: list[str],  # <-- Add this parameter!
    queries: list[dict],
    collection: list[dict],
    retrieval_results: dict[str, list[tuple[str, float]]],
    top_k: int = 5
) -> dict[str, list[tuple[str, float]]]:
    """
    Stage 2: Re-score the top-k retrieved documents using a CrossEncoder.
    """
    # Map qid to the text currently being tested (original, normalized, translated, etc.)
    query_map = {q["qid"]: text for q, text in zip(queries, query_texts)}
    doc_map = {d["doc_id"]: f"{d['title']}. {d['abstract']}" for d in collection}

    reranked_results = {}

    for qid, ranked_docs in retrieval_results.items():
        query_text = query_map[qid]

        # Prepare pairs: (query_text, document_text)
        pairs = []
        doc_ids = []
        for doc_id, _ in ranked_docs:
            pairs.append((query_text, doc_map[doc_id]))
            doc_ids.append(doc_id)

        # Score pairs
        scores = reranker.predict(pairs)

        # Sort by the new cross-encoder scores in descending order
        doc_score_pairs = list(zip(doc_ids, scores))
        doc_score_pairs.sort(key=lambda x: x[1], reverse=True)

        # Keep only the final top_k
        reranked_results[qid] = doc_score_pairs[:top_k]

    return reranked_results

# ========= Data loading =========

def load_data(split: str = "dev", language: str = "en"):
    """
    Load queries and collection from HuggingFace using the CT26 Task 1 schema.
    """
    from datasets import load_dataset
    import numpy as np

    print(f"  Loading queries for language: {language}...")

    # 1. Load Queries and Labels
    # For train/dev, we use the language config ('en', 'de', 'fr')
    if split in ["train", "dev"]:
        dataset_dict = load_dataset("sschellhammer/CT26_Task1_SourceRetrievalForScientificWebClaims", language)
        queries_raw = dataset_dict[split]
    else:
        # For test, the config name is specifically "test"
        dataset_dict = load_dataset("sschellhammer/CT26_Task1_SourceRetrievalForScientificWebClaims", name="test")
        queries_raw = dataset_dict[language]

    queries = []
    qrels = {}
    for row in queries_raw:
        # Mapping: 'index' -> qid, 'text' -> tweet_text
        qid = str(row["index"])
        queries.append({
            "qid": qid,
            "tweet_text": row["text"]
        })

        # If 'pubkey' exists, it is the ground truth relevant document
        if "pubkey" in row and row["pubkey"]:
            qrels[qid] = {str(row["pubkey"])}

    # 2. Load the Document Collection
    # The card indicates this is likely the "collection" or "collection_data" config
    print("  Loading document collection...")
    coll_dataset = load_dataset("sschellhammer/CT26_Task1_SourceRetrievalForScientificWebClaims", "collection")

    # Use the first available split (usually 'train')
    coll_split_name = list(coll_dataset.keys())[0]
    collection_raw = coll_dataset[coll_split_name]

    collection = []
    for row in collection_raw:
        # Mapping: 'pubkey' -> doc_id
        collection.append({
            "doc_id": str(row["pubkey"]),
            "title": row.get("title", ""),
            "abstract": row.get("abstract", "")
        })

    return queries, collection, qrels if split != "test" else None


# ========= Embedding ==================

def get_model(model_name: str = BASELINE_MODEL) -> SentenceTransformer:
    """Load (and cache) a SentenceTransformer model."""
    print(f"Loading model: {model_name}")
    return SentenceTransformer(model_name)


def embed_texts(model: SentenceTransformer, texts: list[str], batch_size: int = 64,
                prefix: str = "") -> np.ndarray:
    """
    Embed a list of texts.  Optionally prepend a prefix (e5 models use 'query: ' / 'passage: ').
    Returns float32 numpy array of shape (N, D).
    """
    if prefix:
        texts = [prefix + t for t in texts]
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return embeddings.astype(np.float32)


# ========= Retrieval ==================

def retrieve(
    query_embeddings: np.ndarray,
    doc_embeddings: np.ndarray,
    queries: list[dict],
    collection: list[dict],
    top_k: int = 10,
) -> dict[str, list[tuple[str, float]]]:
    """
    Cosine-similarity retrieval.

    Returns:
        results — dict[qid -> list of (doc_id, score) sorted descending]
    """
    # Dot product of normalized vectors = cosine similarity
    scores = query_embeddings @ doc_embeddings.T  # (Q, D)

    results = {}
    for i, query in enumerate(queries):
        top_indices = np.argsort(-scores[i])[:top_k]
        results[query["qid"]] = [
            (collection[j]["doc_id"], float(scores[i, j])) for j in top_indices
        ]
    return results


# ========= Evaluation =========

def evaluate(results: dict, qrels: dict, k_values: list[int] = [1, 5, 10]) -> dict:
    """
    Compute MRR@k and Recall@k.

    Args:
        results — dict[qid -> list of (doc_id, score)]
        qrels   — dict[qid -> set of relevant doc_ids]

    Returns:
        metrics dict, e.g. {"MRR@10": 0.45, "Recall@10": 0.72, ...}
    """
    metrics = {f"MRR@{k}": [] for k in k_values}
    metrics.update({f"Recall@{k}": [] for k in k_values})

    for qid, ranked in results.items():
        relevant = qrels.get(qid, set())
        if not relevant:
            continue

        retrieved_ids = [doc_id for doc_id, _ in ranked]

        for k in k_values:
            top_k_ids = retrieved_ids[:k]

            # MRR
            rr = 0.0
            for rank, doc_id in enumerate(top_k_ids, start=1):
                if doc_id in relevant:
                    rr = 1.0 / rank
                    break
            metrics[f"MRR@{k}"].append(rr)

            # Recall
            hits = len(set(top_k_ids) & relevant)
            metrics[f"Recall@{k}"].append(hits / len(relevant))

    return {key: round(float(np.mean(vals)), 4) for key, vals in metrics.items()}


def print_metrics(metrics: dict, label: str = ""):
    header = f"  [{label}]" if label else ""
    print(f"\n{'='*45}{header}")
    for key, val in metrics.items():
        print(f"  {key:<15} {val:.4f}")
    print("=" * 45)


# ========= Run file I/O =========

def save_run(results: dict, run_name: str):
    """
    Save results in TREC run format:
        qid Q0 doc_id rank score run_name

    File is saved to runs/<run_name>.txt
    """
    path = RUNS_DIR / f"{run_name}.txt"
    with open(path, "w") as f:
        for qid, ranked in results.items():
            for rank, (doc_id, score) in enumerate(ranked, start=1):
                f.write(f"{qid} Q0 {doc_id} {rank} {score:.6f} {run_name}\n")
    print(f"Run saved → {path}")
    return path


def load_run(run_name: str) -> dict:
    """Load a TREC run file back into a results dict."""
    path = RUNS_DIR / f"{run_name}.txt"
    results = {}
    with open(path) as f:
        for line in f:
            parts = line.strip().split()
            qid, _, doc_id, rank, score, _ = parts
            results.setdefault(qid, []).append((doc_id, float(score)))
    return results


def save_tsv_submission(results: dict, lang: str):
    """
    Save results to the official CheckThat! TSV format.
    The file MUST be named predictions_{lang}.tsv
    Columns: "index", "preds"
    where preds is a string array: "['pred1', 'pred2', 'pred3', 'pred4', 'pred5']"
    """
    # The guidelines strictly require the naming convention: predictions_{lang}.tsv
    path = RUNS_DIR / f"predictions_{lang}.tsv"

    with open(path, "w", encoding="utf-8", newline="") as f:
        # Use tab delimiter for TSV
        writer = csv.writer(f, delimiter="\t")

        # Write the exact headers requested
        writer.writerow(["index", "preds"])

        for qid, ranked_docs in results.items():
            # Extract just the doc_ids (pubkeys) for the top 5 results
            top5_preds = [doc_id for doc_id, score in ranked_docs[:5]]

            # Convert the python list directly to a string to get the required ['A', 'B'] format
            preds_str = str(top5_preds)

            writer.writerow([qid, preds_str])

    print(f"Official TSV submission saved → {path}")
    return path
