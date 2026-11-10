"""E1/E3 实验公共件（成员3：伍梦圆）。

复用两阶段协议（与 train_baseline.py 完全一致：只换骨干/增强这一个变量）:
    阶段 A 冻结骨干训头 3 epoch → 阶段 B 全网微调 ≤15 epoch（余弦退火 + AMP +
    val F1 选模 + 早停 patience=4），test 只在最终评一次。

与 mj 的 train_baseline 的差异（单变量纪律所需的最小改动）:
    - build_backbone：支持 resnet18/34/50、densenet121、efficientnet_b0，
      分类头统一替换为 Dropout+Linear 二分类（对应各自的 head 属性名）
    - param_groups_ex：按 head 属性名取分类头参数（fc / classifier），
      注意力单列 lr 的逻辑与 mj 的 param_groups 保持一致
    - train_two_stage：train_stage 的通用化版本（head 属性名可配置）
    - build_loaders_tf：允许指定自定义 train transform（E3 增强消融用）
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torchvision import models

from src.train import common
from src.train.train_baseline import run_epoch

# 各骨干：(构建函数, 预训练权重枚举, 分类头属性名)
ATTN_KEYS = ("channel_gate", "spatial_gate", "attn.")


def _torchvision_backbone(arch: str, pretrained: bool = True):
    """按 arch 构建 torchvision 骨干并统一替换分类头。返回 (net, head_attr)。"""
    head_attr = "classifier" if arch in ("densenet121", "efficientnet_b0") else "fc"

    if arch.startswith("resnet"):
        weights_map = {
            "resnet18": models.ResNet18_Weights.IMAGENET1K_V1,
            "resnet34": models.ResNet34_Weights.IMAGENET1K_V1,
            "resnet50": models.ResNet50_Weights.IMAGENET1K_V2,
        }
        net = getattr(models, arch)(weights=weights_map[arch] if pretrained else None)
        in_features = net.fc.in_features
    elif arch == "densenet121":
        net = models.densenet121(
            weights=models.DenseNet121_Weights.IMAGENET1K_V1 if pretrained else None)
        in_features = net.classifier.in_features
    elif arch == "efficientnet_b0":
        net = models.efficientnet_b0(
            weights=models.EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None)
        in_features = net.classifier[1].in_features
    else:
        raise ValueError(f"不支持的骨干: {arch}")

    setattr(net, head_attr,
            torch.nn.Sequential(torch.nn.Dropout(0.3), torch.nn.Linear(in_features, 2)))
    return net, head_attr


def build_backbone(arch: str, freeze: bool, pretrained: bool = True) -> torch.nn.Module:
    """迁移学习骨干：ImageNet 预训练 + 二分类头；freeze 同 mj 的两阶段约定。"""
    net, head_attr = _torchvision_backbone(arch, pretrained)
    if freeze:
        for p in net.parameters():
            p.requires_grad = False
        head = getattr(net, head_attr)
        for p in head.parameters():
            p.requires_grad = True
    return net


def param_groups_ex(net: torch.nn.Module, head_attr: str, lr_head: float,
                    base_lr: float, weight_decay: float,
                    lr_attn: float | None = None):
    """head 属性名可配置的参数组（逻辑与 mj 的 param_groups 一致）。"""
    head = getattr(net, head_attr)
    head_params = [p for p in head.parameters() if p.requires_grad]
    body_params: list[torch.nn.Parameter] = []
    attn_params: list[torch.nn.Parameter] = []
    for name, p in net.named_parameters():
        if not p.requires_grad or name.startswith(f"{head_attr}."):
            continue
        if any(k in name for k in ATTN_KEYS):
            attn_params.append(p)
        else:
            body_params.append(p)

    groups: list[dict] = [{"params": body_params, "lr": base_lr}]
    if attn_params:
        groups.append({"params": attn_params,
                       "lr": lr_attn if lr_attn is not None else base_lr})
    groups.append({"params": head_params, "lr": lr_head})
    return groups, weight_decay


def train_two_stage(model, train_loader, val_loader, run_name: str,
                    epochs_a: int, epochs_b: int, lr_head: float, lr_body: float,
                    patience: int, head_attr: str, ckpt_dir: Path):
    """两阶段训练（协议同 train_baseline），产出冻结式 checkpoint。返回 (ckpt元数据, val/test 概述)。"""
    criterion = common.make_loss()
    log_a = ckpt_dir / f"{run_name}_logA.json"
    log_b = ckpt_dir / f"{run_name}_logB.json"

    def _stage(model, name, epochs, lr_body, lr_head, freeze, log_path):
        if freeze:
            optimizer = AdamW([p for p in model.parameters() if p.requires_grad],
                              lr=lr_head, weight_decay=1e-4)
        else:
            groups, wd = param_groups_ex(model, head_attr, lr_head=lr_head,
                                         base_lr=lr_body, weight_decay=1e-4)
            optimizer = AdamW(groups, lr=lr_head, weight_decay=wd)
        scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=lr_head * 0.01)
        scaler = torch.amp.GradScaler("cuda", enabled=(common.DEVICE.type == "cuda"))
        best = {"f1": -1.0, "state": None, "epoch": -1, "threshold": 0.5}
        history, bad = [], 0
        print(f"\n──── {run_name} · {name} ────  epochs={epochs}", flush=True)
        for ep in range(1, epochs + 1):
            t0 = time.time()
            tr = run_epoch(model, train_loader, criterion, optimizer, scaler)
            va = run_epoch(model, val_loader, criterion, optimizer=None)
            history.append({
                "stage": name, "epoch": ep,
                "train": {k: round(v, 4) for k, v in tr.items()
                          if not isinstance(v, (list, dict))},
                "val": {k: round(v, 4) for k, v in va.items()
                        if not isinstance(v, (list, dict))},
            })
            improved = ""
            if va["f1_macro"] > best["f1"]:
                best = {"f1": va["f1_macro"],
                        "state": {k: v.detach().cpu().clone()
                                  for k, v in model.state_dict().items()},
                        "epoch": ep, "threshold": va["best_threshold"]}
                bad = 0
                improved = "  <- best"
            else:
                bad += 1
            scheduler.step()
            print(f"  epoch {ep:>2}/{epochs}  train F1={tr['f1_macro']:.4f} | "
                  f"val F1={va['f1_macro']:.4f} AUC={va['auc']:.4f} "
                  f"({time.time() - t0:.0f}s){improved}", flush=True)
            if bad >= patience:
                print("  早停触发", flush=True)
                break
        Path(log_path).write_text(
            json.dumps({"stage": name, "history": history}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        return best

    # 阶段 A
    model_a = model.to(common.DEVICE)
    best_a = _stage(model_a, "StageA-headOnly", epochs_a, 0.0, lr_head,
                    freeze=True, log_path=log_a)
    print(f"阶段 A 最佳 val F1 = {best_a['f1']:.4f} (epoch {best_a['epoch']})", flush=True)
    stage_a_ckpt = ckpt_dir / f"{run_name}_stageA.pt"
    torch.save({"model_state": best_a["state"], "arch": f"{run_name}_stageA",
                "val_f1": best_a["f1"], "epoch": best_a["epoch"],
                "threshold": best_a["threshold"]}, stage_a_ckpt)

    # 阶段 B
    model_b = model.to(common.DEVICE)
    model_b.load_state_dict(best_a["state"])
    best_b = _stage(model_b, "StageB-finetune", epochs_b, lr_body, lr_head * 0.1,
                    freeze=False, log_path=log_b)
    print(f"阶段 B 最佳 val F1 = {best_b['f1']:.4f} (epoch {best_b['epoch']})", flush=True)

    ckpt_path = ckpt_dir / f"{run_name}.pt"
    torch.save({"model_state": best_b["state"], "arch": run_name,
                "num_classes": 2, "img_size": common.IMG_SIZE,
                "val_f1": best_b["f1"], "best_threshold": best_b["threshold"],
                "seed": common.SEED}, ckpt_path)
    print(f"最优模型已保存: {ckpt_path}", flush=True)
    return {"run": run_name, "ckpt": str(ckpt_path.name),
            "stage_a_val_f1": best_a["f1"], "val_f1": best_b["f1"],
            "best_epoch": best_b["epoch"], "threshold": best_b["threshold"]}
