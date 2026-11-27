from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

from dataset import PascalVOCSubsetDataset
from LocateAnything import LocateAnythingWorker
from yolo26 import YOLO26Worker


DATASET_PATH = "data/voc_subset"
VOC_COMMON_CLASSES: tuple[str, ...] = (
	"person",
	"aeroplane",
	"car",
	"cat",
	"dog",
	"chair",
	"bottle",
)


def _font() -> Any:
	try:
		return ImageFont.truetype("DejaVuSans.ttf", 14)
	except OSError:
		return ImageFont.load_default()


def _draw_boxes(
	image: Image.Image,
	boxes: Iterable[dict[str, object]],
	title: str,
	color: str,
) -> Image.Image:
	annotated = image.copy()
	draw = ImageDraw.Draw(annotated)
	font = _font()

	for box in boxes:
		bbox = box["bbox"]
		left, top, right, bottom = [int(round(float(value))) for value in bbox]  # type: ignore[arg-type]
		label = str(box.get("class", "object"))
		confidence = box.get("confidence")
		if isinstance(confidence, (int, float)):
			label = f"{label} {confidence:.2f}"

		draw.rectangle([left, top, right, bottom], outline=color, width=3)
		text_bbox = draw.textbbox((0, 0), label, font=font)
		text_width = text_bbox[2] - text_bbox[0]
		text_height = text_bbox[3] - text_bbox[1]
		text_left = left
		text_top = max(0, top - text_height - 4)
		draw.rectangle(
			[text_left, text_top, text_left + text_width + 6, text_top + text_height + 4],
			fill=color,
		)
		draw.text((text_left + 3, text_top + 2), label, fill="white", font=font)

	draw.rectangle([0, 0, annotated.width - 1, annotated.height - 1], outline=color, width=2)
	draw.text((8, 8), title, fill=color, font=font)
	return annotated


def _predict_yolo(worker: YOLO26Worker, image: Image.Image) -> list[dict[str, object]]:
	result = worker.detect(image)[0]
	predictions: list[dict[str, object]] = []

	for box in result.boxes:
		cls_id = int(box.cls.item())
		cls_name = result.names[cls_id]
		if cls_name not in VOC_COMMON_CLASSES:
			continue

		confidence = float(box.conf.item())
		predictions.append(
			{
				"class": cls_name,
				"confidence": confidence,
				"bbox": box.xyxy[0].tolist(),
			}
		)

	return predictions


def _predict_locate_anything(
	worker: LocateAnythingWorker,
	image: Image.Image,
) -> list[dict[str, object]]:
	width, height = image.size
	response = worker.detect(
		image=image,
		categories=list(VOC_COMMON_CLASSES),
		verbose=False,
	)
	answer = str(response["answer"])
	predictions: list[dict[str, object]] = []

	for box in worker.parse_boxes(answer, width, height):
		if box["class"] not in VOC_COMMON_CLASSES:
			continue

		predictions.append(
			{
				"class": box["class"],
				"bbox": [box["x1"], box["y1"], box["x2"], box["y2"]],
			}
		)

	return predictions


def visualize_indices(
	indices: list[int],
	dataset_path: str = DATASET_PATH,
	save_dir: str | Path | None = None,
) -> list[Path]:
	dataset = PascalVOCSubsetDataset(dataset_path)
	yolo_worker = YOLO26Worker()
	locate_anything_worker = LocateAnythingWorker()

	output_paths: list[Path] = []
	output_dir = Path(save_dir) if save_dir is not None else None
	if output_dir is not None:
		output_dir.mkdir(parents=True, exist_ok=True)

	for index in indices:
		image, metadata = dataset[index]
		yolo_predictions = _predict_yolo(yolo_worker, image)
		locate_anything_predictions = _predict_locate_anything(locate_anything_worker, image)

		yolo_image = _draw_boxes(
			image,
			yolo_predictions,
			title=f"YOLO26 | {metadata['image_id']}",
			color="#ff8c42",
		)
		locate_anything_image = _draw_boxes(
			image,
			locate_anything_predictions,
			title=f"LocateAnything | {metadata['image_id']}",
			color="#2ec4b6",
		)

		fig, axes = plt.subplots(1, 2, figsize=(16, 8))
		for ax, annotated, subtitle in zip(
			axes,
			[yolo_image, locate_anything_image],
			["YOLO26", "LocateAnything"],
			strict=True,
		):
			ax.imshow(annotated)
			ax.set_title(subtitle)
			ax.axis("off")

		fig.suptitle(
			f"Index {index} | image_id={metadata['image_id']} | classes={', '.join(VOC_COMMON_CLASSES)}"
		)
		fig.tight_layout()

		if output_dir is not None:
			output_path = output_dir / f"visualize_{index:04d}_{metadata['image_id']}.png"
			fig.savefig(output_path, dpi=200, bbox_inches="tight")
			output_paths.append(output_path)
			plt.close(fig)
		else:
			plt.show()

	return output_paths


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Visualize predictions from YOLO26 and LocateAnything.")
	parser.add_argument(
		"indices",
		nargs="+",
		type=int,
		help="Dataset indices to visualize.",
	)
	parser.add_argument(
		"--dataset-path",
		default=DATASET_PATH,
		help="Path to the Pascal VOC subset dataset.",
	)
	parser.add_argument(
		"--save-dir",
		default="figures",
		help="Optional directory for saving rendered figures.",
	)
	return parser.parse_args()


def main() -> None:
	args = parse_args()
	visualize_indices(args.indices, dataset_path=args.dataset_path, save_dir=args.save_dir)


if __name__ == "__main__":
	main()
