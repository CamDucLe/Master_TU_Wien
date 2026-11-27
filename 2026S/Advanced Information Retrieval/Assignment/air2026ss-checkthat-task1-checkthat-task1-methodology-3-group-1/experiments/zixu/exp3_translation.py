"""
Experiment 3 — Pivot-Language Translation
==========================================
Track 3 contribution: translate non-English tweets to English before retrieval.

Hypothesis:
  multilingual-e5-large is trained across many languages, but its English
  representations may be denser and better-calibrated than German/French ones,
  especially for scientific vocabulary.
  Translating DE/FR tweets → EN before embedding may close this gap.

Two strategies tested:
  A) Translate query only  (document side unchanged)
  B) Translate query + document  — embed both in English only
     (only practical for a subset; full collection is large)

This experiment focuses on Strategy A as the default.

Usage:
    # German queries → English, then retrieve
    python exp3_translation.py --lang de

    # French queries → English, then retrieve
    python exp3_translation.py --lang fr

    # English already — runs as sanity check (should be identical to baseline)
    python exp3_translation.py --lang en
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

# =========== Translation prompts ===========

TRANSLATE_PROMPT = """\
Translate the following tweet to English.
Output ONLY the translated text, no explanation, no quotes.

Tweet ({src_lang}): {tweet}

English translation:"""

LANG_NAMES = {"de": "German", "fr": "French", "en": "English"}


# =========== Lightweight local translation (Helsinki-NLP) ===========

def translate_local(texts: list[str], src_lang: str) -> list[str]:
    """
    Use Helsinki-NLP MarianMT models for free, offline translation.

    Models used:
      DE→EN: Helsinki-NLP/opus-mt-de-en
      FR→EN: Helsinki-NLP/opus-mt-fr-en

    Uses batch_size=1 to avoid stalls on problematic inputs (long tweets,
    unusual unicode). Falls back to original text on any error.
    """
    from transformers import MarianMTModel, MarianTokenizer
    import torch

    model_name = f"Helsinki-NLP/opus-mt-{src_lang}-en"
    print(f"  Loading translation model: {model_name}")
    tokenizer = MarianTokenizer.from_pretrained(model_name)
    model = MarianMTModel.from_pretrained(model_name)
    model.eval()

    translated = []
    fallbacks = 0

    for i, text in enumerate(texts):
        try:
            # Truncate aggressively — tweets are short, long inputs cause stalls
            inputs = tokenizer(
                [text],
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=128,  # tweets fit easily in 128 tokens
            )
            with torch.no_grad():
                outputs = model.generate(
                    **inputs,
                    max_new_tokens=128,
                    num_beams=2,          # faster than default beam=4
                    early_stopping=True,
                )
            result = tokenizer.decode(outputs[0], skip_special_tokens=True)
            translated.append(result)
        except Exception as e:
            print(f"  Warning: fallback for index {i}: {e}")
            translated.append(text)
            fallbacks += 1

        if (i + 1) % 50 == 0:
            print(f"  Translated {i+1}/{len(texts)} (fallbacks so far: {fallbacks})")

    print(f"  Done. Total fallbacks: {fallbacks}/{len(texts)}")
    return translated


# =========== Batch translation with cache ===========

def translate_queries(queries: list[dict], src_lang: str, provider: str,
                      cache: dict) -> list[str]:
    """
    Translate all tweet texts from src_lang to English.
    If src_lang == 'en', returns original texts unchanged.
    """
    if src_lang == "en":
        print("  Source language is English — no translation needed.")
        return [q["tweet_text"] for q in queries]

    if provider == "local":
        # Translate all at once with MarianMT (batch-efficient)
        uncached_queries = [q for q in queries if q["qid"] not in cache]
        if uncached_queries:
            texts_to_translate = [q["tweet_text"] for q in uncached_queries]
            translations = translate_local(texts_to_translate, src_lang)
            for q, t in zip(uncached_queries, translations):
                cache[q["qid"]] = t

        return [cache[q["qid"]] for q in queries]


# =========== Main ===========

def run_experiment(split: str = "dev", lang: str = "de",
                   provider: str = "local"):
    print(f"\n{'='*50}")
    print(f"  EXP 3 — Translation {lang.upper()}→EN | split={split} provider={provider}")
    print(f"{'='*50}")

    # 1. Load
    queries, collection, qrels = load_data(split=split, language=lang)
    print(f"Loaded {len(queries)} queries, {len(collection)} documents")

    # 2. Translate (with caching)
    cp = CACHE_DIR / f"exp3_translation_{lang}_{split}.json"
    cache = json.loads(cp.read_text()) if cp.exists() else {}

    print(f"\nTranslating queries {lang}→en (cache has {len(cache)} entries)...")
    translated_texts = translate_queries(queries, lang, provider, cache)
    cp.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    # 3. Show samples
    if lang != "en":
        print("\n── Sample translations ──")
        for q, tr in zip(queries[:3], translated_texts[:3]):
            print(f"  ORIGINAL ({lang}): {q['tweet_text'][:100]}")
            print(f"  TRANSLATED (en): {tr[:100]}")
            print()

    # 4. Model
    model = get_model(BASELINE_MODEL)

    # 5. Embed — use English-translated queries; document side unchanged
    print("Embedding translated queries...")
    query_embs = embed_texts(model, translated_texts, prefix="query: ")

    doc_texts = [f"{doc['title']}. {doc['abstract']}" for doc in collection]
    print("Embedding documents...")
    doc_embs = embed_texts(model, doc_texts, prefix="passage: ")

    # 6. Retrieve top 100
    print("Retrieving top 100 candidates...")
    final_results = retrieve(query_embs, doc_embs, queries, collection, top_k=100)

    # 7. Evaluate
    if qrels:
        metrics = evaluate(final_results, qrels)
        print_metrics(metrics, label=f"Translation {lang}→en | {split}")

    # 8. Save
    run_name = f"exp3_translation_{lang}en_{split}"
    save_run(final_results, run_name)

    # Save the TSV format ONLY if evaluating on the test split (for official submission)
    # Or remove the if-statement if you just want to generate it every time to check the formatting
    if split == "test":
        save_tsv_submission(final_results, lang)

    return final_results, metrics if qrels else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["train", "dev", "test"])
    parser.add_argument("--lang", default="de", choices=["en", "de", "fr"])
    parser.add_argument("--provider", default="local", choices=["local"],
                        help="'local' uses Helsinki-NLP MarianMT (free, offline). ")
    args = parser.parse_args()

    run_experiment(split=args.split, lang=args.lang, provider=args.provider)
