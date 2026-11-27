from __future__ import annotations

import json
import random
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence
from xml.etree import ElementTree as ET

from PIL import Image
from torch.utils.data import Dataset
from torchvision.datasets import VOCDetection


DEFAULT_VOC_YEAR_TUPLE: tuple[str, ...] = ("2012",)
DEFAULT_VOC_IMAGE_SETS: tuple[str, ...] = ("trainval",)


@dataclass(frozen=True)
class PascalVOCRecord:
	"""Metadata for one sampled VOC image/annotation pair."""

	image_id: str
	year: str
	image_set: str
	source_image_path: str
	source_annotation_path: str
	image_path: str
	annotation_path: str
	objects: list[dict[str, Any]]


def _ensure_downloaded(root: Path, years: Sequence[str], image_sets: Sequence[str]) -> None:
	for year in years:
		for image_set in image_sets:
			VOCDetection(root=root, year=year, image_set=image_set, download=True)


def _parse_objects(annotation_path: Path) -> list[dict[str, Any]]:
	annotation_root = ET.parse(annotation_path).getroot()
	voc_dict = VOCDetection.parse_voc_xml(annotation_root)["annotation"]
	objects = voc_dict.get("object", [])
	if isinstance(objects, dict):
		objects = [objects]

	parsed_objects: list[dict[str, Any]] = []
	for obj in objects:
		bbox = obj.get("bndbox", {})
		parsed_objects.append(
			{
				"name": obj.get("name"),
				"pose": obj.get("pose"),
				"truncated": obj.get("truncated"),
				"difficult": obj.get("difficult"),
				"bbox": {
					"xmin": int(bbox.get("xmin", 0)),
					"ymin": int(bbox.get("ymin", 0)),
					"xmax": int(bbox.get("xmax", 0)),
					"ymax": int(bbox.get("ymax", 0)),
				},
			}
		)
	return parsed_objects


def _collect_records(
	root: Path,
	years: Sequence[str],
	image_sets: Sequence[str],
) -> list[PascalVOCRecord]:
	records: list[PascalVOCRecord] = []
	for year in years:
		for image_set in image_sets:
			dataset = VOCDetection(root=root, year=year, image_set=image_set, download=False)
			for image_path, annotation_path in zip(dataset.images, dataset.annotations, strict=True):
				image_id = Path(image_path).stem
				records.append(
					PascalVOCRecord(
						image_id=image_id,
						year=year,
						image_set=image_set,
						source_image_path=str(Path(image_path).resolve()),
						source_annotation_path=str(Path(annotation_path).resolve()),
						image_path=str(Path(image_path).resolve()),
						annotation_path=str(Path(annotation_path).resolve()),
						objects=_parse_objects(Path(annotation_path)),
					)
				)

	return records


def download_pascal_voc(
	root: str | Path,
) -> None:
	"""Download the official Pascal VOC archives if they are not present yet."""

	root_path = Path(root)
	_ensure_downloaded(root_path, DEFAULT_VOC_YEAR_TUPLE, DEFAULT_VOC_IMAGE_SETS)

	return


def create_pascal_voc_subset(
	root: str | Path,
	output_root: str | Path,
	sample_size: int = 1000,
	seed: int = 27,
) -> Path:
	"""Download Pascal VOC, sample image/annotation pairs, and copy them to a subset folder.

	The copied subset includes a `manifest.json` file with the sampled records and
	preserves the original images and XML annotations.
	"""

	root_path = Path(root)
	output_path = Path(output_root)

	# _ensure_downloaded(root_path, DEFAULT_VOC_YEAR_TUPLE, DEFAULT_VOC_IMAGE_SETS)
	records = _collect_records(root_path, DEFAULT_VOC_YEAR_TUPLE, DEFAULT_VOC_IMAGE_SETS)

	if not records:
		raise RuntimeError("No Pascal VOC records were found after download.")

	sample_count = min(sample_size, len(records))
	rng = random.Random(seed)
	sampled_records = rng.sample(records, sample_count)

	# Create output directories
	images_dir = output_path / "images"
	annotations_dir = output_path / "annotations"
	images_dir.mkdir(parents=True, exist_ok=True)
	annotations_dir.mkdir(parents=True, exist_ok=True)

	# Copy sampled records and build manifest
	manifest: dict[str, Any] = {
		"source_root": str(root_path.resolve()),
		"output_root": str(output_path.resolve()),
		"sample_size_requested": sample_size,
		"sample_size_actual": sample_count,
		"seed": seed,
		"years": list(DEFAULT_VOC_YEAR_TUPLE),
		"image_sets": list(DEFAULT_VOC_IMAGE_SETS),
		"records": [],
	}

	for record in sampled_records:
		subset_stem = f"voc_{record.year}_{record.image_set}_{record.image_id}"
		copied_image_path = images_dir / f"{subset_stem}.jpg"
		copied_annotation_path = annotations_dir / f"{subset_stem}.xml"

		shutil.copy2(record.source_image_path, copied_image_path)
		shutil.copy2(record.source_annotation_path, copied_annotation_path)

		manifest_record = asdict(record)
		manifest_record["image_path"] = str(copied_image_path.relative_to(output_path))
		manifest_record["annotation_path"] = str(copied_annotation_path.relative_to(output_path))
		manifest_record["copied_image_path"] = str(copied_image_path.resolve())
		manifest_record["copied_annotation_path"] = str(copied_annotation_path.resolve())
		manifest["records"].append(manifest_record)

	manifest_path = output_path / "manifest.json"
	with manifest_path.open("w", encoding="utf-8") as handle:
		json.dump(manifest, handle, indent=2)

	return output_path


class PascalVOCSubsetDataset(Dataset):
	"""Dataset wrapper around a subset created by `create_pascal_voc_subset`."""

	def __init__(self, subset_root: str | Path):
		self.subset_root = Path(subset_root)
		manifest_path = self.subset_root / "manifest.json"
		if not manifest_path.exists():
			raise FileNotFoundError(f"Missing manifest file: {manifest_path}")

		with manifest_path.open("r", encoding="utf-8") as handle:
			manifest = json.load(handle)

		self.records: list[dict[str, Any]] = list(manifest.get("records", []))

	def __len__(self) -> int:
		return len(self.records)

	def __getitem__(self, index: int) -> tuple[Image.Image, dict[str, Any]]:
		record = self.records[index]
		image_path = self.subset_root / record["image_path"]
		annotation_path = self.subset_root / record["annotation_path"]

		image = Image.open(image_path).convert("RGB")
		annotation = _parse_objects(annotation_path)
		return image, {
			"image_id": record["image_id"],
			"year": record["year"],
			"image_set": record["image_set"],
			"objects": annotation,
		}


if __name__ == "__main__":
	root = "data"                   # where VOC will be downloaded / is located
	output = "data/voc_subset"      # destination for sampled subset

	# download VOC (will skip if already present)
	download_pascal_voc(root)

	# create subset (adjust sample_size and seed as desired)
	create_pascal_voc_subset(root, output)

	# load and inspect
	ds = PascalVOCSubsetDataset(output)
	print("subset size:", len(ds))
	img, meta = ds[0]
	print(meta)
