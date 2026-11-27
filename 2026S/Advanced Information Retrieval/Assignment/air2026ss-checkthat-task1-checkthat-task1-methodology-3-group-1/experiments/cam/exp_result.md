# Experiment Structure

### Baseline
- **Each publication:** `"passage: title + venue + abstract + authors"` (max 512 tokens)  
- **Each query:** `"query: + query"` (max 128 tokens)  
- **Embedding model:** `multilingual-e5-large`  
- **Re-ranking model:** None  

---

### Preprocessing / Experiment Variants

- Translate all data into a pivot language (`done`)
- Normalize tweet style into scientific style (`TODO`)
- Extract and rewrite the core claim (`done`)
- Remove rhetorical framing (`?`)
- Rewrite abstracts into tweet-like summaries (`done`)
- Apply reranking (`done`)

---

### Results

| Method | train_ev | dev_en | train_de | dev_de | train_fr | dev_fr |
|------|------|------|------|------|------|------|
| **Baseline** | 0.5012 | 0.4985 | 0.3702 | 0.3744 | 0.4683 | 0.4558 |
| **Baseline + Reranker (bge-reranker-m3-v2)** | - | - | **0.4312** | **0.4432** | **0.5632** | **0.5283** |
| **Tweet Translation (gemma3-1b-it)** | 0.5012 | 0.4985 | **0.3730** | **0.3968** | **0.4939** | **0.4751** |
| **Tweet Rewriting (gemma3-270m-it)** | - | - | 0.3513 | 0.3516 | 0.4635 | 0.4441 |
| **Abstract Rewriting (gemma3-270m-it)** | 0.3307 | 0.3457 | 0.2691 | 0.3032 | 0.3916 | 0.3920 |
| **Query cleaning** | - | - | 0.3813 | 0.3824 | 0.4652 | 0.4607 |

Note:

    - Biases: the way I chose small language model, hyperparams, prompt may affect the result.
    - Gema3-270m-it just for fast inference. I use Gemma3-1B and Qwen3.5-0.8B as the main language model.
    - Experiment focus on "de" and "fr" as the performance of baseline on these language is much worse compared to "en". Furthermore, too many samples for english (take too much time).
