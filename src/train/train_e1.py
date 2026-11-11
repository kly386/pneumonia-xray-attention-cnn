"""E1：骨干网络对比实验（成员3：伍梦圆）。

单变量纪律：与保底基线相比，**只换骨干网络**，其余（两阶段协议/损失/优化器/
增强/输入/seed=1234）完全一致；test 只在最终评一次。

用法（dl-env 环境，仓库根目录）:
    D:\\Miniconda3\\envs\\dl-env\\python.exe -m src.train.train_e1 --arch resnet18
    顺序跑多个骨干（建议单独一个终端逐个跑，看日志）:
    ... --arch resnet34
    ... --arch densenet121
    ... --arch efficientnet_b0

产出:
    models/checkpoints/<arch>_baseline.pt       （+ _logA/_logB/_stageA）
    reports/e1_results.json                     全部骨干的对比行（逐次追加）
    reports/e1_backbone.md                      对比表（每次运行重写）
"""
from __future__ import annotations

import argparse
import json

import torch
from torch.utils.data import DataLoader
from torchvision import datasets

from src.train import common
from src.train.exp_utils import build_backbone, train_two_stage
from src.train.metrics import format_metrics
from src.train.train_baseline import run_epoch

RESULTS_JSON = common.REPORT_DIR / "e1_results.json"
RESULTS_MD = common.REPORT_DIR / "e1_backbone.md"


@torch.no_grad()
def test_once(run_name: str, arch: str, ckpt_meta: dict, batch_size: int,
              num_workers: int) -> dict:
    """test 一次性评估（红线：只在这里评 test 这一次）。"""
    ds = datasets.ImageFolder(common.DATA_DIR / "test", transform=common.eval_tf)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False,
                        num_workers=num_workers)
    net = build_backbone(arch, freeze=False, pretrained=False).to(common.DEVICE)
    sd = torch.load(common.CKPT_DIR / ckpt_meta["ckpt"], map_location="cpu",
                    weights_only=True)["model_state"]
    net.load_state_dict(sd)
    criterion = common.make_loss()
    m = run_epoch(net, loader, criterion, optimizer=None)
    text = format_metrics(m, title=f"{run_name} · TEST (val F1={ckpt_meta['val_f1']:.4f})")
    print("\n" + text, flush=True)
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
    RESULTS_JSON.write_text(
        json.dumps(_round(rows), ensure_ascii=False, indent=2), encoding="utf-8")
    md = ["# E1 骨干网络对比（单变量：只换骨干，其余与保底基线协议一致）",
          "",
          "> 负责: 伍梦圆 ｜ 协议: 两阶段迁移学习（冻结训头 3ep → 全网微调 ≤15ep，",
          "> 余弦退火 + AMP + weighted-CE + val F1 选模 + 早停 pat=4，seed=1234）",
          "",
          "| 骨干 | 阶段A val F1 | 最佳 val F1 | best@ep | val 阈值 | test Acc | test F1 | test AUC | P-Recall | N-Recall |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        t = r.get("test", {})
        md.append(
            f"| {r['run']} | {r['stage_a_val_f1']:.4f} | {r['val_f1']:.4f} "
            f"| {r['best_epoch']} | {r['threshold']:.4f} "
            f"| {t.get('accuracy', '-')} | {t.get('f1_macro', '-')} "
            f"| {t.get('auc', '-')} "
            f"| {t.get('per_class', {}).get('PNEUMONIA', {}).get('recall', '-')} "
            f"| {t.get('per_class', {}).get('NORMAL', {}).get('recall', '-')} |")
    RESULTS_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"对比表已更新: {RESULTS_MD}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arch", required=True,
                        choices=["resnet18", "resnet34", "densenet121", "efficientnet_b0"])
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--epochs-a", type=int, default=3)
    parser.add_argument("--epochs-b", type=int, default=15)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--lr-head", type=float, default=1e-3)
    parser.add_argument("--lr-body", type=float, default=3e-4)
    parser.add_argument("--test-only", action="store_true",
                        help="跳过训练，只对已存 checkpoint 做 test 评估 + 更新报表")
    args = parser.parse_args()

    common.set_seed(common.SEED)
    common.CKPT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"device = {common.DEVICE}  seed = {common.SEED}", flush=True)

    run_name = f"{args.arch}_baseline"
    ckpt_path = common.CKPT_DIR / f"{run_name}.pt"

    if args.test_only:  # 断点续跑：训练已完成，只补最终 test 评估 + 报表
        ck = torch.load(ckpt_path, map_location="cpu", weights_only=True)
        ck_a = torch.load(common.CKPT_DIR / f"{run_name}_stageA.pt",
                          map_location="cpu", weights_only=True)
        hist_b = json.loads((common.CKPT_DIR / f"{run_name}_logB.json")
                            .read_text(encoding="utf-8"))["history"]
        best_ep = max(hist_b, key=lambda h: h["val"]["f1_macro"])["epoch"]
        meta = {"run": run_name, "ckpt": ckpt_path.name,
                "stage_a_val_f1": ck_a["val_f1"], "val_f1": ck["val_f1"],
                "best_epoch": best_ep, "threshold": ck["best_threshold"]}
        te = test_once(run_name, args.arch, meta, args.batch_size,
                       args.num_workers)
        rows = json.loads(RESULTS_JSON.read_text(encoding="utf-8")) if RESULTS_JSON.exists() else []
        rows = [r for r in rows if r["run"] != run_name]
        rows.append({**meta, "test": _round(te)})
        update_reports(rows)
        return 0

    train_loader, val_loader, _ = common.build_loaders(
        batch_size=args.batch_size, num_workers=args.num_workers)

    model = build_backbone(args.arch, freeze=True)
    meta = train_two_stage(model, train_loader, val_loader, run_name,
                           epochs_a=args.epochs_a, epochs_b=args.epochs_b,
                           lr_head=args.lr_head, lr_body=args.lr_body,
                           patience=args.patience, head_attr=("classifier"
                                                              if args.arch in ("densenet121", "efficientnet_b0") else "fc"),
                           ckpt_dir=common.CKPT_DIR)

    te = test_once(run_name, args.arch, meta, args.batch_size, args.num_workers)

    rows = json.loads(RESULTS_JSON.read_text(encoding="utf-8")) if RESULTS_JSON.exists() else []
    rows = [r for r in rows if r["run"] != run_name]  # 重跑覆盖旧行
    rows.append({**meta,
                 "test": {k: round(v, 4) if isinstance(v, float) else v
                          for k, v in te.items()}})
    update_reports(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
