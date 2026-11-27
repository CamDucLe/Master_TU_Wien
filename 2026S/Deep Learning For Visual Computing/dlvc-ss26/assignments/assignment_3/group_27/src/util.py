def extract_gt_boxes(objects):
    gt = []

    for obj in objects:
        bbox = obj.get("bbox", obj)

        gt.append(
            {
                "class": obj["name"],
                "bbox": [
                    bbox["xmin"],
                    bbox["ymin"],
                    bbox["xmax"],
                    bbox["ymax"],
                ],
            }
        )

    return gt


def compute_iou(box1, box2):
    """
    xyxy format
    """

    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)

    inter_area = inter_w * inter_h

    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])

    union = area1 + area2 - inter_area

    if union <= 0:
        return 0.0

    return inter_area / union


def evaluate_predictions(
    gt_boxes,
    pred_boxes,
    iou_threshold=0.5,
):
    matched_gt = set()

    ious = []

    for pred in pred_boxes:

        best_iou = 0.0
        best_gt_idx = -1

        for gt_idx, gt in enumerate(gt_boxes):

            if gt_idx in matched_gt:
                continue

            if pred["class"] != gt["class"]:
                continue

            iou = compute_iou(
                pred["bbox"],
                gt["bbox"],
            )

            if iou > best_iou:
                best_iou = iou
                best_gt_idx = gt_idx

        if best_iou >= iou_threshold:
            matched_gt.add(best_gt_idx)
            ious.append(best_iou)

    return {
        "matched": len(ious),
        "gt_count": len(gt_boxes),
        "miou": sum(ious) / len(ious) if ious else 0.0,
    }
