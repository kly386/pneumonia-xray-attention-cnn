"""ResNet50 保底基线训练（两阶段迁移学习 + 早停）。

策略（对应技术方案书 5.2，保底版优先）:
    阶段 A：冻结骨干，只训练分类头（快速验证管道）
    阶段 B：解冻全网低学习率微调，余弦退火 + AMP 混合精度
    早停与选模指标：val 的 F1(macro)（类别不平衡下比 Accuracy 更可靠）
    交叉熵使用类别权重 [1.8444, 0.6860]（数据组 verify_loader.py 给出）

产出:
    models/checkpoints/resnet50_baseline.pt      最优模型（含 best 阈值）
    models/checkpoints/resnet50_baseline_log.json 训练日志
    reports/model_baseline.md                    阶段 A/B 与 test 评估汇总

⚠️ 纪律：test 只允许最终评估一次，禁止在 test 上调参。

用法（conda pytorch 环境，仓库根目录）:
    C:\\Users\\29542\\.conda\\envs\\pytorch\\python.exe -m src.train.train_baseline
    可选: --batch-size 32 --epochs-b 15 --patience 4 --num-workers 2
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from src.train import common
from src.train.metrics import compute_metrics, format_metrics
from src.train.model import build_resnet50, param_groups


# --------------------------------------------------------------- 训练/评估单轮
def run_epoch(model, loader, criterion, optimizer=None, scaler=None, desc=""):
    """一个 epoch 的训练（optimizer 非 None）或评估（None）。"""
    import torch

    is_train = optimizer is not None
    model.train(is_train) if is_train else model.eval()

    ys, ps, probs = [], [], []
    loss_sum = 0.0
    n = 0

    ctx = torch.enable_grad() if is_train else torch.no_grad()
    with ctx:
        for i, (imgs, labels) in enumerate(loader):
            imgs = imgs.to(common.DEVICE, non_blocking=True)
            labels = labels.to(common.DEVICE, non_blocking=True)

            with torch.autocast("cuda", enabled=scaler is not None):
                logits = model(imgs)
                loss = criterion(logits, labels)

            if is_train:
                optimizer.zero_grad(set_to_none=True)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

            bs = labels.size(0)
            loss_sum += loss.item() * bs
            n += bs
            pred = logits.argmax(1)
            prob1 = torch.softmax(logits, dim=1)[:, 1]

            ys.extend(labels.cpu().tolist())
            ps.extend(pred.cpu().tolist())
            probs.extend(prob1.detach().float().cpu().tolist())

    avg_loss = loss_sum / max(n, 1)
    m = compute_metrics(ys, ps, probs)
    m["loss"] = avg_loss
    return m


def train_stage(model, train_loader, val_loader, name, epochs, lr_body, lr_head,
                patience, freeze, log_path, lr_attn=None):
    """训练一个阶段，返回 (best_checkpoint 状态字典, 最佳 val F1, 历史列表)。"""
    criterion = common.make_loss()

    if freeze:
        optimizer = AdamW(
            [p for p in model.parameters() if p.requires_grad],
            lr=lr_head, weight_decay=1e-4,
        )
    else:
        groups, wd = param_groups(model, lr_head=lr_head, base_lr=lr_body,
                                  weight_decay=1e-4, lr_attn=lr_attn)
        optimizer = AdamW(groups, lr=lr_head, weight_decay=wd)  # 组内会覆盖顶层 lr

    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=lr_head * 0.01)
    scaler = torch.amp.GradScaler("cuda", enabled=(common.DEVICE.type == "cuda"))

    best = {"f1": -1.0, "state": None, "epoch": -1, "threshold": 0.5}
    history = []
    bad_epochs = 0

    print(f"\n──── {name} 开始 ────  epochs={epochs}  device={common.DEVICE}", flush=True)
    for ep in range(1, epochs + 1):
        t0 = time.time()
        tr = run_epoch(model, train_loader, criterion, optimizer, scaler)
        va = run_epoch(model, val_loader, criterion, optimizer=None, scaler=None)

        history.append({
            "stage": name, "epoch": ep,
            "train": {k: round(v, 4) for k, v in tr.items() if not isinstance(v, (list, dict))},
            "val": {k: round(v, 4) for k, v in va.items() if not isinstance(v, (list, dict))},
            "lr": scheduler.get_last_lr(),
        })

        improved = ""
        if va["f1_macro"] > best["f1"]:
            best = {
                "f1": va["f1_macro"],
                "state": {k: v.detach().cpu().clone() for k, v in model.state_dict().items()},
                "epoch": ep,
                "threshold": va["best_threshold"],
            }
            bad_epochs = 0
            improved = "  ⬆ best"
        else:
            bad_epochs += 1

        scheduler.step()
        print(
            f"  epoch {ep:>2}/{epochs}  "
            f"train F1={tr['f1_macro']:.4f} AUC={tr['auc']:.4f} loss={tr['loss']:.4f} | "
            f"val F1={va['f1_macro']:.4f} AUC={va['auc']:.4f} loss={va['loss']:.4f} "
            f"({time.time() - t0:.0f}s){improved}",
            flush=True,
        )

        if bad_epochs >= patience:
            print(f"  早停触发（连续 {patience} 个 epoch 无提升）", flush=True)
            break

    Path(log_path).write_text(
        json.dumps({"stage": name, "history": history}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return best, history


# --------------------------------------------------------------- 主流程
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--epochs-a", type=int, default=3, help="阶段 A 分类头训练轮数")
    parser.add_argument("--epochs-b", type=int, default=15, help="阶段 B 微调最大轮数")
    parser.add_argument("--patience", type=int, default=4, help="早停耐心值（epoch）")
    parser.add_argument("--lr-head", type=float, default=1e-3, help="分类头学习率")
    parser.add_argument("--lr-body", type=float, default=3e-4, help="骨干微调学习率")
    parser.add_argument("--skip-a", action="store_true",
                        help="跳过阶段 A，直接载入 models/checkpoints/resnet50_baseline_stageA.pt 续跑阶段 B")
    args = parser.parse_args()

    common.set_seed(common.SEED)
    common.CKPT_DIR.mkdir(parents=True, exist_ok=True)

    from src.train import common as c  # 避免重复导入 name
    print(f"device = {c.DEVICE}  seed = {c.SEED}")
    print(f"数据目录: {c.DATA_DIR}")

    train_loader, val_loader, test_loader = common.build_loaders(
        batch_size=args.batch_size, num_workers=args.num_workers
    )
    criterion = common.make_loss()

    # ---------- 阶段 A：冻结骨干，只训练分类头 ----------
    stage_a_ckpt = c.CKPT_DIR / "resnet50_baseline_stageA.pt"
    if args.skip_a and stage_a_ckpt.exists():
        print(f"[skip-a] 载入已有阶段 A 检查点: {stage_a_ckpt}", flush=True)
        saved = torch.load(stage_a_ckpt, map_location="cpu", weights_only=True)
        best_a = {
            "f1": saved["val_f1"],
            "state": saved["model_state"],
            "epoch": saved["epoch"],
            "threshold": saved["threshold"],
        }
    else:
        model_a = build_resnet50(freeze=True, dropout=0.3).to(c.DEVICE)
        best_a, hist_a = train_stage(
            model_a, train_loader, val_loader, "StageA-headOnly",
            epochs=args.epochs_a, lr_body=0.0, lr_head=args.lr_head,
            patience=args.patience, freeze=True,
            log_path=c.CKPT_DIR / "resnet50_baseline_logA.json",
        )
        # 阶段 A 最优落盘，供后续断点续跑（--skip-a）复用
        torch.save(
            {
                "model_state": best_a["state"],
                "arch": "resnet50_baseline_stageA",
                "val_f1": best_a["f1"],
                "epoch": best_a["epoch"],
                "threshold": best_a["threshold"],
            },
            stage_a_ckpt,
        )
        print(f"阶段 A 检查点已保存: {stage_a_ckpt}", flush=True)
    print(f"阶段 A 最佳 val F1 = {best_a['f1']:.4f} (epoch {best_a['epoch']})", flush=True)

    # ---------- 阶段 B：解冻全网微调（从阶段 A 最优出发） ----------
    model_b = build_resnet50(freeze=False, dropout=0.3).to(c.DEVICE)
    model_b.load_state_dict(best_a["state"])  # 继承阶段 A 结构+权重（fc 只有 shape 一致）
    best_b, hist_b = train_stage(
        model_b, train_loader, val_loader, "StageB-finetune",
        epochs=args.epochs_b, lr_body=args.lr_body, lr_head=args.lr_head * 0.1,
        patience=args.patience, freeze=False,
        log_path=c.CKPT_DIR / "resnet50_baseline_logB.json",
    )
    print(f"阶段 B 最佳 val F1 = {best_b['f1']:.4f} (epoch {best_b['epoch']})")

    # ---------- 保存最优 ----------
    ckpt_path = c.CKPT_DIR / "resnet50_baseline.pt"
    torch.save(
        {
            "model_state": best_b["state"],
            "arch": "resnet50_baseline",
            "num_classes": 2,
            "img_size": c.IMG_SIZE,
            "val_f1": best_b["f1"],
            "best_threshold": best_b["threshold"],
            "seed": c.SEED,
        },
        ckpt_path,
    )
    print(f"最优模型已保存: {ckpt_path}")

    # ---------- test 一次性评估 ----------
    model_final = build_resnet50(freeze=False, dropout=0.3).to(c.DEVICE)
    model_final.load_state_dict(best_b["state"])
    te = run_epoch(model_final, test_loader, criterion, optimizer=None, scaler=None)
    text = format_metrics(te, title=f"ResNet50 保底基线 · TEST (val F1={best_b['f1']:.4f})")
    print("\n" + text)

    # ---------- 报告落盘 ----------
    md = f"""# ResNet50 保底基线 · 训练与评估

> 训练环境: conda `pytorch` (torch 2.7.1+cu118, RTX 4060 Laptop)  seed={c.SEED}

## 配置
| 参数 | 值 |
|---|---|
| 骨干 | torchvision ResNet50（ImageNet1K_V2 预训练） |
| 阶段 A | 冻结骨干，只训分类头，epochs={args.epochs_a}，lr_head={args.lr_head} |
| 阶段 B | 全网微调，epochs≤{args.epochs_b}，lr_body={args.lr_body}，余弦退火 |
| 损失 | CrossEntropy + 类别权重 [1.8444, 0.6860] + label_smoothing=0.05 |
| 优化 | AdamW + AMP 混合精度 + 早停 patience={args.patience} |
| 选模指标 | **val F1(macro)**（非 Accuracy） |
| batch | {args.batch_size}，输入 224×224，增强仅 train |

## 阶段表现
| 阶段 | 最佳 val F1(macro) | epoch |
|---|---|---|
| A（head only） | {best_a['f1']:.4f} | {best_a['epoch']} |
| B（finetune） | {best_b['f1']:.4f} | {best_b['epoch']} |

## TEST 一次性评估（最终报告用）

```
{text}
```

> 阈值说明：类别 1:2.69 不平衡下，默认 0.5 阈值非最优，以上 test 结果
> 使用「val 最佳 F1 阈值」在 test 同样阈值下评估；部署时如需更高 PNEUMONIA
> Recall（灵敏度），可在 val 曲线上再调低阈值。

## 结论与下一步
- 保底版验收线：Accuracy ≥ 0.90、AUC ≥ 0.95、PNEUMONIA Recall ≥ 0.92
- 达标后按既定策略冻结本版；下一步叠加 SE / CBAM 注意力消融（实验 E2）。
"""
    (c.REPORT_DIR / "model_baseline.md").write_text(md, encoding="utf-8")
    print(f"训练报告已写入: {c.REPORT_DIR / 'model_baseline.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
