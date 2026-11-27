# Feel free to change the imports according to your implementation and needs
import argparse
import os
import torch
from torch.utils.data import DataLoader
import torchvision.transforms.v2 as v2
import os

from tqdm import tqdm  # change to the model you want to test
from assignment_1_code.models.class_model import DeepClassifier
from assignment_1_code.models.vit import ViT
from assignment_1_code.metrics import Accuracy
from assignment_1_code.datasets.cifar10 import CIFAR10Dataset
from assignment_1_code.datasets.dataset import Subset
from config import DATA_DIR, MODEL_SAVE_DIR
from datetime import datetime


def test(args):

    transform = v2.Compose(
        [
            v2.ToImage(),
            v2.ToDtype(torch.float32, scale=True),
            v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    # Use config.py for machine-dependent paths, e.g. DATA_DIR and MODEL_SAVE_DIR.
    test_data = CIFAR10Dataset(
        fdir=DATA_DIR,  # type: ignore
        subset=Subset.TEST,
        transform=transform,
    )
    test_loader = DataLoader(
        test_data, batch_size=args.batch_size, shuffle=False, num_workers=4,  # type: ignore
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    num_test_data = len(test_data)

    # Use ViT as a backbone
    net = ViT()
    model = DeepClassifier(net=net)
    model.load(args.path_to_trained_model)
    model.to(device)

    loss_fn = torch.nn.CrossEntropyLoss()

    test_metric = Accuracy(classes=test_data.classes)

    # Below implement testing loop and print final loss
    # and metrics to terminal after testing is finished
    # ...

    test_loss, test_macc, test_mpacc = 0.0, 0.0, 0.0
    model.eval()
    with torch.no_grad():
        for images, labels in tqdm(test_loader):
            images, labels = images.to(device), labels.to(device)

            outputs = model(images)

            loss = loss_fn(outputs, labels)
            test_loss += loss.item() * images.size(0)

            test_metric.update(outputs.cpu(), labels.cpu())

    test_loss /= num_test_data
    test_macc = test_metric.accuracy()
    test_mpacc = test_metric.per_class_accuracy()

    print(f"Test Loss: {test_loss:.4f}")
    print(f"Test Mean Accuracy: {test_macc:.4f}")
    print(f"Test Mean Per-Class Accuracy: {test_mpacc:.4f}")


if __name__ == "__main__":
    # Feel free to change this part - you do not have to use this argparse and gpu handling
    parser = argparse.ArgumentParser(description="Training")
    parser.add_argument(
        "-d", "--gpu_id", default="0", type=str, help="index of which GPU to use"
    )

    parser.add_argument("--batch_size", type=int, default=727)

    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)

    # convenience attributes used by the train function
    args.batch_size = args.batch_size
    args.path_to_trained_model = os.path.join(MODEL_SAVE_DIR, "model.pt")

    start = datetime.now()
    test(args)
    end = datetime.now()
    print(f"Testing time for batch_size={args.batch_size}: {end - start}")
