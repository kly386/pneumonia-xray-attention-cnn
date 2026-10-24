"""数据清洗 + 8:1:1 分层划分。

流程:
    1. 扫描 data/raw/chest_xray/ 下 train/val/test 全部图像
    2. 完整性校验（能否被 PIL 正常打开，剔除损坏文件）
    3. MD5 精确去重（同名/异名同一张图只保留一份）
    4. 合并后按 8:1:1 分层抽样划分（固定随机种子 SEED=1234）
    5. 复制到 data/processed/{split}/{class}/
    6. 输出划分清单 data/splits/split_manifest.csv
       输出清洗日志 data/splits/cleaning_log.csv

用法:
    python src/data/make_split.py
"""
from __future__ import annotations

import csv
import hashlib
import random
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image
from sklearn.model_selection import train_test_split

RAW_DIR = Path("data/raw/chest_xray")
OUT_DIR = Path("data/processed")
SPLIT_DIR = Path("data/splits")
MANIFEST = SPLIT_DIR / "split_manifest.csv"
CLEAN_LOG = SPLIT_DIR / "cleaning_log.csv"

SEED = 1234
CLASSES = ["NORMAL", "PNEUMONIA"]
SRC_SPLITS = ["train", "val", "test"]
OUT_SPLITS = ["train", "val", "test"]
IMG_EXTS = {".jpeg", ".jpg", ".png", ".bmp", ".tif", ".tiff"}

# 目标比例 8:1:1
VAL_TEST_RATIO = 0.2        # 先切出 20% 作为 val+test
TEST_RATIO_OF_VALTEST = 0.5  # 再对半分成 val / test


def md5_of(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def verify_image(path: Path) -> tuple[bool, str, tuple[int, int] | None]:
    """返回 (是否有效, 原因, (宽,高))"""
    try:
        with Image.open(path) as im:
            im.verify()  # 校验文件完整性
        with Image.open(path) as im:
            im.load()    # 真正解码一次，捕获截断文件
            return True, "", im.size
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}", None


def main() -> int:
    if not RAW_DIR.exists():
        print(f"[ERR] 找不到 {RAW_DIR.resolve()}")
        return 1

    random.seed(SEED)
    SPLIT_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- 1. 扫描 ----------
    print("=" * 60)
    print("[1/5] 扫描原始数据 ...")
    items: list[tuple[Path, str]] = []
    for s in SRC_SPLITS:
        for c in CLASSES:
            d = RAW_DIR / s / c
            if not d.exists():
                continue
            for f in sorted(d.iterdir()):
                if f.is_file() and f.suffix.lower() in IMG_EXTS:
                    items.append((f, c))
    print(f"      扫描到 {len(items)} 张图像，原始分布 {dict(Counter(c for _, c in items))}")

    # ---------- 2. 完整性校验 ----------
    print("\n[2/5] 完整性校验 ...")
    clean_log: list[dict] = []
    valid: list[tuple[Path, str, tuple[int, int]]] = []
    for p, c in items:
        ok, reason, size = verify_image(p)
        if ok and size:
            valid.append((p, c, size))
        else:
            clean_log.append({
                "src_path": str(p).replace("\\", "/"),
                "label": c,
                "action": "removed_corrupt",
                "reason": reason,
                "md5": "",
            })
    print(f"      有效 {len(valid)} 张，损坏/无法读取 {len(items) - len(valid)} 张")

    # ---------- 3. 去重 ----------
    print("\n[3/5] MD5 精确去重 ...")
    seen: dict[str, Path] = {}
    unique: list[tuple[Path, str, tuple[int, int], str]] = []
    dup_cnt = 0
    for p, c, size in valid:
        h = md5_of(p)
        if h in seen:
            dup_cnt += 1
            clean_log.append({
                "src_path": str(p).replace("\\", "/"),
                "label": c,
                "action": "removed_duplicate",
                "reason": f"与 {seen[h].name} 完全相同",
                "md5": h,
            })
        else:
            seen[h] = p
            unique.append((p, c, size, h))
    print(f"      去重后 {len(unique)} 张，剔除重复 {dup_cnt} 张")

    # ---------- 4. 分层划分 ----------
    print("\n[4/5] 8:1:1 分层划分 (seed=%d) ..." % SEED)
    paths = [u[0] for u in unique]
    labels = [u[1] for u in unique]

    train_paths, vt_paths, train_labels, vt_labels = train_test_split(
        paths, labels,
        test_size=VAL_TEST_RATIO,
        stratify=labels,
        random_state=SEED,
    )
    val_paths, test_paths, val_labels, test_labels = train_test_split(
        vt_paths, vt_labels,
        test_size=TEST_RATIO_OF_VALTEST,
        stratify=vt_labels,
        random_state=SEED,
    )

    # 建立 path -> (label, size, md5) 索引
    info = {str(u[0]): (u[1], u[2], u[3]) for u in unique}
    split_map = {
        "train": list(zip(train_paths, train_labels)),
        "val": list(zip(val_paths, val_labels)),
        "test": list(zip(test_paths, test_labels)),
    }

    # ---------- 5. 复制 + 清单 ----------
    print("\n[5/5] 复制文件并生成清单 ...")
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    for s in OUT_SPLITS:
        for c in CLASSES:
            (OUT_DIR / s / c).mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    name_counter: Counter[str] = Counter()
    for s in OUT_SPLITS:
        for src, lbl in split_map[s]:
            # 防止跨划分同名（极少见）
            key = f"{s}/{lbl}/{src.name}"
            dst = OUT_DIR / s / lbl / src.name
            if dst.exists():
                dst = OUT_DIR / s / lbl / f"{src.parent.name}_{name_counter[key]}_{src.name}"
            name_counter[key] += 1
            shutil.copy2(src, dst)

            _, size, md5 = info[str(src)]
            rows.append({
                "filepath": str(dst).replace("\\", "/"),
                "label": lbl,
                "split": s,
                "width": size[0],
                "height": size[1],
                "md5": md5,
                "src_path": str(src).replace("\\", "/"),
            })

    with open(MANIFEST, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["filepath", "label", "split", "width", "height", "md5", "src_path"],
        )
        w.writeheader()
        w.writerows(rows)

    with open(CLEAN_LOG, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["src_path", "label", "action", "reason", "md5"])
        w.writeheader()
        w.writerows(clean_log)

    # ---------- 汇总 ----------
    print("\n" + "=" * 60)
    print("=== 清洗汇总 ===")
    print(f"  原始: {len(items)} 张")
    print(f"  损坏剔除: {len(items) - len(valid)} 张")
    print(f"  重复剔除: {dup_cnt} 张")
    print(f"  最终可用: {len(unique)} 张")

    print("\n=== 划分结果 (8:1:1 分层) ===")
    total = len(unique)
    for s in OUT_SPLITS:
        cnt = Counter(lbl for _, lbl in split_map[s])
        n = len(split_map[s])
        print(f"  {s:<5}: {n:>4} 张 ({n / total * 100:5.2f}%)  "
              f"NORMAL={cnt['NORMAL']:<4} PNEUMONIA={cnt['PNEUMONIA']:<4} "
              f"阳性占比={cnt['PNEUMONIA'] / n * 100:5.2f}%")

    print(f"\n  已输出: {OUT_DIR.resolve()}")
    print(f"  划分清单: {MANIFEST.resolve()}")
    print(f"  清洗日志: {CLEAN_LOG.resolve()}")
    print("\n完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
