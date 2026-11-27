# YOLO26 vs LocateAnything

This project compares two open-source models on object detection:

- **YOLO26** from Ultralytics
- **LocateAnything** from NVIDIA

The main question is whether a vision-language model can achieve performance comparable to a dedicated object detector on a Pascal VOC subset.

## What the project does

The code downloads / reuses Pascal VOC data, creates a sampled subset, runs both models on the same images, and evaluates them with mIoU on a small set of common classes:

- person
- aeroplane
- car
- cat
- dog
- chair
- bottle

The project also includes a visualization script to compare predictions side by side.

## Python files

### `dataset.py`

Prepares the dataset.

- Downloads Pascal VOC if needed
- Builds a sampled VOC subset with image and annotation pairs
- Writes `data/voc_subset/manifest.json`
- Exposes `PascalVOCSubsetDataset` for loading images and annotations later

### `util.py`

Contains evaluation helpers.

- `extract_gt_boxes(...)` converts VOC annotations to the internal box format
- `compute_iou(...)` computes Intersection over Union for two boxes
- `evaluate_predictions(...)` matches predictions to ground truth and returns mIoU

### `yolo26.py`

Wraps YOLO26 inference.

- Loads `yolo26n.pt`
- Runs detection on a single image
- Returns the raw Ultralytics results object

### `LocateAnything.py`

Wraps LocateAnything inference.

- Loads the remote model from the Hugging Face Hub
- Handles the model's custom remote-code loading
- Parses LocateAnything text output into bounding boxes
- Includes compatibility fixes for newer Transformers versions

### `inference.py`

Runs the quantitative comparison.

- Loads the Pascal VOC subset
- Runs YOLO26 and LocateAnything on the same dataset
- Filters predictions to the shared classes
- Computes mIoU for each model
- Prints final dataset-level scores

### `visualize.py`

Creates qualitative comparisons.

- Takes a list of dataset indices
- Runs both models on those images
- Draws predicted boxes on the images
- Shows or saves side-by-side figures

## Overall workflow

1. Create or reuse the VOC subset with `dataset.py`.
2. Run `inference.py` to compute the mIoU for YOLO26 and LocateAnything.
3. Run `visualize.py` on selected indices to inspect qualitative predictions.
4. Use the measured scores and example figures in the report.

## How to run

Go to src directory:

```bash
cd src
```


Set up virtual environment:

```bash
uv sync
source .venv/bin/activate
```

Create the dataset subset if needed:

```bash
python3 dataset.py
```

Run the quantitative evaluation:

```bash
python3 inference.py
```

Generate visual comparisons for selected indices:

```bash
python3 visualize.py
```
