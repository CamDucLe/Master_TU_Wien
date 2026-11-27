# Assignment 2

This repository contains three Spark-based exercises for data-intensive computing:

1. Part 1 builds a chi-square feature ranking with RDDs.
2. Part 2 builds a Spark ML pipeline with DataFrames.
3. Part 3 trains and tunes a text classifier with Spark ML.

The implementations live in [src/](../src), and the generated outputs are written to [output/](../output).

## Local Development

- Python 3.12 or newer
- Java and a local Spark-compatible runtime
- Dependencies installed through `uv`

Install the environment from the repository root:

```bash
uv sync
source .venv/bin/activate
```

## Data

The default inputs are:

- [data/reviews_devset.json](../data/reviews_devset.json)
- [data/stopwords.txt](../data/stopwords.txt)

You can override them with environment variables:

- `REVIEWS_FILE_PATH`
- `STOPWORDS_FILE_PATH`

## Run

Run each task from the repository root:

### Local
```bash
python3 -m src.part1_rdds
python3 -m src.part2_dataframes
python3 -m src.part3_classification
```

### Hadoop Cluster
```bash
sh src/part_1_script_cluster.sh
sh src/part_2_script_cluster.sh
sh src/part_3_script_cluster.sh
```


## Outputs

- Part 1 writes chi-square term rankings to `output/output_rdd.txt`.
- Part 2 writes the selected vocabulary to `output/output_ds.txt`.
- Part 3 writes the best validation settings and test F1 score to `output/part3_best_params.txt`.

## Notes

- The scripts use `local[*]` so they run on a single machine.
- Part 3 performs a TrainValidationSplit grid search and can take noticeably longer than the other parts.
