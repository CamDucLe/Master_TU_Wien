from datasets import load_dataset
import json

REPO = "sschellhammer/CT26_Task1_SourceRetrievalForScientificWebClaims"

for cfg in ['collection', 'en', 'de', 'fr', 'test']:
    print(f'\n=== {cfg} ===')
    ds = load_dataset(REPO, cfg)
    print(ds)
    for split in ds:
        sample = ds[split][0]
        print(f'  Split: {split}')
        print(f'  First row keys: {list(sample.keys())}')
        sample_str = json.dumps(sample, ensure_ascii=False, default=str)[:600]
        print(f'  Sample: {sample_str}')
