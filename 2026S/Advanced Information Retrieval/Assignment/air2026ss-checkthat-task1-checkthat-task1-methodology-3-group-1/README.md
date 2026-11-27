# CLEF CheckThat! 2026 — Task 1: Source Retrieval for Scientific Web Claims
## Course Project Template

This repository is your team's workspace for the course project. You will participate in
[CLEF CheckThat! Task 1](https://checkthat.gitlab.io/) and develop a retrieval system under
your assigned methodological track.

**Core problem:** Given a tweet containing a scientific claim, retrieve the corresponding
scientific paper (title + abstract).

---

## Getting Started

### 1. Register your team (do this first)

Open [`team.toml`](team.toml) and fill in your details, then verify with:

```bash
python validate_team.py
```

Fields to fill in:
- `team_name` — must exactly match the name under which you registered for CLEF CheckThat! Task 1
- `track` — your assigned track number (1–5)
- `members` — name, immatriculation number, and GitHub username for each of the 5 members

Commit `team.toml` to your repository. Failure to do so means your project cannot be matched
to TUWEL and **cannot be graded**.

### 2. Register for CLEF CheckThat!

Register your team for CLEF CheckThat! Task 1 and note the team name — it must match what
you put in `team.toml`.

### 3. Get the Data

The dataset is hosted on Hugging Face:
[sschellhammer/CT26_Task1_SourceRetrievalForScientificWebClaims](https://huggingface.co/datasets/sschellhammer/CT26_Task1_SourceRetrievalForScientificWebClaims)

Fill out the Declaration of Commitment on the Hugging Face page to get access, then
[authenticate your runtime](https://huggingface.co/docs/hub/datasets-polars-auth).

The dataset includes:
- Query sets (English, German, French) for training and development
- A shared collection across all languages and splits

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Project Tracks

Each team works on exactly one track. The track is assigned by the course instructors.

### Track 1 — Small & Distilled Models (< 0.5B parameters)
**Focus:** Efficient and lightweight retrieval systems.
- All models must be below ~0.5B parameters
- Model distillation is required
- Evaluate retrieval latency, model size, and performance/efficiency trade-offs

### Track 2 — Large / High-Capacity Models
**Focus:** Maximum retrieval accuracy, ignoring computational cost.
- Allowed: large encoders, fine-tuning, cross-encoder reranking, multi-stage pipelines, hard negative mining
- Goal: push performance as high as possible

### Track 3 — Translation & Rewriting
**Focus:** Transform tweets and/or documents before retrieval.
- Directions: pivot-language translation, tweet-to-scientific-style normalization, core claim extraction, abstract rewriting
- Constraint: main contribution must be in transformation, not model scaling
- Use a fixed baseline model to compare strategies

### Track 4 — Query Engineering & Retrieval Signals
**Focus:** Intelligent query formulation and scoring.
- Directions: entity extraction & boosting, numeric matching, term weighting, query reduction, pseudo-relevance feedback, hybrid lexical/dense scoring
- Constraints: no heavy rewriting pipelines, no large model fine-tuning

### Track 5 — Document Representation & Indexing Strategies
**Focus:** How scientific papers are represented and indexed.
- Directions: title-only vs abstract-only, sentence-level indexing, claim-sentence extraction, multi-view representations, document-side weighting
- Constraint: keep the query side relatively fixed

---

## Deliverables & Grading

| Component | Weight | Description |
|-----------|--------|-------------|
| Competition Registration | required | Must register — unregistered teams cannot be graded |
| Competitive Baseline | 20% | Retrieval + reranking pipeline with at least one fine-tuned model, evaluated on dev and test |
| Track-Specific Research | 50% | Multiple meaningful experiments, ablations, literature engagement, error analysis |
| Report | 20% | 2-page ACM-style (double column): system description, experimental setup, results, discussion |
| Run Submission | 10% | Run files submitted to the shared task platform, mirrored in `runs/` in this repository |
| Code Submission | required | This repository, including all scripts and reproduction instructions |

### Report Requirements
The 2-page report must include: system description, experimental setup, results, discussion.

**Appendix** (not counted toward page limit): work distribution, team name, optional extra tables/runtimes.

### Code Requirements
Your repository must include:
- Scripts to reproduce all submitted runs
- Environment setup instructions (`requirements.txt` or equivalent)
- Model checkpoints or instructions to obtain them
- The code must run with reasonable effort — non-runnable code may lose credit

---

## Repository Structure

Organize your repository as follows (adapt as needed for your track):

```
├── team.toml                # Fill in your team details — commit this
├── validate_team.py         # Run to check team.toml is correct
├── README.md                # This file — replace with a description of your system
├── requirements.txt         # Python dependencies
├── task1/                   # Baseline notebook and scorer (do not modify)
├── baseline/                # Your baseline pipeline (retrieval + reranking)
├── experiments/             # Track-specific experiments
├── runs/                    # Mirror of the run files you submitted to the shared task
└── report/                  # PDF of your 2-page ACM report
```

> Note: Do not commit raw datasets or model weights. Large files will be rejected.

---

## Baseline

A reference baseline is provided in [`task1/CT26_Task1_baseline.ipynb`](task1/CT26_Task1_baseline.ipynb).
It uses `multilingual-e5-large` to embed tweets and papers and ranks by cosine similarity.

Use it as your starting point. Your baseline must be competitive — check the CLEF 2025
proceedings for reference systems and scores.

---

## Evaluation

Use the provided scorer to evaluate on development data:

```bash
python task1/scorer.py --run <your_run_file> --qrels <qrels_file>
```

## Run Submission

Submit your runs to the shared task platform as instructed by the CLEF organisers.
Then copy the exact same files into the `runs/` folder of this repository and commit them —
no format conversion needed, we just need the same files you submitted.

---

## Questions?

Post questions in the course forum on TUWEL or contact the course instructors.
