"""生成样本预览图，用于报告与答辩 PPT。

输出: reports/figures/samples.png

用法:
    python src/data/make_samples.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

MANIFEST = Path("data/splits/split_manifest.csv")
OUT = Path("reports/figures/samples.png")
CLASSES = ["NORMAL", "PNEUMONIA"]
PER_CLASS = 4


def main() -> int:
    import csv

    if not MANIFEST.exists():
        print(f"[ERR] 找不到 {MANIFEST}")
        return 1

    by_class: dict[str, list[str]] = {c: [] for c in CLASSES}
    with open(MANIFEST, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["split"] == "train":
                by_class[row["label"]].append(row["filepath"])

    fig, axes = plt.subplots(len(CLASSES), PER_CLASS, figsize=(PER_CLASS * 2.6, len(CLASSES) * 2.9))
    for i, c in enumerate(CLASSES):
        files = by_class[c][:PER_CLASS]
        for j in range(PER_CLASS):
            ax = axes[i][j]
            if j < len(files):
                with Image.open(files[j]) as im:
                    ax.imshow(im.convert("L"), cmap="gray")
                ax.set_title(c, fontsize=11)
            ax.axis("off")
    fig.suptitle("Sample chest X-ray images (train split)", fontsize=13)
    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"已生成: {OUT.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
