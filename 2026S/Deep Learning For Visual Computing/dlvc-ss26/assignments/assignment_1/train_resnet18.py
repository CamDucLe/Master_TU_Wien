# Feel free to change the imports according to your implementation and needs
import argparse
import os
import torch
from torch.utils.data import DataLoader
from torchvision.models import resnet18
import torch.nn as nn
import torchvision.transforms.v2 as v2
from pathlib import Path
import os

from assignment_1_code.models.class_model import (
    DeepClassifier,
)  # etc. change to your model
from assignment_1_code.metrics import Accuracy
from assignment_1_code.trainer import ImgClassificationTrainer
from assignment_1_code.datasets.cifar10 import CIFAR10Dataset
from assignment_1_code.datasets.dataset import Subset
from config import DATA_DIR, MODEL_SAVE_DIR


def add_dropout(model, p=0.0):
    if p <= 0.0:
        return model

    for name, module in model.named_children():

        if name == "fc":
            continue

        if isinstance(module, nn.Linear):
            setattr(model, name, nn.Sequential(module, nn.Dropout(p)))

        elif isinstance(module, nn.Conv2d):
            setattr(model, name, nn.Sequential(module, nn.Dropout2d(p)))

        else:
            add_dropout(module, p)

    return model

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
            # # TO RUN: Apply data augmentation
            v2.RandomHorizontalFlip(p=0.27),
            v2.RandomCrop(size=32, padding=4),
            v2.RandomRotation(degrees=(0, 180)),
            # # Random color jitter with brightness, contrast, saturation and hue changes
            # v2.ColorJitter(
            #     brightness=0.2,
            #     contrast=0.2,
            #     saturation=0.2,
            #     hue=0.1
            # ),
            # v2.RandomGrayscale(p=0.072),
            # v2.RandomInvert(p=0.072),
            # Convert to float and normalize to [0, 1]
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
        fdir=DATA_DIR,  # type: ignore
        subset=Subset.TRAINING,
        transform=train_transform,
    )
    val_dataset = CIFAR10Dataset(
        fdir=DATA_DIR,  # type: ignore
        subset=Subset.VALIDATION,
        transform=val_transform,
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # Use pretrained resnet18 as a backbone
    net = resnet18()

    # Add a fully connected layer to output the correct number of classes for CIFAR-10 (10 classes)
    net.fc = DropoutLinear(
        net.fc.in_features,
        train_dataset.num_classes(),
        args.dropout,
    )

    # Add dropout to the model
    net = add_dropout(net, args.dropout)

    model = DeepClassifier(net=net)

    train_loader = DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=True, num_workers=2  # type: ignore
    )
    val_loader = DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False, num_workers=2  # type: ignore
    )

    model.to(device)

    # TO RUN
    # optimizer = torch.optim.SGD(model.parameters(), lr=args.lr)
    # optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    # optimizer = torch.optim.AdamW(
    #     model.parameters(),
    #     lr=args.lr,
    #     # weight_decay=args.weight_decay,
    # )
    optimizer = torch.optim.NAdam(model.parameters(), lr=args.lr)

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
    parser.add_argument("--num_epochs", type=int, default=31)
    parser.add_argument("--batch_size", type=int, default=273)
    parser.add_argument("--lr", type=float, default=0.0027)
    parser.add_argument("--val_frequency", type=int, default=5)
    parser.add_argument("--weight_decay", type=float, default=1e-4)
    parser.add_argument("--dropout", type=float, default=0.2)

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
