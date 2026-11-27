from dataset import PascalVOCSubsetDataset
from yolo26 import YOLO26Worker
from LocateAnything import LocateAnythingWorker
from util import extract_gt_boxes, evaluate_predictions
from tqdm import tqdm


VOC_COMMON_CLASSES: tuple[str, ...] = (
	"person",
	"aeroplane",
	"car",
	"cat",
	"dog",
	"chair",
	"bottle",
)

DATASET_PATH: str = "data/voc_subset"
YOLO_CONF_THRESHOLD: float = 0.25
MIOU_IOU_THRESHOLD: float = 0.5
IS_TEST = True


def run_yolo26(
    worker: YOLO26Worker,
    dataset: PascalVOCSubsetDataset,
):
    dataset_ious = []

    for idx in tqdm(
        range(len(dataset)),
        desc="Running YOLO26",
    ):
        image, metadata = dataset[idx]

        gt_boxes = extract_gt_boxes(
            metadata["objects"]
        )

        results = worker.detect(image)

        result = results[0]
        print(result.boxes)

        predictions = []

        for box in result.boxes:

            cls_id = int(box.cls.item())
            cls_name = result.names[cls_id]

            if cls_name not in VOC_COMMON_CLASSES:
                continue

            conf = float(box.conf.item())

            if conf < YOLO_CONF_THRESHOLD:
                continue

            predictions.append(
                {
                    "class": cls_name,
                    "confidence": conf,
                    "bbox": box.xyxy[0].tolist(),
                }
            )

        metrics = evaluate_predictions(
            gt_boxes,
            predictions,
            iou_threshold=MIOU_IOU_THRESHOLD,
        )

        dataset_ious.append(metrics["miou"])

        print(
            f"image={metadata['image_id']} "
            f"mIoU={metrics['miou']:.4f}"
        )

        if IS_TEST and idx >= 0:
            break

    final_miou = (
        sum(dataset_ious) / len(dataset_ious)
        if dataset_ious
        else 0.0
    )

    print(
        f"\nYOLO26 dataset mIoU = "
        f"{final_miou:.4f}"
    )

    return final_miou


def run_locate_anything(
    worker: LocateAnythingWorker,
    dataset: PascalVOCSubsetDataset,
):
    dataset_ious = []

    for idx in tqdm(range(len(dataset)), desc="Running LocateAnything"):
        image, metadata = dataset[idx]

        width, height = image.size

        gt_boxes = extract_gt_boxes(
            metadata["objects"]
        )

        response = worker.detect(
            image=image,
            categories=list(VOC_COMMON_CLASSES),
            verbose=False,
        )

        answer = response["answer"]

        predictions = []

        for box in worker.parse_boxes(answer, width, height):
            if box["class"] not in VOC_COMMON_CLASSES:
                continue

            predictions.append(
                {
                    "class": box["class"],
                    "bbox": [
                        box["x1"],
                        box["y1"],
                        box["x2"],
                        box["y2"],
                    ],
                }
            )

        metrics = evaluate_predictions(
            gt_boxes,
            predictions,
            iou_threshold=MIOU_IOU_THRESHOLD,
        )

        dataset_ious.append(metrics["miou"])

        print(
            f"image={metadata['image_id']} "
            f"mIoU={metrics['miou']:.4f}"
        )

        if IS_TEST and idx >= 0:
            break

    final_miou = (
        sum(dataset_ious) / len(dataset_ious)
        if dataset_ious
        else 0.0
    )

    print(
        f"\nLocateAnything dataset mIoU = "
        f"{final_miou:.4f}"
    )

    return final_miou


def main() -> None:
    sub_dataset = PascalVOCSubsetDataset(DATASET_PATH)

    yolo_worker = YOLO26Worker()
    run_yolo26(yolo_worker, sub_dataset)

    locate_anything_worker = LocateAnythingWorker()
    run_locate_anything(locate_anything_worker, sub_dataset)


if __name__ == "__main__":
	main()
