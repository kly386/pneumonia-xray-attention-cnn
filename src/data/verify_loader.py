"""数据管道冒烟测试：验证 processed 数据能被 DataLoader 正常加载。

用法:
    python src/data/verify_loader.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

ROOT = Path("data/processed")

eval_tf = transforms.Compose([
    transforms.Grayscale(num_output_channels=3),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def main() -> int:
    for s in ["train", "val", "test"]:
        if not (ROOT / s).exists():
            print(f"[ERR] 缺少 {ROOT / s}，请先运行 make_split.py")
            return 1

    train_ds = datasets.ImageFolder(ROOT / "train", transform=eval_tf)
    val_ds = datasets.ImageFolder(ROOT / "val", transform=eval_tf)
    test_ds = datasets.ImageFolder(ROOT / "test", transform=eval_tf)

    print("=== ImageFolder 加载结果 ===")
    for name, ds in [("train", train_ds), ("val", val_ds), ("test", test_ds)]:
        print(f"  {name:<5}: {len(ds):>4} 张，classes={ds.classes}")

    print(f"\n类别编码: {train_ds.class_to_idx}")

    dl = DataLoader(train_ds, batch_size=8, shuffle=True, num_workers=0)
    x, y = next(iter(dl))
    print(f"\n=== batch 检查 ===")
    print(f"  images: shape={tuple(x.shape)}, dtype={x.dtype}")
    print(f"  labels: {y.tolist()}")
    print(f"  pixel range: min={x.min():.3f}, max={x.max():.3f}")
    print(f"  mean={x.mean():.3f}, std={x.std():.3f}")

    # 类别权重建议
    import collections
    counts = collections.Counter(train_ds.targets)
    print("\n=== 训练集类别权重建议 ===")
    total = len(train_ds)
    w = [total / (len(counts) * counts[i]) for i in sorted(counts)]
    for i, c in enumerate(train_ds.classes):
        print(f"  {c:<10}: {counts[i]:>4} 张 -> weight={w[i]:.4f}")
    print(f"  weight 张量: torch.tensor([{w[0]:.4f}, {w[1]:.4f}])")

    print("\n数据管道正常 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
