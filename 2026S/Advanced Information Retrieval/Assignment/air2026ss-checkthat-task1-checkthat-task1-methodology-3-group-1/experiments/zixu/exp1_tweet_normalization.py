"""
Experiment 1 — Tweet Normalization
===============================================================================
Track 3 contribution: transform tweet text into formal scientific prose
before retrieval, keeping the model and documents fixed.

Hypothesis:
  Tweets use informal language, hashtags, emojis, and opinions.
  Scientific abstracts use formal language.
  Normalizing the tweet to match the register of the abstract
  should reduce the lexical gap and improve retrieval.

Transformation:
  tweet ──[LLM prompt]──> formal scientific claim ──[e5-large]──> embedding

The document side is UNCHANGED from the baseline.

Usage:
    python exp1_tweet_normalization.py
    python exp1_tweet_normalization.py --split dev --lang en --provider ollama
    python exp1_tweet_normalization.py --split dev --lang de
"""

import argparse
import json
import time
import re
import os
from pathlib import Path
from utils import (
    load_data, get_model, embed_texts, retrieve,
    save_tsv_submission, evaluate, print_metrics, save_run, BASELINE_MODEL
)

# =========== Cache ============
# Normalizing tweets is slow — cache results to disk so re-runs are free.
CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)


def cache_path(experiment: str, lang: str, split: str) -> Path:
    return CACHE_DIR / f"{experiment}_{lang}_{split}.json"


def load_cache(path: Path) -> dict:
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict, path: Path):
    with open(path, "w") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


# =========== Normalization prompts =============

NORMALIZATION_PROMPT = """\
You are a scientific writing assistant.

Your task: rewrite the tweet below as a single, formal scientific claim.

Rules:
- Remove all hashtags, emojis, URLs, @mentions, opinions, and rhetorical language
- Use formal academic register
- Keep all factual content (numbers, percentages, study populations, outcomes)
- Output ONLY the rewritten claim, nothing else — no explanation, no quotes

Tweet: {tweet}

Rewritten claim:"""


NORMALIZATION_PROMPT_DE = """\
Du bist ein wissenschaftlicher Schreibassistent.

Deine Aufgabe: Schreibe den folgenden Tweet als einen einzigen, formellen wissenschaftlichen Satz um.

Regeln:
- Entferne alle Hashtags, Emojis, URLs, @Erwähnungen, Meinungen und rhetorische Sprache
- Verwende einen formellen akademischen Stil
- Behalte alle sachlichen Inhalte (Zahlen, Prozentsätze, Studienpopulationen, Ergebnisse)
- Gib NUR den umgeschriebenen Satz aus — keine Erklärung, keine Anführungszeichen

Tweet: {tweet}

Umgeschriebener Satz:"""


NORMALIZATION_PROMPT_FR = """\
Vous êtes un assistant en rédaction scientifique.

Votre tâche : réécrivez le tweet ci-dessous en une seule affirmation scientifique formelle.

Règles :
- Supprimez tous les hashtags, emojis, URLs, @mentions, opinions et langage rhétorique
- Utilisez un registre académique formel
- Conservez tout le contenu factuel (chiffres, pourcentages, populations d'étude, résultats)
- Sortez UNIQUEMENT l'affirmation réécrite — pas d'explication, pas de guillemets

Tweet : {tweet}

Affirmation réécrite :"""


PROMPTS_BY_LANG = {"en": NORMALIZATION_PROMPT, "de": NORMALIZATION_PROMPT_DE, "fr": NORMALIZATION_PROMPT_FR}


# =========== LLM backends ===========

def normalize_with_ollama(tweet: str, lang: str = "en", model: str = "gemma2:2b") -> str:
    """Call a local Ollama model (free, no API key needed)."""
    import requests
    prompt = PROMPTS_BY_LANG[lang].format(tweet=tweet)
    response = requests.post(
        "http://localhost:11434/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


def normalize_tweet(tweet: str, lang: str = "en", provider: str = "ollama",
                    ollama_model: str = "llama3") -> str:
    """Dispatch to the selected LLM backend."""
    if provider == "ollama":
        return normalize_with_ollama(tweet, lang, ollama_model)
    else:
        raise ValueError(f"Unknown provider: {provider}. Choose 'ollama'.")


# =========== Batch normalization ===========

def normalize_queries(queries: list[dict], lang: str, provider: str,
                      cache: dict, ollama_model: str = "llama3") -> list[str]:
    """
    Normalize all tweet texts, using cache to avoid redundant API calls.
    Returns list of normalized strings in same order as queries.
    """
    normalized = []
    new_entries = 0

    for i, q in enumerate(queries):
        qid = q["qid"]
        tweet = q["tweet_text"]

        if qid in cache:
            normalized.append(cache[qid])
        else:
            print(f"  Normalizing [{i+1}/{len(queries)}] qid={qid} ...")
            try:
                result = normalize_tweet(tweet, lang=lang, provider=provider,
                                         ollama_model=ollama_model)
                cache[qid] = result
                normalized.append(result)
                new_entries += 1
                time.sleep(0.3)  # gentle rate limiting
            except Exception as e:
                print(f"  Warning: normalization failed for {qid}: {e}")
                print(f"  Falling back to original tweet.")
                normalized.append(tweet)  # fallback

    if new_entries > 0:
        print(f"  Normalized {new_entries} new tweets.")

    return normalized


# =========== Main ===========

def build_doc_texts(collection: list[dict]) -> list[str]:
    return [f"{doc['title']}. {doc['abstract']}" for doc in collection]


def run_experiment(split: str = "dev", lang: str = "en",
                   provider: str = "ollama", ollama_model: str = "llama3"):
    print(f"\n{'='*50}")
    print(f"  EXP 1 — Tweet Normalization | split={split} lang={lang} provider={provider}")
    print(f"{'='*50}")

    # 1. Load
    queries, collection, qrels = load_data(split=split, language=lang)
    print(f"Loaded {len(queries)} queries, {len(collection)} documents")

    # 2. Normalize tweets (with caching)
    cp = cache_path("exp1_normalization", lang, split)
    cache = load_cache(cp)
    print(f"\nNormalizing tweets (cache has {len(cache)} entries)...")
    normalized_texts = normalize_queries(queries, lang, provider, cache, ollama_model)
    save_cache(cache, cp)

    # 3. Show samples
    print("\n── Sample normalizations ──")
    for q, norm in zip(queries[:3], normalized_texts[:3]):
        print(f"  TWEET : {q['tweet_text'][:120]}")
        print(f"  NORM  : {norm[:120]}")
        print()

    # 4. Load model
    model = get_model(BASELINE_MODEL)

    # 5. Embed normalized queries; documents unchanged
    print("Embedding normalized queries...")
    query_embs = embed_texts(model, normalized_texts, prefix="query: ")

    doc_texts = build_doc_texts(collection)
    print("Embedding documents...")
    doc_embs = embed_texts(model, doc_texts, prefix="passage: ")

    # 6. Retrieve top 100
    print("Retrieving top 100 candidates...")
    final_results = retrieve(query_embs, doc_embs, queries, collection, top_k=100)

    # 7. Evaluate
    metrics = None
    if qrels:
        metrics = evaluate(final_results, qrels, k_values=[1, 5])
        print_metrics(metrics, label=f"Normalization | {lang} {split}")

    # 8. Save
    run_name = f"exp1_normalization_{lang}_{split}"
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
    parser.add_argument("--provider", default="ollama", choices=["ollama"],
                        help="LLM backend to use for normalization")
    parser.add_argument("--ollama-model", default="llama3",
                        help="Ollama model name (only used if provider=ollama)")
    args = parser.parse_args()

    run_experiment(split=args.split, lang=args.lang,
                   provider=args.provider, ollama_model=args.ollama_model)
