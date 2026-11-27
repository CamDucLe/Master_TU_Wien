
import argparse
import os
import torch
import torchvision.transforms.v2 as v2
from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import ExponentialLR, StepLR
from pathlib import Path
from torchvision.models import ResNet50_Weights
from torchvision.models.segmentation import fcn_resnet50

from assignment_2_code.models.segment_model import DeepSegmenter
from assignment_2_code.dataset.oxfordpets import OxfordPetsCustom
from assignment_2_code.metrics import SegMetrics
from assignment_2_code.trainer import ImgSemSegTrainer
from config import OXFORD_PETS_DIR, MODEL_SAVE_DIR, LOG_DIR


def train(args):

    train_transform = v2.Compose([v2.ToImage(),
                                  v2.ToDtype(torch.float32, scale=True),
                                  v2.Resize(size=(64, 64), interpolation=v2.InterpolationMode.NEAREST),
                                  v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])
    train_transform2 = v2.Compose([v2.ToImage(),
                                   v2.ToDtype(torch.long, scale=False),
                                   v2.Resize(size=(64, 64), interpolation=v2.InterpolationMode.NEAREST)])  # ,

    val_transform = v2.Compose([v2.ToImage(),
                                v2.ToDtype(torch.float32, scale=True),
                                v2.Resize(size=(64, 64), interpolation=v2.InterpolationMode.NEAREST),
                                v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])])
    val_transform2 = v2.Compose([v2.ToImage(),
                                 v2.ToDtype(torch.long, scale=False),
                                 v2.Resize(size=(64, 64), interpolation=v2.InterpolationMode.NEAREST)])

    train_data = OxfordPetsCustom(root=str(OXFORD_PETS_DIR),
                                  split="trainval",
                                  target_types='segmentation',
                                  transform=train_transform,
                                  target_transform=train_transform2,
                                  download=True)

    val_data = OxfordPetsCustom(root=str(OXFORD_PETS_DIR),
                                split="test",
                                target_types='segmentation',
                                transform=val_transform,
                                target_transform=val_transform2,
                                download=True)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    if args.backbone_init == "pretrained":
        weights_backbone = ResNet50_Weights.IMAGENET1K_V1
    else:
        weights_backbone = None

    network = fcn_resnet50(
        weights=None,
        weights_backbone=weights_backbone,
        num_classes=len(train_data.classes_seg),
        aux_loss=False,
    )
    model = DeepSegmenter(network).to(device)

    optimizer = AdamW(model.parameters(), lr=args.learning_rate, amsgrad=True)
    loss_fn = nn.CrossEntropyLoss()

    train_metric = SegMetrics(classes=train_data.classes_seg)
    val_metric = SegMetrics(classes=val_data.classes_seg)
    val_frequency = 2

    save_dir = MODEL_SAVE_DIR / f"fcn_resnet50_{args.backbone_init}"
    save_dir.mkdir(parents=True, exist_ok=True)

    lr_scheduler = ExponentialLR(optimizer, gamma=0.98)

    trainer = ImgSemSegTrainer(model,
                               optimizer,
                               loss_fn,
                               lr_scheduler,
                               train_metric,
                               val_metric,
                               train_data,
                               val_data,
                               device,
                               args.num_epochs,
                               save_dir,
                               batch_size=args.batch_size,
                               val_frequency=val_frequency)
    trainer.train()

    # see Reference implementation of ImgSemSegTrainer
    # just comment if not used
    # trainer.dispose()


if __name__ == "__main__":
    args = argparse.ArgumentParser(description='Training')
    args.add_argument('-d', '--gpu_id', default='0', type=str,
                      help='index of which GPU to use')
    args.add_argument('--num-epochs', default=31, type=int)
    args.add_argument('--batch-size', default=4, type=int)
    args.add_argument('--learning-rate', default=1e-3, type=float)
    args.add_argument('--backbone-init', default='pretrained', type=str, choices=('scratch', 'pretrained'))

    if not isinstance(args, tuple):
        args = args.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = str(args.gpu_id)  # type: ignore
    args.gpu_id = 0  # type: ignore

    train(args)
