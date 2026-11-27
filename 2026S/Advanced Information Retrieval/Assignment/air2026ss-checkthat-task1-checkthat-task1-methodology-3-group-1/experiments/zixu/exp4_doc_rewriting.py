"""
Experiment 4 — Document-Side Rewriting
=======================================
Track 3 contribution: rewrite each abstract as a tweet-style summary,
then embed the rewritten version alongside the original tweet query.

Hypothesis:
  The stylistic gap between tweets and abstracts is bidirectional.
  Instead of lifting the tweet up to abstract register (Exp 1),
  we pull the abstract DOWN to tweet register.
  This may improve cosine similarity for informal or ambiguous queries.

Two sub-strategies tested:
  A) Rewrite abstract only  (query side unchanged, default)
  B) Rewrite both query (normalize) + document — requires combining with Exp 1

This experiment focuses on Strategy A.

Usage:
    python exp4_doc_rewriting.py
    python exp4_doc_rewriting.py --split dev --lang en --provider ollama
"""

import argparse
import json
import time
from pathlib import Path
from utils import (
    load_data, get_model, embed_texts, retrieve,
    save_tsv_submission, evaluate, print_metrics, save_run, BASELINE_MODEL
)

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

REWRITE_PROMPT = """\
You are summarizing a scientific paper for a general audience on social media.

Rewrite the title and abstract below as a single tweet-length sentence (max 280 characters).

Rules:
- Use plain, accessible language
- Keep the key finding, population, and outcome
- No hashtags, no emojis, no URLs
- Output ONLY the rewritten sentence, nothing else

Title: {title}
Abstract: {abstract}

Tweet-style summary:"""


def rewrite_doc(title: str, abstract: str, provider: str = "ollama",
                ollama_model: str = "llama3") -> str:
    prompt = REWRITE_PROMPT.format(title=title, abstract=abstract[:800])

    if provider == "ollama":
        import requests
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["response"].strip()




def rewrite_collection(collection: list[dict], provider: str,
                       cache: dict, ollama_model: str = "llama3") -> list[str]:
    rewritten = []
    new_entries = 0

    for i, doc in enumerate(collection):
        doc_id = doc["doc_id"]

        if doc_id in cache:
            rewritten.append(cache[doc_id])
        else:
            try:
                result = rewrite_doc(doc["title"], doc["abstract"],
                                     provider=provider, ollama_model=ollama_model)
                cache[doc_id] = result
                rewritten.append(result)
                new_entries += 1
                time.sleep(0.2)
            except Exception as e:
                print(f"  Warning: rewrite failed for {doc_id}: {e}")
                fallback = f"{doc['title']}. {doc['abstract']}"
                rewritten.append(fallback)

        if (i + 1) % 100 == 0:
            print(f"  Rewritten {i+1}/{len(collection)} docs "
                  f"(new this run: {new_entries})")

    print(f"  Done. New rewrites: {new_entries}/{len(collection)}")
    return rewritten


def run_experiment(split: str = "dev", lang: str = "en",
                   provider: str = "ollama", ollama_model: str = "llama3"):
    print(f"\n{'='*50}")
    print(f"  EXP 4 — Doc Rewriting | split={split} lang={lang} provider={provider}")
    print(f"{'='*50}")

    # 1. Load
    queries, collection, qrels = load_data(split=split, language=lang)
    print(f"Loaded {len(queries)} queries, {len(collection)} documents")

    # 2. Rewrite collection (with caching — collection is shared across languages)
    cp = CACHE_DIR / f"exp4_doc_rewrites_{split}.json"
    cache = json.loads(cp.read_text()) if cp.exists() else {}

    print(f"\nRewriting collection (cache has {len(cache)} entries)...")
    rewritten_docs = rewrite_collection(collection, provider, cache, ollama_model)
    cp.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    # 3. Load model
    model = get_model(BASELINE_MODEL)

    # 4. Embed — query side UNCHANGED, document side uses rewritten text
    query_texts = [q["tweet_text"] for q in queries]
    print("Embedding queries (original)...")
    query_embs = embed_texts(model, query_texts, prefix="query: ")

    print("Embedding rewritten documents...")
    doc_embs = embed_texts(model, rewritten_docs, prefix="passage: ")

    # 5. Retrieve top 100
    print("Retrieving top 100 candidates...")
    final_results = retrieve(query_embs, doc_embs, queries, collection, top_k=100)

    # 6. Evaluate
    metrics = None
    if qrels:
        metrics = evaluate(final_results, qrels, k_values=[1, 5])
        print_metrics(metrics, label=f"Doc Rewriting | {lang} {split}")

    # 7. Save
    run_name = f"exp4_doc_rewriting_{lang}_{split}"
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
    parser.add_argument("--provider", default="ollama", choices=["ollama"])
    parser.add_argument("--ollama-model", default="llama3")
    args = parser.parse_args()

    run_experiment(split=args.split, lang=args.lang,
                   provider=args.provider, ollama_model=args.ollama_model)
