"""模型构建：迁移学习骨干网络。

基线 = torchvision ResNet50（ImageNet 预训练），替换全连接头为
Dropout + Linear 二分类。

两阶段训练约定（保底版策略，见技术方案书 5.2）:
    freeze=True   -> 全部卷积层冻结，只训练分类头（阶段 A，快速验证管道）
    freeze=False  -> 解冻全网低学习率微调（阶段 B，冲指标）

后续注意力改进（SE / CBAM）与骨干对比模型也将以同样的接口在此文件扩展。
"""
from __future__ import annotations

import torch.nn as nn
from torchvision import models


def _replace_head(net: nn.Module, num_classes: int, dropout: float) -> None:
    """统一替换分类头（ResNet50 的 fc）。"""
    in_features = net.fc.in_features
    net.fc = nn.Sequential(
        nn.Dropout(dropout),
        nn.Linear(in_features, num_classes),
    )


def build_resnet50(freeze: bool, dropout: float = 0.3) -> models.ResNet:
    """构建 ResNet50 迁移学习模型。

    Args:
        freeze: True 表示冻结全部卷积层（阶段 A），False 表示全网可训练（阶段 B）。
        dropout: 分类头 Dropout 概率。
    Returns:
        models.ResNet（已替换分类头）
    """
    # weights=IMAGENET1K_V2 = 更新的预训练权重（ torchvision >= 0.13）
    net = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
    _replace_head(net, num_classes=2, dropout=dropout)

    if freeze:
        for p in net.parameters():
            p.requires_grad = False
        # 只解冻分类头
        for p in net.fc.parameters():
            p.requires_grad = True

    # 关键：必须让分类头之外的 BatchNorm 的 momentum 保持默认，
    # freeze 模式下带 BN 的层若不 eval 会更新 running stats —— 训练时由 train 脚本处理。
    return net


def param_groups(net: nn.Module, lr_head: float, base_lr: float, weight_decay: float):
    """返回 optimizer 参数组：分类头用大学习率，骨干用小学习率（阶段 B 微调）。"""
    head_params = [p for p in net.fc.parameters() if p.requires_grad]
    body_params = [p for i, (name, p) in enumerate(net.named_parameters())
                   if p.requires_grad and not name.startswith("fc.")]
    return [
        {"params": body_params, "lr": base_lr},
        {"params": head_params, "lr": lr_head},
    ], weight_decay


if __name__ == "__main__":
    import torch

    net = build_resnet50(freeze=True)
    trainable = sum(p.numel() for p in net.parameters() if p.requires_grad)
    total = sum(p.numel() for p in net.parameters())
    print(f"stage A 可训练参数: {trainable / 1e6:.2f} M / 总参数 {total / 1e6:.1f} M")

    net = build_resnet50(freeze=False)
    trainable = sum(p.numel() for p in net.parameters() if p.requires_grad)
    print(f"stage B 可训练参数: {trainable / 1e6:.2f} M")

    x = torch.randn(2, 3, 224, 224)
    out = net(x)
    print(f"前向输出 shape: {tuple(out.shape)}  (期望 (2, 2))")
