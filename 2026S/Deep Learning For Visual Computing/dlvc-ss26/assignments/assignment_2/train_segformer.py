
import argparse
import os
import torch
import torchvision.transforms.v2 as v2
from pathlib import Path
from torch import nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import ExponentialLR

from assignment_2_code.models.segformer import SegFormer
from assignment_2_code.models.segment_model import DeepSegmenter
from assignment_2_code.dataset.cityscapes import CityscapesCustom
from assignment_2_code.dataset.oxfordpets import OxfordPetsCustom
from assignment_2_code.metrics import SegMetrics
from assignment_2_code.trainer import ImgSemSegTrainer
from config import OXFORD_PETS_DIR, CITYSCAPES_DIR, MODEL_SAVE_DIR


def build_transforms(image_size: int):
    image_transform = v2.Compose([
        v2.ToImage(),
        v2.ToDtype(torch.float32, scale=True),
        v2.Resize(size=(image_size, image_size), interpolation=v2.InterpolationMode.NEAREST),
        v2.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    mask_transform = v2.Compose([
        v2.ToImage(),
        v2.ToDtype(torch.long, scale=False),
        v2.Resize(size=(image_size, image_size), interpolation=v2.InterpolationMode.NEAREST),
    ])

    return image_transform, mask_transform


def build_datasets(args):
    image_transform, mask_transform = build_transforms(args.image_size)

    if args.dataset == "oxford":
        train_data = OxfordPetsCustom(
            root=str(OXFORD_PETS_DIR),
            split="trainval",
            target_types="segmentation",
            transform=image_transform,
            target_transform=mask_transform,
            download=True,
        )
        val_data = OxfordPetsCustom(
            root=str(OXFORD_PETS_DIR),
            split="test",
            target_types="segmentation",
            transform=image_transform,
            target_transform=mask_transform,
            download=True,
        )
    else:
        train_data = CityscapesCustom(
            root=str(CITYSCAPES_DIR),
            split="train",
            mode="fine",
            target_type="semantic",
            transform=image_transform,
            target_transform=mask_transform,
        )
        val_data = CityscapesCustom(
            root=str(CITYSCAPES_DIR),
            split="val",
            mode="fine",
            target_type="semantic",
            transform=image_transform,
            target_transform=mask_transform,
        )

    return train_data, val_data


def load_encoder_from_checkpoint(model: SegFormer, checkpoint_path: Path):
    state_dict = torch.load(checkpoint_path, map_location="cpu")
    encoder_state_dict = {}

    for key, value in state_dict.items():
        if key.startswith("encoder."):
            encoder_state_dict[key[len("encoder."):]] = value
        elif key.startswith("net.encoder."):
            encoder_state_dict[key[len("net.encoder."):]] = value

    if not encoder_state_dict:
        encoder_state_dict = state_dict

    missing_keys, unexpected_keys = model.encoder.load_state_dict(encoder_state_dict, strict=False)
    if unexpected_keys:
        raise ValueError(f"Unexpected encoder keys in checkpoint {checkpoint_path}: {unexpected_keys}")

    print(f"Loaded encoder weights from {checkpoint_path}")
    if missing_keys:
        print(f"Missing encoder keys left at initialization: {missing_keys}")


def build_save_dir(args):
    if args.run_name is not None:
        run_name = args.run_name
    elif args.dataset == "city":
        run_name = "segformer_city_pretrain"
    elif args.freeze_encoder:
        run_name = "segformer_oxford_finetune_frozen"
    elif args.encoder_checkpoint is not None:
        run_name = "segformer_oxford_finetune_init"
    else:
        run_name = "segformer_oxford_scratch"

    save_dir = MODEL_SAVE_DIR / run_name
    save_dir.mkdir(parents=True, exist_ok=True)
    return save_dir


def validate_args(args):
    if args.freeze_encoder and args.encoder_checkpoint is None:
        raise ValueError("--freeze-encoder requires --encoder-checkpoint.")

    if args.dataset == "city" and args.encoder_checkpoint is not None:
        raise ValueError("Encoder checkpoint loading is only supported for Oxford fine-tuning.")


def train(args):
    validate_args(args)
    train_data, val_data = build_datasets(args)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    segformer = SegFormer(num_classes=len(train_data.classes_seg))
    model = DeepSegmenter(segformer)
    if args.encoder_checkpoint is not None:
        load_encoder_from_checkpoint(segformer, Path(args.encoder_checkpoint))

    if args.freeze_encoder:
        segformer.encoder.requires_grad_(False)

    model.to(device)

    optimizer_params = model.parameters()
    if args.freeze_encoder:
        optimizer_params = segformer.decoder.parameters()

    optimizer = AdamW(optimizer_params, lr=args.learning_rate, amsgrad=True)
    loss_fn = nn.CrossEntropyLoss(ignore_index=255 if args.dataset == "city" else -100)

    train_metric = SegMetrics(classes=train_data.classes_seg)
    val_metric = SegMetrics(classes=val_data.classes_seg)

    save_dir = build_save_dir(args)

    lr_scheduler = ExponentialLR(optimizer, gamma=args.lr_gamma)

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
                               val_frequency=args.val_frequency,
                               train_num_workers=args.train_num_workers,
                               val_num_workers=args.val_num_workers)
    trainer.train()
    # see Reference implementation of ImgSemSegTrainer
    # just comment if not used


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Training SegFormer')
    parser.add_argument('-d', '--gpu_id', default='0', type=str,
                        help='index of which GPU to use')
    parser.add_argument('--num-epochs', default=31, type=int)
    parser.add_argument('--batch-size', default=64, type=int)
    parser.add_argument('--learning-rate', default=1e-3, type=float)
    parser.add_argument('--dataset', default='oxford', choices=('oxford', 'city'))
    parser.add_argument('--encoder-checkpoint', default=None, type=str)
    parser.add_argument('--freeze-encoder', action='store_true')
    parser.add_argument('--run-name', default=None, type=str)
    parser.add_argument('--image-size', default=64, type=int)
    parser.add_argument('--val-frequency', default=2, type=int)
    parser.add_argument('--lr-gamma', default=0.98, type=float)
    parser.add_argument('--train-num-workers', default=0, type=int)
    parser.add_argument('--val-num-workers', default=0, type=int)

    args = parser.parse_args()
    os.environ['CUDA_VISIBLE_DEVICES'] = str(args.gpu_id)

    train(args)
