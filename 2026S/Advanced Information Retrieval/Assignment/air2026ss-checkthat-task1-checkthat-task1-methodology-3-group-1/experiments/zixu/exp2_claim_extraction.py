"""
Experiment 2 — Core Claim Extraction
====================================================
Track 3 contribution: strip each tweet down to its bare factual claim,
removing everything that is noise for retrieval.

Hypothesis:
  Tweets often contain opinions, hedges, calls-to-action, emojis, and social
  context that are irrelevant to the underlying scientific claim.
  Extracting *only* the core claim reduces noise and focuses retrieval
  on the scientifically meaningful content.

Difference from Exp 1 (Normalization):
  Normalization rewrites the tweet in a formal style.
  Claim extraction is more aggressive — it REMOVES content rather than
  rewriting it, producing a shorter, compressed claim.
  These are separate hypotheses worth testing independently.

Usage:
    python exp2_claim_extraction.py
    python exp2_claim_extraction.py --split dev --lang en
    python exp2_claim_extraction.py --split dev --lang de
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

# =========== Prompts ===========

CLAIM_PROMPT = """\
Extract the core scientific claim from this tweet. Output a single sentence.

Rules:
- Include: the main finding or fact (effect, mechanism, statistic, population, outcome)
- Exclude: opinions, hashtags, emojis, @mentions, URLs, calls-to-action, rhetorical questions, source names
- If there are multiple claims, output only the most specific and central one
- Output ONLY the claim, nothing else

Tweet: {tweet}

Core claim:"""


CLAIM_PROMPT_DE = """\
Extrahiere die zentrale wissenschaftliche Aussage aus diesem Tweet. Gib einen einzigen Satz aus.

Regeln:
- Einschließen: der Hauptbefund oder die Tatsache (Effekt, Mechanismus, Statistik, Population, Ergebnis)
- Ausschließen: Meinungen, Hashtags, Emojis, @Erwähnungen, URLs, Handlungsaufforderungen, rhetorische Fragen, Quellennamen
- Falls mehrere Aussagen vorhanden sind, gib nur die spezifischste und zentralste aus
- Gib NUR die Aussage aus, nichts anderes

Tweet: {tweet}

Zentrale Aussage:"""


CLAIM_PROMPT_FR = """\
Extrayez l'affirmation scientifique centrale de ce tweet. Produisez une seule phrase.

Règles :
- Inclure : la conclusion ou le fait principal (effet, mécanisme, statistique, population, résultat)
- Exclure : opinions, hashtags, emojis, @mentions, URLs, appels à l'action, questions rhétoriques, noms de sources
- S'il y a plusieurs affirmations, n'en produire qu'une seule — la plus spécifique et centrale
- Produire UNIQUEMENT l'affirmation, rien d'autre

Tweet : {tweet}

Affirmation centrale :"""


PROMPTS_BY_LANG = {"en": CLAIM_PROMPT, "de": CLAIM_PROMPT_DE, "fr": CLAIM_PROMPT_FR}


# =========== LLM call ===========

def extract_claim(tweet: str, lang: str = "en", provider: str = "ollama",
                  ollama_model: str = "llama3") -> str:
    prompt = PROMPTS_BY_LANG[lang].format(tweet=tweet)

    if provider == "ollama":
        import requests
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": ollama_model, "prompt": prompt, "stream": False},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    else:
        raise ValueError(f"Unknown provider: {provider}")


# =========== Batch extraction ===========

def extract_claims_batch(queries: list[dict], lang: str, provider: str,
                         cache: dict, ollama_model: str = "llama3") -> list[str]:
    claims = []
    new_entries = 0

    for i, q in enumerate(queries):
        qid = q["qid"]
        tweet = q["tweet_text"]

        if qid in cache:
            claims.append(cache[qid])
        else:
            print(f"  Extracting [{i+1}/{len(queries)}] qid={qid} ...")
            try:
                result = extract_claim(tweet, lang=lang, provider=provider,
                                       ollama_model=ollama_model)
                cache[qid] = result
                claims.append(result)
                new_entries += 1
                time.sleep(0.3)
            except Exception as e:
                print(f"  Warning: extraction failed for {qid}: {e}")
                claims.append(tweet)

    if new_entries > 0:
        print(f"  Extracted {new_entries} new claims.")

    return claims


# =========== Analysis helpers ===========

def compression_stats(originals: list[str], extracted: list[str]):
    """Print how much shorter the extracted claims are on average."""
    orig_lens = [len(t.split()) for t in originals]
    extr_lens = [len(t.split()) for t in extracted]
    avg_orig = sum(orig_lens) / len(orig_lens)
    avg_extr = sum(extr_lens) / len(extr_lens)
    ratio = avg_extr / avg_orig
    print(f"\n  Avg tweet length:   {avg_orig:.1f} words")
    print(f"  Avg claim length:   {avg_extr:.1f} words")
    print(f"  Compression ratio:  {ratio:.2f}  ({(1-ratio)*100:.0f}% shorter)")


# =========== Main ===========

def run_experiment(split: str = "dev", lang: str = "en",
                   provider: str = "ollama", ollama_model: str = "llama3"):
    print(f"\n{'='*50}")
    print(f"  EXP 2 — Claim Extraction | split={split} lang={lang} provider={provider}")
    print(f"{'='*50}")

    # 1. Load
    queries, collection, qrels = load_data(split=split, language=lang)
    print(f"Loaded {len(queries)} queries, {len(collection)} documents")

    # 2. Extract claims (with caching)
    cp = CACHE_DIR / f"exp2_claims_{lang}_{split}.json"
    cache = json.loads(cp.read_text()) if cp.exists() else {}

    print(f"\nExtracting claims (cache has {len(cache)} entries)...")
    claim_texts = extract_claims_batch(queries, lang, provider, cache, ollama_model)
    cp.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

    # 3. Stats + examples
    original_tweets = [q["tweet_text"] for q in queries]
    compression_stats(original_tweets, claim_texts)

    print("\n── Sample extractions ──")
    for q, claim in zip(queries[:3], claim_texts[:3]):
        print(f"  TWEET : {q['tweet_text'][:120]}")
        print(f"  CLAIM : {claim[:120]}")
        print()

    # 4. Load model
    model = get_model(BASELINE_MODEL)

    # 5. Embed
    print("Embedding extracted claims...")
    query_embs = embed_texts(model, claim_texts, prefix="query: ")

    doc_texts = [f"{doc['title']}. {doc['abstract']}" for doc in collection]
    print("Embedding documents...")
    doc_embs = embed_texts(model, doc_texts, prefix="passage: ")

    # 6. Retrieve top 100
    print("Retrieving top 100 candidates...")
    final_results = retrieve(query_embs, doc_embs, queries, collection, top_k=100)

    # 7. Evaluate
    if qrels:
        metrics = evaluate(final_results, qrels)
        print_metrics(metrics, label=f"Claim Extraction | {lang} {split}")

    # 8. Save
    run_name = f"exp2_claim_extraction_{lang}_{split}"
    save_run(final_results, run_name)

    # Save the TSV format ONLY if evaluating on the test split (for official submission)
    # Or remove the if-statement if you just want to generate it every time to check the formatting
    if split == "test":
        save_tsv_submission(final_results, lang)

    return final_results, metrics if qrels else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev", choices=["train", "dev", "test"])
    parser.add_argument("--lang", default="en", choices=["en", "de", "fr"])
    parser.add_argument("--provider", default="ollama", choices=["ollama"])
    parser.add_argument("--ollama-model", default="llama3")
    args = parser.parse_args()

    run_experiment(split=args.split, lang=args.lang,
                   provider=args.provider, ollama_model=args.ollama_model)
