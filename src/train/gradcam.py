"""Grad-CAM 可视化（成员3：伍梦圆，P0 任务）。

约定（全部对齐 logs/mj.md 第四节交接，勿改）:
    - 目标层：ResNet50 的 layer4[-1]
    - 输入：224x224 三通道，ImageNet 归一化（复用 common::eval_tf）
    - 判定阈值：读 checkpoint 里 val 上选定的值（基线 = 0.5101）

用法（dl-env 环境，仓库根目录的路）:
    D:\\Miniconda3\\envs\\dl-env\\python.exe -m src.train.gradcam --image 某张X光片.jpg
    多张一起出图:
    ... --image a.jpg --image b.jpg --image c.jpg
    注意力变体 checkpoint 也支持（会自动识别 attn 类型重建网络）:
    ... --ckpt models/checkpoints/resnet50_cbam_v1.pt --image xxx.jpg

产出:
    reports/figures/gradcam/<图名>_<判定标签>__gradcam.png
    （三联：原图 | Jet 热力图 | 叠加图，图像文件夹名以判定标签区分，写报告直接用）
同时按部署约定打印推理 JSON（联调字段见 logs/mj.md 第四节第 2 点）。

注意:
    - 本脚本只出图与数值，不参与任何选模/调参（test 只评一次红线之前哨）
    - 支持负样本/难例成对出图：传 --image 负例.jpg --image 难例.jpg 依次生成
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import numpy as np
import torch
from PIL import Image
from pytorch_grad_cam import GradCAM

from src.train import common
from src.train.predict import load_model

OUT_DIR = common.REPORT_DIR / "figures" / "gradcam"


def _jet(gray01: np.ndarray) -> np.ndarray:
    """灰度热力 -> Jet 伪彩色 RGB（0~1 float）。"""
    cmap = matplotlib.colormaps["jet"]
    return np.asarray(cmap(gray01))[:, :, :3]


@torch.no_grad()
def predict_json(net, x: torch.Tensor, threshold: float, model_version: str) -> dict:
    """与部署 JSON 约定完全一致的输出（logs/mj.md 第四节第 2 点）。"""
    p1 = torch.softmax(net(x), dim=1)[0, 1].item()  # PNEUMONIA 概率
    return {
        "probs": {"NORMAL": round(1 - p1, 4), "PNEUMONIA": round(p1, 4)},
        "label": "PNEUMONIA" if p1 >= threshold else "NORMAL",
        "threshold": round(threshold, 4),
        "model_version": model_version,
    }


def process_one(net, target_layer, img_path: Path, threshold: float,
                model_version: str) -> dict:
    """单图：推理 JSON + Grad-CAM 三联图落盘。"""
    img = Image.open(img_path).convert("L")            # X 光按管道先转灰度
    x = common.eval_tf(img).unsqueeze(0).to(common.DEVICE)

    info = predict_json(net, x, threshold, model_version)

    with GradCAM(model=net, target_layers=[target_layer]) as eng:
        cam7 = eng(input_tensor=x, targets=None)[0]    # (7, 7) float

    cam224 = np.asarray(Image.fromarray((cam7 * 255).astype(np.uint8))
                        .resize((common.IMG_SIZE, common.IMG_SIZE),
                                Image.BILINEAR)) / 255.0
    gray01 = np.asarray(img.resize((common.IMG_SIZE, common.IMG_SIZE),
                                   Image.BILINEAR)) / 255.0
    rgb01 = np.stack([gray01] * 3, axis=-1)
    heat = _jet(cam224)
    overlay = np.clip(heat * 0.55 + rgb01 * 0.45, 0.0, 1.0)

    triplet = np.concatenate([rgb01, heat, overlay], axis=1)
    out_path = OUT_DIR / f"{img_path.stem}_{info['label']}__gradcam.png"
    Image.fromarray((triplet * 255).astype(np.uint8)).save(out_path)
    return {**info, "cam": out_path.name}


def main() -> int:
    parser = argparse.ArgumentParser(description="Grad-CAM 热力图可视化")
    parser.add_argument("--ckpt", type=Path,
                        default=common.CKPT_DIR / "resnet50_baseline.pt")
    parser.add_argument("--image", action="append", required=True,
                        help="X 光片路径，可传多次出多张图")
    args = parser.parse_args()

    print(f"设备: {common.DEVICE}")
    net, threshold, name = load_model(args.ckpt)
    print(f"模型: {name}  阈值(checkpoint/val 选定): {threshold:.4f}")
    target_layer = net.layer4[-1]
    print(f"目标层: layer4[-1]  ({target_layer.conv3.out_channels} ch @ 7x7)\n")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p in args.image:
        info = process_one(net, target_layer, Path(p), threshold, name)
        print(json.dumps(info, ensure_ascii=False))
    print(f"\n热力图已保存: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
