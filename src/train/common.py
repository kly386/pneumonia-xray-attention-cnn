"""训练公共组件：随机种子 / 设备 / 数据加载 / 类别权重。

数据约定（详见 data/README.md）：
    - 训练集实问增强：data/processed/train（增强由 transforms 实时完成，不落盘）
    - val / test 只做确定性变换，不允许随机增强
    - 类别编码：NORMAL=0，PNEUMONIA=1（ImageFolder 按文件夹名排序）
    - 类别不平衡 1:2.69，交叉熵类别权重 [1.8444, 0.6860]

用法（conda pytorch 环境，仓库根目录下运行）:
    C:\\Users\\29542\\.conda\\envs\\pytorch\\python.exe -m src.train.common
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

# ---------------------------------------------------------------- 常量（与数据组对齐，勿改）
SEED = 1234
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "processed"
CKPT_DIR = REPO_ROOT / "models" / "checkpoints"
REPORT_DIR = REPO_ROOT / "reports"
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

CLASSES = ["NORMAL", "PNEUMONIA"]
NUM_CLASSES = len(CLASSES)

# 样本数反比权重（由 src/data/verify_loader.py 计算：1263 / 3396）
CLASS_WEIGHTS = torch.tensor([1.8444, 0.6860])

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
IMG_SIZE = 224

# ---------------------------------------------------------------- 预处理（与 data/README.md 完全一致）
train_tf = transforms.Compose([
    transforms.Grayscale(num_output_channels=3),    # 灰度 -> 三通道
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.RandomHorizontalFlip(p=0.5),         # ↓ 以下仅训练集
    transforms.RandomRotation(10),
    transforms.RandomResizedCrop(IMG_SIZE, scale=(0.85, 1.0)),
    transforms.ColorJitter(brightness=0.1, contrast=0.1),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])

# val / test：确定性变换，无随机增强
eval_tf = transforms.Compose([
    transforms.Grayscale(num_output_channels=3),
    transforms.Resize((IMG_SIZE, IMG_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])


def set_seed(seed: int = SEED) -> None:
    """固定所有随机源，保证实验可复现（与数据划分 seed=1234 同源）。"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def build_loaders(batch_size: int = 32, num_workers: int = 2) -> tuple[DataLoader, DataLoader, DataLoader]:
    """构建 train / val / test 三个 DataLoader。"""
    train_ds = datasets.ImageFolder(DATA_DIR / "train", transform=train_tf)
    val_ds = datasets.ImageFolder(DATA_DIR / "val", transform=eval_tf)
    test_ds = datasets.ImageFolder(DATA_DIR / "test", transform=eval_tf)

    common = dict(
        batch_size=batch_size,
        num_workers=num_workers,
        pin_memory=True,
    )
    train_loader = DataLoader(train_ds, shuffle=True, drop_last=False, **common)
    val_loader = DataLoader(val_ds, shuffle=False, **common)
    test_loader = DataLoader(test_ds, shuffle=False, **common)
    return train_loader, val_loader, test_loader


def make_loss() -> nn.CrossEntropyLoss:
    """带类别权重的交叉熵（医学场景漏诊代价高，PNEUMONIA 权重低但整体平衡）。"""
    return nn.CrossEntropyLoss(weight=CLASS_WEIGHTS.to(DEVICE), label_smoothing=0.05)


if __name__ == "__main__":
    set_seed()
    tr, va, te = build_loaders(batch_size=16, num_workers=0)
    print(f"device        : {DEVICE}")
    print(f"train batches : {len(tr)}  (n={len(tr.dataset)})")
    print(f"val batches   : {len(va)}  (n={len(va.dataset)})")
    print(f"test batches  : {len(te)}  (n={len(te.dataset)})")
    imgs, labels = next(iter(tr))
    print(f"batch shape   : {tuple(imgs.shape)}  labels={labels.tolist()}")
