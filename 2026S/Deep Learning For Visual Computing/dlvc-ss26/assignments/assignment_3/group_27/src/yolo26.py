import torch
from ultralytics import YOLO


class YOLO26Worker:
    def __init__(self):
        # Load a COCO-pretrained YOLO26n model
        self.model = YOLO("yolo26n.pt")  # 2.4 M parameters
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device).eval()

    def detect(self, image):
        # Perform inference on the input image
        results = self.model(image)

        return results
