"""注意力模块库（实验 E2：注意力消融）。

提供两种课程方案书选定的注意力增强模块，可插入 torchvision ResNet50 的指定 stage：
    - SE  (Squeeze-and-Excitation, Hu et al., 2018)  通道注意力
    - CBAM (Convolutional Block Attention Module, Woo et al., ECCV 2018) 通道+空间双注意力

插入位置约定（单变量纪律，首版固定）:
    默认 stage = layer3 + layer4（接近输出端的深层特征，语义强、GPU 开销小）；
    layer1/layer2 不动 —— 保留低层通用边缘/纹理特征不被首版实验扰动。

实现要点（给后续复用的同学）:
    ResNet50 的每个 Bottleneck 内部已做残差相加，因此选择在"整个 Bottleneck 输出之后"
    串联注意力（out = attn(out)），这是论文与主流实现的常规做法，梯度路径清晰；
    注意力模块本身**永远可训练**（即使冻结骨干阶段 A）——它们是新学的组件，
    冻骨冻的是预训练权重，不该把新模块一起冻死。
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torchvision import models

# ---------------------------------------------------------------- SE
class SEBlock(nn.Module):
    """通道注意力：全局池化 -> 两层 1x1 卷积（压缩/扩张）-> Sigmoid 门控。"""

    def __init__(self, channels: int, reduction: int = 16):
        super().__init__()
        mid = max(channels // reduction, 1)
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Conv2d(channels, mid, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, channels, 1),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        w = self.fc(self.pool(x))          # (B, C, 1, 1)
        return x * w                       # 逐通道缩放


# ---------------------------------------------------------------- CBAM
class ChannelGate(nn.Module):
    """CBAM 通道门：avg-pool 与 max-pool 共享同一个 MLP，两者结果相加后过 Sigmoid。"""

    def __init__(self, channels: int, reduction: int = 16):
        super().__init__()
        mid = max(channels // reduction, 1)
        self.mlp = nn.Sequential(
            nn.Conv2d(channels, mid, 1),
            nn.ReLU(inplace=True),
            nn.Conv2d(mid, channels, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        avg = self.mlp(x.mean(dim=(2, 3), keepdim=True))
        mx = self.mlp(x.amax(dim=(2, 3), keepdim=True))
        return torch.sigmoid(avg + mx)     # (B, C, 1, 1)


class SpatialGate(nn.Module):
    """CBAM 空间门：沿通道取 avg/max 拼接 -> 7x7 卷积 -> Sigmoid。"""

    def __init__(self, kernel_size: int = 7):
        super().__init__()
        self.conv = nn.Conv2d(2, 1, kernel_size, padding=kernel_size // 2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        avg = x.mean(dim=1, keepdim=True)
        mx = x.amax(dim=1, keepdim=True)
        w = torch.sigmoid(self.conv(torch.cat([avg, mx], dim=1)))   # (B, 1, H, W)
        return x * w


class CBAMBlock(nn.Module):
    """通道门 + 空间门 串联。"""

    def __init__(self, channels: int, reduction: int = 16, kernel_size: int = 7):
        super().__init__()
        self.channel_gate = ChannelGate(channels, reduction)
        self.spatial_gate = SpatialGate(kernel_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x * self.channel_gate(x)
        return self.spatial_gate(x)


# ---------------------------------------------------------------- 插入基础设施
ATTN_MODULES = {"se": SEBlock, "cbam": CBAMBlock}


class BottleneckWithAttention(nn.Module):
    """把 Bottleneck 原块与注意力模块打包；forward = 原块输出 -> 注意力。"""

    def __init__(self, bottleneck: nn.Module, attn: nn.Module):
        super().__init__()
        self.block = bottleneck
        self.attn = attn

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.attn(self.block(x))


def attach_attention_to_stage(stage: nn.Sequential, attn_type: str) -> None:
    """把 stage（如 net.layer3）里每个 Bottleneck 都包上注意力。原地修改。"""
    attn_cls = ATTN_MODULES[attn_type]
    for i, block in enumerate(stage):
        channels = block.conv3.out_channels        # bottleneck 输出通道（在 conv3 上）
        stage[i] = BottleneckWithAttention(block, attn_cls(channels))


def build_resnet50_attn(
    freeze: bool,
    dropout: float = 0.3,
    attn_type: str = "none",
    positions: tuple[str, ...] = ("layer3", "layer4"),
) -> models.ResNet:
    """构建带注意力的 ResNet50 迁移学习模型（与 model.py::build_resnet50 同约定）。

    Args:
        freeze: True 冻结骨干卷积（阶段 A）；注意力与分类头始终可训练。
        attn_type: "none" / "se" / "cbam"。
        positions: 插入注意力的 stage 名，可含 layer1~layer4。
    """
    net = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)

    if attn_type != "none":
        for pos in positions:
            attach_attention_to_stage(getattr(net, pos), attn_type)

    in_features = net.fc.in_features
    net.fc = nn.Sequential(
        nn.Dropout(dropout),
        nn.Linear(in_features, 2),
    )

    if freeze:
        for p in net.parameters():
            p.requires_grad = False
        # 只解冻：分类头 + （插入了的）注意力模块 —— 冻的是预训练权重，新学组件不冻
        for p in net.fc.parameters():
            p.requires_grad = True
        for m in net.modules():
            if isinstance(m, BottleneckWithAttention):
                for p in m.attn.parameters():
                    p.requires_grad = True

    return net


def count_params_by_group(net: nn.Module) -> dict[str, int]:
    """分桶统计可训练参数（自检/写报告用）。"""
    head = sum(p.numel() for p in net.fc.parameters() if p.requires_grad)
    attn = 0
    body = 0
    for name, p in net.named_parameters():
        if not p.requires_grad or name.startswith("fc."):
            continue
        in_attn = any(k in name for k in ("channel_gate", "spatial_gate", "attn."))
        if in_attn:
            attn += p.numel()
        else:
            body += p.numel()
    return {"head": head, "attention": attn, "backbone(body)": body}


if __name__ == "__main__":
    torch.manual_seed(1234)
    for attn in ("none", "se", "cbam"):
        net = build_resnet50_attn(freeze=True, attn_type=attn)
        g = count_params_by_group(net)
        x = torch.randn(2, 3, 224, 224)
        y = net(x)
        print(f"attn={attn:<5}  前向 {tuple(y.shape)}  可训练: head={g['head'] / 1e3:.1f}K "
              f"attn={g['attention'] / 1e3:.1f}K body={g['backbone(body)'] / 1e3:.1f}K")
