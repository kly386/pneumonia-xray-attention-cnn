"""E3：数据增强消融实验（成员3：伍梦圆）。

单变量纪律：与保底基线相比，**只改 train 增强策略**（骨干固定 ResNet50，其余
两阶段协议/损失/优化器/seed=1234 与 train_baseline 完全一致），test 只终评一次。

变体（对照基线增强 = flip + rot10 + RRC(0.85,1.0) + CJ(0.1,0.1)）:
    none   全关（仅 resize+归一化）      -> 回答"增强是否必要"
    geo    仅几何（flip + rot10 + RRC）  -> 拆出颜色项贡献
    color  仅颜色（CJ 0.1,0.1）          -> 拆出几何项贡献
    strong 加强版（rot15 + RRC(0.7,1.0) + CJ 0.2）> 是否更强更好
    flip   仅水平翻转                   -> 单项贡献

用法（dl-env环境，仓库根目录）:
    D:\\Miniconda3\\envs\\dl-env\\python.exe -m src.train.train_e3 --variant none
    ... --variant geo / color / strong / flip
产出:
    models/checkpoints/resnet50_aug_<variant>.pt（+ logA/logB/stageA）
    reports/e3_results.json / reports/e3_augment.md
"""
from __future__ import annotations

import argparse
import json

import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

from src.train import common
from src.train.exp_utils import build_backbone, train_two_stage
from src.train.metrics import format_metrics
from src.train.train_baseline import run_epoch

RESULTS_JSON = common.REPORT_DIR / "e3_results.json"
RESULTS_MD = common.REPORT_DIR / "e3_augment.md"

IM = common.IMAGENET_MEAN, common.IMAGENET_STD
VARIANTS = {
    # 变体名 -> train transform（eval/val/test 永远 common::eval_tf 不变）
    "none": transforms.Compose([
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((common.IMG_SIZE, common.IMG_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize(*IM),
    ]),
    "geo": transforms.Compose([
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((common.IMG_SIZE, common.IMG_SIZE)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(10),
        transforms.RandomResizedCrop(common.IMG_SIZE, scale=(0.85, 1.0)),
        transforms.ToTensor(),
        transforms.Normalize(*IM),
    ]),
    "color": transforms.Compose([
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((common.IMG_SIZE, common.IMG_SIZE)),
        transforms.ColorJitter(brightness=0.1, contrast=0.1),
        transforms.ToTensor(),
        transforms.Normalize(*IM),
    ]),
    "strong": transforms.Compose([
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((common.IMG_SIZE, common.IMG_SIZE)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(15),
        transforms.RandomResizedCrop(common.IMG_SIZE, scale=(0.7, 1.0)),
        transforms.ColorJitter(brightness=0.2, contrast=0.2),
        transforms.ToTensor(),
        transforms.Normalize(*IM),
    ]),
    "flip": transforms.Compose([
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((common.IMG_SIZE, common.IMG_SIZE)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.ToTensor(),
        transforms.Normalize(*IM),
    ]),
}
HEAD_ATTR = "fc"


@torch.no_grad()
def test_once(run_name: str, ckpt_meta: dict, batch_size: int, num_workers: int) -> dict:
    ds = datasets.ImageFolder(common.DATA_DIR / "test", transform=common.eval_tf)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False,
                        num_workers=num_workers)
    net = build_backbone("resnet50", freeze=False, pretrained=False).to(common.DEVICE)
    sd = torch.load(common.CKPT_DIR / ckpt_meta["ckpt"], map_location="cpu",
                    weights_only=True)["model_state"]
    net.load_state_dict(sd)
    m = run_epoch(net, loader, common.make_loss(), optimizer=None)
    print("\n" + format_metrics(
        m, title=f"{run_name} · TEST (val F1={ckpt_meta['val_f1']:.4f})"), flush=True)
    return {k: (round(v, 4) if isinstance(v, float) else v)
            for k, v in m.items()
            if k != "loss" and k != "confusion_matrix"}


def _round(obj):
    if isinstance(obj, float):
        return round(obj, 4)
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    return obj


def update_reports(rows: list[dict]) -> None:
    RESULTS_JSON.write_text(json.dumps(_round(rows), ensure_ascii=False, indent=2),
                            encoding="utf-8")
    md = ["# E3 数据增强消融（单变量：只改 train 增强，骨干固定 ResNet50）",
          "",
          "> 负责: 伍梦圆 ｜ 协议与保底基线完全一致（两阶段 + weighted-CE +",
          "> val F1(macro) 选模 + 早停 pat=4，seed=1234，val/test 不增强）",
          "",
          "| 增强变体 | 阶段A val F1 | 最佳 val F1 | best@ep | test Acc | test F1 | test AUC | P-Recall | N-Recall |",
          "|---|---|---|---|---|---|---|---|---|"]
    order = ["baseline(全量增强)", "none", "geo", "color", "strong", "flip"]
    for name in order:
        r = next((x for x in rows if x["run"] == name), None)
        if not r:
            continue
        t = r.get("test", {})
        md.append(
            f"| {r['run']} | {r['stage_a_val_f1']:.4f} | {r['val_f1']:.4f} "
            f"| {r['best_epoch']} | {t.get('accuracy', '-')} "
            f"| {t.get('f1_macro', '-')} | {t.get('auc', '-')} "
            f"| {t.get('per_class', {}).get('PNEUMONIA', {}).get('recall', '-')} "
            f"| {t.get('per_class', {}).get('NORMAL', {}).get('recall', '-')} |")
    RESULTS_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"对比表已更新: {RESULTS_MD}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", required=True, choices=list(VARIANTS))
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--epochs-a", type=int, default=3)
    parser.add_argument("--epochs-b", type=int, default=15)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--lr-head", type=float, default=1e-3)
    parser.add_argument("--lr-body", type=float, default=3e-4)
    parser.add_argument("--test-only", action="store_true")
    args = parser.parse_args()

    common.set_seed(common.SEED)
    common.CKPT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"device = {common.DEVICE}  seed = {common.SEED}", flush=True)

    run_name = f"resnet50_aug_{args.variant}"
    ckpt_path = common.CKPT_DIR / f"{run_name}.pt"

    if args.test_only:
        ck = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        ck_a = torch.load(common.CKPT_DIR / f"{run_name}_stageA.pt",
                          map_location="cpu", weights_only=True)
        hist_b = json.loads((common.CKPT_DIR / f"{run_name}_logB.json")
                            .read_text(encoding="utf-8"))["history"]
        best_ep = max(hist_b, key=lambda h: h["val"]["f1_macro"])["epoch"]
        meta = {"run": run_name, "ckpt": ckpt_path.name,
                "stage_a_val_f1": ck_a["val_f1"], "val_f1": ck["val_f1"],
                "best_epoch": best_ep, "threshold": ck["best_threshold"]}
        te = test_once(run_name, meta, args.batch_size, args.num_workers)
        rows = json.loads(RESULTS_JSON.read_text(encoding="utf-8")) if RESULTS_JSON.exists() else []
        rows = [r for r in rows if r["run"] != run_name]
        rows.append({**meta, "test": _round(te)})
        update_reports(rows)
        return 0

    # 自定义 train transform 的 loaders（val/test 永远 eval_tf，纪律不破）
    train_ds = datasets.ImageFolder(common.DATA_DIR / "train",
                                    transform=VARIANTS[args.variant])
    val_ds = datasets.ImageFolder(common.DATA_DIR / "val", transform=common.eval_tf)
    test_ds = datasets.ImageFolder(common.DATA_DIR / "test", transform=common.eval_tf)
    kw = dict(batch_size=args.batch_size, num_workers=args.num_workers,
              pin_memory=True)
    train_loader = DataLoader(train_ds, shuffle=True, drop_last=False, **kw)
    val_loader = DataLoader(val_ds, shuffle=False, **kw)

    model = build_backbone("resnet50", freeze=True)
    meta = train_two_stage(model, train_loader, val_loader, run_name,
                           epochs_a=args.epochs_a, epochs_b=args.epochs_b,
                           lr_head=args.lr_head, lr_body=args.lr_body,
                           patience=args.patience, head_attr=HEAD_ATTR,
                           ckpt_dir=common.CKPT_DIR)

    te = test_once(run_name, meta, args.batch_size, args.num_workers)
    rows = json.loads(RESULTS_JSON.read_text(encoding="utf-8")) if RESULTS_JSON.exists() else []
    rows = [r for r in rows if r["run"] != run_name]
    rows.append({**meta, "test": {k: round(v, 4) if isinstance(v, float) else v
                                  for k, v in te.items()}})
    update_reports(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
