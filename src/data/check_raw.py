"""检查原始数据集目录结构与数量分布。

用法:
    python src/data/check_raw.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

RAW_DIR = Path("data/raw/chest_xray")
SPLITS = ["train", "val", "test"]
CLASSES = ["NORMAL", "PNEUMONIA"]
IMG_EXTS = {".jpeg", ".jpg", ".png", ".bmp", ".tif", ".tiff"}


def main() -> int:
    if not RAW_DIR.exists():
        print(f"[ERR] 找不到 {RAW_DIR.resolve()}")
        print("请先把 chest_xray 整个文件夹放到 data/raw/ 下")
        return 1

    print(f"数据根目录: {RAW_DIR.resolve()}\n")
    print("=== 原始数据集分布（官方划分） ===")

    total = 0
    merged: Counter[str] = Counter()

    for s in SPLITS:
        split_dir = RAW_DIR / s
        row = []
        if not split_dir.exists():
            print(f"[{s}] 文件夹不存在")
            continue
        for c in CLASSES:
            class_dir = split_dir / c
            if not class_dir.exists():
                row.append(f"{c}=0(缺失)")
                continue
            n = sum(1 for f in class_dir.iterdir() if f.is_file() and f.suffix.lower() in IMG_EXTS)
            merged[c] += n
            total += n
            row.append(f"{c}={n}")
        print(f"[{s}] " + "  ".join(row))

    print("\n=== 合并后分布（train+val+test） ===")
    for c in CLASSES:
        print(f"  {c}: {merged[c]}")
    print(f"  总计: {sum(merged.values())} 张")

    if merged:
        n, p = merged["NORMAL"], merged["PNEUMONIA"]
        if n:
            print(f"\n类别比例 NORMAL:PNEUMONIA = 1 : {p / n:.2f}")

    # 检查非图像文件
    print("\n=== 其他文件（非图像，如 .DS_Store） ===")
    others = []
    for s in SPLITS:
        split_dir = RAW_DIR / s
        if not split_dir.exists():
            continue
        for f in split_dir.rglob("*"):
            if f.is_file() and f.suffix.lower() not in IMG_EXTS:
                others.append(f.relative_to(RAW_DIR))
    for f in others[:20]:
        print(f"  {f}")
    if len(others) > 20:
        print(f"  ... 共 {len(others)} 个")
    if not others:
        print("  无")

    return 0


if __name__ == "__main__":
    sys.exit(main())
