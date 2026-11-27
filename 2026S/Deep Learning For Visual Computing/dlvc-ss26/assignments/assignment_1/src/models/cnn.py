from pathlib import Path
import torch
import torch.nn as nn
import torch.nn.functional as F


class AttentionBlock(nn.Module):
    """
    Three-way attention block converted from TF (NHWC) to PyTorch (NCHW).

    Mirrors the original TF AttentionBlock:
        + Spatial  attention: mean over channels -> MHA on (B, H, W) -> sigmoid spatial mask
        + Row      attention: mean over W        -> MHA on (B, C, H) -> sigmoid height mask
        + Column   attention: mean over H        -> MHA on (B, C, W) -> sigmoid width  mask
    The three masked feature maps are averaged and returned.
    """

    def __init__(self, channels: int, height: int, width: int):
        super().__init__()

        def valid_heads(dim: int) -> int:
            for n in [4, 2, 1]:
                if dim % n == 0:
                    return n
            return 1

        # Spatial attention: seq_len=H, embed_dim=W
        self.spatial_attn = nn.MultiheadAttention(
            embed_dim=width,
            num_heads=valid_heads(width),
            batch_first=True,
        )
        # Row attention: seq_len=C, embed_dim=H
        self.row_attn = nn.MultiheadAttention(
            embed_dim=height,
            num_heads=valid_heads(height),
            batch_first=True,
        )
        # Col attention: seq_len=C, embed_dim=W
        self.col_attn = nn.MultiheadAttention(
            embed_dim=width,
            num_heads=valid_heads(width),
            batch_first=True,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, C, H, W)

        # Spatial attention (C-averaged)
        tl1 = x.mean(dim=1)                            # (B, H, W)
        tl1, _ = self.spatial_attn(tl1, tl1, tl1)      # (B, H, W)
        tl1 = torch.sigmoid(tl1).unsqueeze(1)          # (B, 1, H, W)
        tl1 = x * tl1                                  # (B, C, H, W)

        # Row attention (W-averaged)
        tl2 = x.mean(dim=3)                            # (B, C, H)
        tl2, _ = self.row_attn(tl2, tl2, tl2)          # (B, C, H)
        tl2 = torch.sigmoid(tl2).unsqueeze(3)          # (B, C, H, 1)
        tl2 = x * tl2                                  # (B, C, H, W)

        # Column attention (H-averaged)
        tl3 = x.mean(dim=2)                            # (B, C, W)
        tl3, _ = self.col_attn(tl3, tl3, tl3)          # (B, C, W)
        tl3 = torch.sigmoid(tl3).unsqueeze(2)          # (B, C, 1, W)
        tl3 = x * tl3                                  # (B, C, H, W)

        return (tl1 + tl2 + tl3) / 3.0


class ResidualBlock(nn.Module):
    """
    Residual block with two parallel conv branches (3x3 and 2x2) fused by
    summation, followed by a 3x3 conv, an AttentionBlock, and a skip connection.

    The 2x2 branch uses asymmetric zero-padding (pad right/bottom by 1) so
    that its output matches the 3x3 branch spatial size — equivalent to
    TF Conv2D(padding='same') with kernel_size=2.
    """

    def __init__(self, channels: int, height: int, width: int):
        super().__init__()

        # Branch 1: 3x3, same padding
        self.branch1 = nn.Sequential(
            nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.LeakyReLU(inplace=True),
        )

        # Branch 2: 2x2, asymmetric pad to keep spatial size (TF padding='same')
        self.branch2 = nn.Sequential(
            nn.ZeroPad2d((0, 1, 0, 1)),                      # pad right=1, bottom=1
            nn.Conv2d(channels, channels, kernel_size=2, padding=0, bias=False),
            nn.BatchNorm2d(channels),
            nn.LeakyReLU(inplace=True),
        )

        # Fusion conv after element-wise sum
        self.fuse = nn.Sequential(
            nn.Conv2d(channels, channels, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(channels),
            nn.LeakyReLU(inplace=True),
        )

        self.attn = AttentionBlock(channels, height, width)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        fused = self.fuse(self.branch1(x) + self.branch2(x))
        fused = self.attn(fused)
        return fused + x


class YourCNN(nn.Module):
    """
    PyTorch CNN for CIFAR-10 classification (input: Bx3x32x32, output: Bx10).

    Architecture (encoder-only, adapted from the TF Residual Attention U-Net):
      Stem  → ResBlock → downsample (32→16)
            → ResBlock → downsample (16→8)
            → ResBlock → downsample (8→4)
            → ResBlock (bottom)
            → GlobalAvgPool → Dropout → Linear(10)

    Each ResBlock contains two parallel convolutions (3x3 and 2x2), a fused
    3x3 conv, an AttentionBlock (channel / row / column attention via MHA),
    and a skip connection.
    """

    def __init__(self, num_classes: int = 10, filters: int = 72, dropout: float = 0.2):
        super().__init__()

        # --- Stem ---
        self.stem = nn.Sequential(
            nn.Conv2d(3, filters, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(filters),
            nn.LeakyReLU(inplace=True),
        )

        # --- Encoder stages (spatial sizes for CIFAR-10: 32→16→8→4) ---
        self.res1  = ResidualBlock(filters, 32, 32)
        self.down1 = nn.Conv2d(filters, filters, kernel_size=2, stride=2)   # 32→16

        self.res2  = ResidualBlock(filters, 16, 16)
        self.down2 = nn.Conv2d(filters, filters, kernel_size=2, stride=2)   # 16→8

        self.res3  = ResidualBlock(filters, 8, 8)
        self.down3 = nn.Conv2d(filters, filters, kernel_size=2, stride=2)   # 8→4

        # --- Bottom ---
        self.bottom = ResidualBlock(filters, 4, 4)

        # --- Classifier head ---
        self.pool       = nn.AdaptiveAvgPool2d(1)
        self.dropout    = nn.Dropout(dropout)
        self.classifier = nn.Linear(filters, num_classes)

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode="fan_out", nonlinearity="leaky_relu")
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.ones_(m.weight)
                nn.init.zeros_(m.bias)
            elif isinstance(m, nn.Linear):
                nn.init.xavier_uniform_(m.weight)
                nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.stem(x)                   # (B, 72, 32, 32)

        x = self.res1(x)                   # (B, 72, 32, 32)
        x = F.selu(self.down1(x))          # (B, 72, 16, 16)

        x = self.res2(x)                   # (B, 72, 16, 16)
        x = F.selu(self.down2(x))          # (B, 72,  8,  8)

        x = self.res3(x)                   # (B, 72,  8,  8)
        x = F.selu(self.down3(x))          # (B, 72,  4,  4)

        x = self.bottom(x)                 # (B, 72,  4,  4)

        x = self.pool(x).flatten(1)        # (B, 72)
        x = self.dropout(x)
        x = self.classifier(x)             # (B, 10)

        return x


if __name__ == "__main__":
    model = YourCNN()
    print(f"Number of trainable parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad)}")

    # Test random input through the model
    x = torch.randn(8, 3, 32, 32)  # (B, C, H, W)
    out = model(x)
    print(f"Output shape: {out.shape}")  # Should be (B, num_classes)
