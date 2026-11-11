"""单图推理试车台（成员2自用：验证训练好的模型"到底灵不灵"）。

用法（conda pytorch 环境，仓库根目录）：
    C:\\Users\\29542\\.conda\\envs\\pytorch\\python.exe -m src.train.predict --image 某张X光片.jpg
    多张一起验:
    ... --image a.jpg --image b.jpg --image c.jpg
    试 SE/CBAM 变体:
    ... --ckpt models/checkpoints/resnet50_se_v1.pt --image xxx.jpg

说明：
    - 预处理与训练验证集完全一致（common.py::eval_tf，确定性变换）
    - 判定阈值用 checkpoint 里 val 上选定的阈值（与部署约定一致），同时打印 0.5 口径做对照
    - Grad-CAM 热力图可视化属成员3（伍梦圆）的职责，本脚本只输出数值结果
"""
from __future__ import annotations

import argparse
from pathlib import Path

import torch
from PIL import Image

from src.train import common
from src.train.attention import build_resnet50_attn
from src.train.model import build_resnet50


def load_model(ckpt_path: Path):
    """载入 checkpoint 并按架构元数据重建网络。返回 (model, threshold, 文件名)."""
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    attn = ckpt.get("attn", "")
    net = (build_resnet50_attn(freeze=False, attn_type=attn)
           if attn in ("se", "cbam") else
           build_resnet50(freeze=False))
    net.load_state_dict(ckpt["model_state"], strict=True)
    net.to(common.DEVICE).eval()
    # 兼容两代键名：训练脚本存 best_threshold（val 上选定）
    threshold = float(ckpt.get("best_threshold", ckpt.get("threshold", 0.5)))
    return net, threshold, Path(ckpt_path).name


@torch.no_grad()
def predict_one(net, img_path: Path, threshold: float) -> dict:
    img = Image.open(img_path).convert("L")           # X 光转灰度
    x = common.eval_tf(img).unsqueeze(0).to(common.DEVICE)
    p1 = torch.softmax(net(x), dim=1)[0, 1].item()    # PNEUMONIA 概率
    return {
        "file": img_path.name,
        "p_normal": 1 - p1,
        "p_pneumonia": p1,
        "verdict_thr": "PNEUMONIA" if p1 >= threshold else "NORMAL",
        "verdict_050": "PNEUMONIA" if p1 >= 0.5 else "NORMAL",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="单图试车")
    parser.add_argument("--ckpt", type=Path,
                        default=common.CKPT_DIR / "resnet50_baseline.pt")
    parser.add_argument("--image", action="append", required=True,
                        help="要检验的图片路径，可传多次判多张")
    args = parser.parse_args()

    print(f"设备: {common.DEVICE}")
    net, threshold, name = load_model(args.ckpt)
    print(f"模型: {name}  阈值(checkpoint/val 选定): {threshold:.4f}\n")

    results = [predict_one(net, Path(p), threshold) for p in args.image]
    print(f"{'文件':<42}{'P(正常)':>9}{'P(肺炎)':>9}  {'判(阈值)':<12}{'判(0.5)'}")
    print("-" * 86)
    for r in results:
        print(f"{r['file']:<42}{r['p_normal']:>9.4f}{r['p_pneumonia']:>9.4f}  "
              f"{r['verdict_thr']:<12}{r['verdict_050']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
