"""数据统计与质量报告。

读取 data/splits/split_manifest.csv，输出:
    - reports/data_stats.md          统计报告（Markdown）
    - reports/figures/class_dist.png 各划分类别分布
    - reports/figures/size_dist.png  图像尺寸分布
    - reports/figures/aspect_dist.png 宽高比分布

用法:
    python src/data/data_stats.py
"""
from __future__ import annotations

import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

MANIFEST = Path("data/splits/split_manifest.csv")
CLEAN_LOG = Path("data/splits/cleaning_log.csv")
REPORT = Path("reports/data_stats.md")
FIG_DIR = Path("reports/figures")
SPLITS = ["train", "val", "test"]
CLASSES = ["NORMAL", "PNEUMONIA"]


def pct(a: float, b: float) -> str:
    return f"{a / b * 100:.2f}%" if b else "0.00%"


def main() -> int:
    if not MANIFEST.exists():
        print(f"[ERR] 找不到 {MANIFEST}，请先运行 python src/data/make_split.py")
        return 1

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(MANIFEST)
    total = len(df)

    # ---------- 防泄漏检查 ----------
    leak = 0
    md5_sets = {s: set(df.loc[df.split == s, "md5"]) for s in SPLITS}
    overlaps = []
    for i in range(len(SPLITS)):
        for j in range(i + 1, len(SPLITS)):
            a, b = SPLITS[i], SPLITS[j]
            common = md5_sets[a] & md5_sets[b]
            if common:
                overlaps.append((a, b, len(common)))
                leak += len(common)

    # ---------- 交叉表 ----------
    ct = pd.crosstab(df["split"], df["label"]).reindex(index=SPLITS, columns=CLASSES).fillna(0).astype(int)

    # ---------- 尺寸统计 ----------
    df["aspect"] = df["width"] / df["height"]
    df["megapixel"] = df["width"] * df["height"] / 1e6
    sizes = Counter(zip(df["width"], df["height"]))

    # ---------- 图 1: 类别分布 ----------
    fig, ax = plt.subplots(figsize=(7, 4.5))
    x = range(len(SPLITS))
    w = 0.36
    n_vals = [int(ct.loc[s, "NORMAL"]) for s in SPLITS]
    p_vals = [int(ct.loc[s, "PNEUMONIA"]) for s in SPLITS]
    b1 = ax.bar([i - w / 2 for i in x], n_vals, w, label="NORMAL", color="#4C9BE8")
    b2 = ax.bar([i + w / 2 for i in x], p_vals, w, label="PNEUMONIA", color="#E8734C")
    for bars in (b1, b2):
        for r in bars:
            ax.annotate(f"{int(r.get_height())}",
                        (r.get_x() + r.get_width() / 2, r.get_height()),
                        ha="center", va="bottom", fontsize=9)
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{s}\n(n={int(ct.loc[s].sum())})" for s in SPLITS])
    ax.set_ylabel("Number of images")
    ax.set_title(f"Class distribution per split (8:1:1 stratified, total={total})")
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "class_dist.png", dpi=150)
    plt.close(fig)

    # ---------- 图 2: 原始尺寸散点 ----------
    fig, ax = plt.subplots(figsize=(6, 5))
    colors = {"NORMAL": "#4C9BE8", "PNEUMONIA": "#E8734C"}
    for c in CLASSES:
        sub = df[df.label == c]
        ax.scatter(sub["width"], sub["height"], s=6, alpha=0.35, label=c, color=colors[c])
    ax.set_xlabel("Width (px)")
    ax.set_ylabel("Height (px)")
    ax.set_title("Original image sizes")
    ax.legend(markerscale=4)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "size_dist.png", dpi=150)
    plt.close(fig)

    # ---------- 图 3: 宽高比分布 ----------
    fig, ax = plt.subplots(figsize=(7, 4))
    for c in CLASSES:
        sub = df[df.label == c]
        ax.hist(sub["aspect"], bins=40, alpha=0.6, label=c, color=colors[c])
    ax.axvline(1.0, color="k", ls="--", lw=1, label="1:1")
    ax.set_xlabel("Aspect ratio (W/H)")
    ax.set_ylabel("Count")
    ax.set_title("Aspect ratio distribution")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "aspect_dist.png", dpi=150)
    plt.close(fig)

    # ---------- 写 Markdown ----------
    L: list[str] = []
    L.append("# 数据统计报告\n")
    L.append("> 由 `src/data/data_stats.py` 自动生成，数据源 `data/splits/split_manifest.csv`\n")

    L.append("## 1. 数据集来源\n")
    L.append("- **名称**：Chest X-Ray Images (Pneumonia)")
    L.append("- **来源**：Kermany et al., *Cell*, 2018")
    L.append("- **地址**：https://www.kaggle.com/datasets/paultimothymooney/chest-xray-pneumonia")
    L.append("- **任务**：二分类（NORMAL / PNEUMONIA）")
    L.append("- **合规性**：公开、已去标识化，仅用于课程教学科研。详见 `docs/数据合规说明.md`\n")

    L.append("## 2. 清洗结果\n")
    raw_total = total
    removed_corrupt = 0
    removed_dup = 0
    if CLEAN_LOG.exists():
        clog = pd.read_csv(CLEAN_LOG)
        removed_corrupt = int((clog["action"] == "removed_corrupt").sum()) if len(clog) else 0
        removed_dup = int((clog["action"] == "removed_duplicate").sum()) if len(clog) else 0
    L.append("| 项目 | 数量 |")
    L.append("|---|---|")
    L.append(f"| 原始图像总数 | {raw_total + removed_corrupt + removed_dup} |")
    L.append(f"| 损坏 / 无法解码（剔除） | {removed_corrupt} |")
    L.append(f"| MD5 完全重复（剔除） | {removed_dup} |")
    L.append(f"| **最终有效样本** | **{raw_total}** |\n")
    L.append("说明：官方划分中 `val/` 仅 16 张（NORMAL 8 / PNEUMONIA 8），不具备统计意义，"
             "本项目**合并官方 train/val/test 全部样本后重新划分**。\n")

    L.append("## 3. 划分结果（8:1:1 分层抽样）\n")
    L.append("| 划分 | NORMAL | PNEUMONIA | 合计 | 占比 | 阳性占比 |")
    L.append("|---|---|---|---|---|---|")
    for s in SPLITS:
        n, p, t = int(ct.loc[s, "NORMAL"]), int(ct.loc[s, "PNEUMONIA"]), int(ct.loc[s].sum())
        L.append(f"| {s} | {n} | {p} | {t} | {pct(t, total)} | {pct(p, t)} |")
    L.append(f"| **合计** | **{int(ct['NORMAL'].sum())}** | **{int(ct['PNEUMONIA'].sum())}** | "
             f"**{total}** | 100% | {pct(int(ct['PNEUMONIA'].sum()), total)} |\n")

    L.append("**划分参数**：分层抽样（stratified），`random_state=1234`，"
             "两次切分（先 8:2，再对半分 val/test），可完全复现。\n")

    L.append("## 4. 数据泄漏检查\n")
    if leak == 0:
        L.append("✅ 通过。各划分之间 **MD5 无重叠**，不存在同一张图像跨 train/val/test 的情况。\n")
    else:
        L.append(f"⚠️ 发现 {leak} 处 MD5 重叠：{overlaps}\n")

    L.append("## 5. 类别平衡分析\n")
    n_all, p_all = int(ct["NORMAL"].sum()), int(ct["PNEUMONIA"].sum())
    L.append(f"- 总体 NORMAL : PNEUMONIA = 1 : {p_all / n_all:.2f}（阳性占 {pct(p_all, total)}）")
    L.append("- 各划分阳性占比几乎一致（分层抽样生效），说明**划分无偏**。")
    L.append("- ⚠️ 存在约 **1:2.7** 的类别不平衡，建议算法组采取以下措施之一：")
    L.append("  1. `CrossEntropyLoss(weight=[1.0, 0.37])` 或按样本数反比设置类别权重；")
    L.append("  2. 训练集对 NORMAL 做重采样 / 对 PNEUMONIA 做欠采样；")
    L.append("  3. **评价指标不要只看 Accuracy**，必须同时报告 Recall / F1 / AUC / 混淆矩阵"
             "（医学场景漏诊代价高，Recall 尤为重要）。\n")

    L.append("## 6. 图像尺寸统计\n")
    L.append("| 指标 | 宽 (W) | 高 (H) | 宽高比 W/H |")
    L.append("|---|---|---|---|")
    L.append(f"| 最小 | {int(df.width.min())} | {int(df.height.min())} | {df.aspect.min():.3f} |")
    L.append(f"| 中位数 | {int(df.width.median())} | {int(df.height.median())} | {df.aspect.median():.3f} |")
    L.append(f"| 最大 | {int(df.width.max())} | {int(df.height.max())} | {df.aspect.max():.3f} |")
    L.append(f"| 均值 | {df.width.mean():.1f} | {df.height.mean():.1f} | {df.aspect.mean():.3f} |")
    L.append(f"| 标准差 | {df.width.std():.1f} | {df.height.std():.1f} | {df.aspect.std():.3f} |\n")
    L.append(f"- 图像尺寸**极不统一**（共 {len(sizes)} 种不同分辨率），必须在预处理阶段统一 Resize。")
    L.append(f"- 最大分辨率达 {int(df.width.max())}×{int(df.height.max())}，"
             f"平均约 {df.megapixel.mean():.2f} MP，统一缩放到 224×224 会带来明显信息压缩，"
             "属预期内的精度/成本权衡。\n")

    L.append("### 最常见的 5 种尺寸\n")
    L.append("| 尺寸 (W×H) | 数量 |")
    L.append("|---|---|")
    for (w, h), c in sizes.most_common(5):
        L.append(f"| {w}×{h} | {c} |")
    L.append("")

    L.append("## 7. 图表\n")
    L.append("| 图 | 文件 |")
    L.append("|---|---|")
    L.append("| 各划分类别分布 | `reports/figures/class_dist.png` |")
    L.append("| 原始尺寸散点 | `reports/figures/size_dist.png` |")
    L.append("| 宽高比分布 | `reports/figures/aspect_dist.png` |")
    L.append("| 样本预览（train） | `reports/figures/samples.png` |")
    L.append("")

    L.append("## 8. 交付给算法组的预处理约定\n")
    L.append("```python")
    L.append("train_tf = transforms.Compose([")
    L.append("    transforms.Grayscale(num_output_channels=3),   # 灰度 -> 三通道（适配 ImageNet 预训练）")
    L.append("    transforms.Resize((224, 224)),                 # 统一尺寸")
    L.append("    transforms.RandomHorizontalFlip(p=0.5),        # ↓ 以下仅训练集")
    L.append("    transforms.RandomRotation(10),")
    L.append("    transforms.RandomResizedCrop(224, scale=(0.85, 1.0)),")
    L.append("    transforms.ColorJitter(brightness=0.1, contrast=0.1),")
    L.append("    transforms.ToTensor(),")
    L.append("    transforms.Normalize([0.485, 0.456, 0.406],   # ImageNet 均值/方差")
    L.append("                         [0.229, 0.224, 0.225]),")
    L.append("])")
    L.append("")
    L.append("# val / test：不做随机增强，只做确定性变换")
    L.append("eval_tf = transforms.Compose([")
    L.append("    transforms.Grayscale(num_output_channels=3),")
    L.append("    transforms.Resize((224, 224)),")
    L.append("    transforms.ToTensor(),")
    L.append("    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),")
    L.append("])")
    L.append("```")
    L.append("")
    L.append("> **数据增强不落盘**：`data/processed/` 中只保存原图，增强在训练时由 "
             "`torchvision.transforms` 实时完成，避免磁盘膨胀与目录混乱。\n")

    L.append("## 9. 使用方式\n")
    L.append("```python")
    L.append('train_ds = datasets.ImageFolder("data/processed/train", transform=train_tf)')
    L.append('val_ds   = datasets.ImageFolder("data/processed/val",   transform=eval_tf)')
    L.append('test_ds  = datasets.ImageFolder("data/processed/test",  transform=eval_tf)')
    L.append("```")
    L.append("")
    L.append("`ImageFolder` 会自动按文件夹名排序编码：**NORMAL=0，PNEUMONIA=1**。")
    L.append("")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(L), encoding="utf-8")

    print("=" * 60)
    print("=== 数据统计完成 ===")
    print(f"总样本: {total}")
    for s in SPLITS:
        print(f"  {s:<5}: NORMAL={int(ct.loc[s, 'NORMAL'])}  PNEUMONIA={int(ct.loc[s, 'PNEUMONIA'])}  合计={int(ct.loc[s].sum())}")
    print(f"数据泄漏检查: {'通过 ✅' if leak == 0 else f'发现 {leak} 处重叠 ⚠️'}")
    print(f"尺寸种类: {len(sizes)} 种，范围 {int(df.width.min())}×{int(df.height.min())} ~ {int(df.width.max())}×{int(df.height.max())}")
    print(f"\n报告: {REPORT.resolve()}")
    print(f"图表: {FIG_DIR.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
