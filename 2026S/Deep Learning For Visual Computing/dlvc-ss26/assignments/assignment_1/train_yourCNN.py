import argparse
import os
import torch
from torch.utils.data import DataLoader
import torch.nn as nn
import torchvision.transforms.v2 as v2
from pathlib import Path
import os

from assignment_1_code.models.class_model import DeepClassifier
from assignment_1_code.models.cnn import YourCNN
from assignment_1_code.metrics import Accuracy
from assignment_1_code.trainer import ImgClassificationTrainer
from assignment_1_code.datasets.cifar10 import CIFAR10Dataset
from assignment_1_code.datasets.dataset import Subset
from config import DATA_DIR, MODEL_SAVE_DIR


class DropoutLinear(nn.Linear):
    def __init__(self, in_features: int, out_features: int, dropout: float) -> None:
        super().__init__(in_features, out_features)
        self.dropout = dropout

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = nn.functional.dropout(x, p=self.dropout, training=self.training)
        return super().forward(x)


def train(args):

    # Implement this function so that it trains a specific model as described in the instruction.md file
    # feel free to change the code snippets given here, they are just to give you an initial structure
    # but do not have to be used if you want to do it differently
    # For device handling you can take a look at pytorch documentation

    train_transform = v2.Compose(
        [
            v2.ToImage(),
            v2.ToDtype(torch.float32, scale=True),
            v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    val_transform = v2.Compose(
        [
            v2.ToImage(),
            v2.ToDtype(torch.float32, scale=True),
            v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )

    # Use config.py for all machine-dependent paths, e.g. DATA_DIR.
    train_dataset = CIFAR10Dataset(
        fdir=DATA_DIR,
        subset=Subset.TRAINING,
        transform=train_transform,
    )
    val_dataset = CIFAR10Dataset(
        fdir=DATA_DIR,
        subset=Subset.VALIDATION,
        transform=val_transform,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    net = YourCNN()
    model = DeepClassifier(net=net)

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=2
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=2
    )

    model.to(device)

    # TO RUN
    # optimizer = torch.optim.SGD(model.parameters(), lr=args.lr)
    # optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.lr,
        # weight_decay=args.weight_decay,
    )
    # optimizer = torch.optim.NAdam(model.parameters(), lr=args.lr)

    loss_fn = torch.nn.CrossEntropyLoss()

    train_metric = Accuracy(classes=train_dataset.classes)
    val_metric = Accuracy(classes=val_dataset.classes)
    val_frequency = args.val_frequency

    model_save_dir = Path(MODEL_SAVE_DIR)
    model_save_dir.mkdir(exist_ok=True)

    # TO RUN
    lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=7, gamma=0.27)
    # lr_scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min')
    # lr_scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.num_epochs)
    # lr_scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=args.lr, steps_per_epoch=len(train_loader), epochs=args.num_epochs)

    trainer = ImgClassificationTrainer(
        model,
        optimizer,
        loss_fn,
        lr_scheduler,
        train_metric,
        val_metric,
        train_loader,
        val_loader,
        device,
        args.num_epochs,
        model_save_dir,
        batch_size=args.batch_size,
        val_frequency=val_frequency,
    )
    trainer.train()


if __name__ == "__main__":
    # Feel free to change this part - you do not have to use this argparse and gpu handling
    parser = argparse.ArgumentParser(description="Training")
    parser.add_argument(
        "-d", "--gpu_id", default="0", type=str, help="index of which GPU to use"
    )
    parser.add_argument("--num_epochs", type=int, default=3)
    parser.add_argument("--batch_size", type=int, default=273)
    parser.add_argument("--lr", type=float, default=0.01)
    parser.add_argument("--val_frequency", type=int, default=3)
    parser.add_argument("--weight_decay", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.0)

    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = str(args.gpu_id)

    # convenience attributes used by the train function
    args.num_epochs = args.num_epochs
    args.batch_size = args.batch_size
    args.lr = args.lr
    args.val_frequency = args.val_frequency
    args.weight_decay = args.weight_decay
    args.dropout = args.dropout

    train(args)
