"""ONNX 模型加载与单张胸片推理模块。"""

from __future__ import annotations

import logging
import threading
import uuid
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import onnxruntime as ort
from PIL import Image, UnidentifiedImageError
from torchvision import transforms

logger = logging.getLogger(__name__)

# 项目根目录：src/backend/model_loader.py -> parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = PROJECT_ROOT / "models" / "onnx" / "resnet50_baseline.onnx"
TORCH_MODEL_PATH = PROJECT_ROOT / "models" / "checkpoints" / "resnet50_baseline.pt"
HEATMAP_DIR = Path(__file__).resolve().parent / "uploads" / "heatmaps"

INPUT_NAME = "images"
OUTPUT_NAME = "logits"
PNEUMONIA_THRESHOLD = 0.5101
IMG_SIZE = 224

# 严格按训练/部署约定构造预处理流程。
_transform = transforms.Compose(
    [
        transforms.Grayscale(num_output_channels=3),
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ]
)

_session: Optional[ort.InferenceSession] = None
_session_lock = threading.Lock()

_torch_model = None
_torch_model_loaded = False
_torch_lock = threading.Lock()


def load_model() -> ort.InferenceSession:
    """加载并缓存 ONNX 会话；重复调用时直接返回已有会话。"""

    global _session

    if _session is not None:
        return _session

    with _session_lock:
        if _session is not None:
            return _session

        if not MODEL_PATH.is_file():
            raise FileNotFoundError(f"ONNX 模型文件不存在：{MODEL_PATH}")

        try:
            options = ort.SessionOptions()
            options.intra_op_num_threads = 4
            options.inter_op_num_threads = 1
            session = ort.InferenceSession(
                str(MODEL_PATH),
                sess_options=options,
                providers=["CPUExecutionProvider"],
            )
        except Exception as exc:
            raise RuntimeError(f"ONNX 模型加载失败：{exc}") from exc

        input_names = [item.name for item in session.get_inputs()]
        output_names = [item.name for item in session.get_outputs()]

        if INPUT_NAME not in input_names:
            raise RuntimeError(
                f"ONNX 输入名不匹配，期望 {INPUT_NAME}，实际 {input_names}"
            )
        if OUTPUT_NAME not in output_names:
            raise RuntimeError(
                f"ONNX 输出名不匹配，期望 {OUTPUT_NAME}，实际 {output_names}"
            )

        _session = session
        return _session


def _get_session() -> ort.InferenceSession:
    """获取已加载的会话；若启动阶段未加载则延迟加载一次。"""

    if _session is None:
        return load_model()
    return _session


def predict_image(image_bytes: bytes) -> Tuple[str, float, float]:
    """对单张图片执行推理。

    返回：
        (预测类别, 判定类别置信度, 肺炎概率)

    类别顺序与模型输出一致：索引 0 = NORMAL，索引 1 = PNEUMONIA。
    """

    if not image_bytes:
        raise ValueError("图片二进制数据为空")

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            # Grayscale 会统一处理 RGB、L、RGBA 等常见模式。
            tensor = _transform(image).unsqueeze(0)
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("无法解析图片内容") from exc

    input_array = np.ascontiguousarray(tensor.numpy(), dtype=np.float32)

    try:
        outputs = _get_session().run(
            [OUTPUT_NAME],
            {INPUT_NAME: input_array},
        )
    except Exception as exc:
        raise RuntimeError(f"ONNX 推理失败：{exc}") from exc

    logits = np.asarray(outputs[0], dtype=np.float64)
    if logits.ndim == 2:
        if logits.shape[0] != 1 or logits.shape[1] != 2:
            raise RuntimeError(f"ONNX 输出形状异常：{logits.shape}")
        row = logits[0]
    else:
        row = logits.reshape(-1)
        if row.size != 2:
            raise RuntimeError(f"ONNX 输出形状异常：{logits.shape}")

    # 数值稳定的 Softmax。
    shifted = row - np.max(row)
    exp_values = np.exp(shifted)
    probabilities = exp_values / np.sum(exp_values)

    prob_normal = float(probabilities[0])
    prob_pneumonia = float(probabilities[1])

    if prob_pneumonia >= PNEUMONIA_THRESHOLD:
        label = "PNEUMONIA"
        confidence = prob_pneumonia
    else:
        label = "NORMAL"
        confidence = prob_normal

    return label, float(confidence), float(prob_pneumonia)


# ---------------------------------------------------------------------------
# Grad-CAM 热力图
# ---------------------------------------------------------------------------
def _softmax(logits: np.ndarray) -> np.ndarray:
    """对一维 logits 做数值稳定 Softmax。"""

    shifted = logits - np.max(logits)
    exp_values = np.exp(shifted)
    return exp_values / np.sum(exp_values)


def _build_torch_model():
    """按训练脚本的架构重建 PyTorch 模型（不下载预训练权重）。"""

    import torch.nn as nn
    from torchvision import models

    from src.train.attention import build_resnet50_attn

    checkpoint = _torch_load(TORCH_MODEL_PATH)
    state_dict = (
        checkpoint.get("model_state")
        or checkpoint.get("state_dict")
        or checkpoint
    )

    attn_type = str(checkpoint.get("attn", "")).lower()
    if attn_type in {"se", "cbam"}:
        net = build_resnet50_attn(freeze=False, attn_type=attn_type)
    else:
        net = models.resnet50(weights=None)
        net.fc = nn.Sequential(
            nn.Dropout(0.3),
            nn.Linear(net.fc.in_features, 2),
        )

    net.load_state_dict(state_dict, strict=True)
    net.eval()
    return net


def _torch_load(path: Path):
    """加载 .pt checkpoint。"""

    import torch

    return torch.load(path, map_location="cpu", weights_only=True)


def _get_torch_model():
    """惰性加载 PyTorch 模型；.pt 缺失或无法加载时返回 None。"""

    global _torch_model, _torch_model_loaded

    if _torch_model_loaded:
        return _torch_model

    with _torch_lock:
        if _torch_model_loaded:
            return _torch_model

        _torch_model_loaded = True
        if not TORCH_MODEL_PATH.is_file():
            logger.warning(
                "PyTorch checkpoint 不存在，Grad-CAM 将退回 ONNX 遮挡分析：%s",
                TORCH_MODEL_PATH,
            )
            return None

        try:
            _torch_model = _build_torch_model()
        except Exception:
            logger.exception("PyTorch 模型加载失败，Grad-CAM 将退回 ONNX 遮挡分析")
            _torch_model = None

        return _torch_model


def _jet(gray01: np.ndarray) -> np.ndarray:
    """灰度热力 -> Jet 伪彩色 RGB（0~1 float）。"""

    import matplotlib

    cmap = matplotlib.colormaps["jet"]
    return np.asarray(cmap(gray01))[:, :, :3]


def _gradcam_cam(net, tensor):
    """在 layer4[-1] 上计算真实 Grad-CAM（返回 7x7 或对应尺寸的归一化热力）。"""

    import torch

    target_layer = net.layer4[-1]
    captured: dict[str, "torch.Tensor"] = {}

    def _forward_hook(_module, _inputs, output):
        captured["activation"] = output
        output.register_hook(
            lambda gradient: captured.__setitem__("gradient", gradient)
        )

    handle = target_layer.register_forward_hook(_forward_hook)
    try:
        net.zero_grad(set_to_none=True)
        logits = net(tensor)
        target_class = int(logits.argmax(dim=1).item())
        logits[0, target_class].backward()
    finally:
        handle.remove()

    activation = captured.get("activation")
    gradient = captured.get("gradient")
    if activation is None or gradient is None:
        raise RuntimeError("Grad-CAM 未捕获到目标层激活或梯度")

    activation = activation.detach()[0]
    gradient = gradient.detach()[0]
    weights = gradient.mean(dim=(1, 2))
    cam = torch.relu((weights[:, None, None] * activation).sum(dim=0))
    cam = cam.cpu().numpy().astype(np.float32)

    cam_min = float(cam.min())
    cam_max = float(cam.max())
    if cam_max - cam_min > 1e-8:
        cam = (cam - cam_min) / (cam_max - cam_min)
    else:
        cam = np.zeros_like(cam)
    return cam


def _onnx_occlusion_cam(tensor, grid: int = 7):
    """ONNX 无法直接求梯度时的遮挡敏感度近似热力图（梯度无关兜底）。"""

    session = _get_session()
    input_array = np.ascontiguousarray(tensor.numpy(), dtype=np.float32)
    base_logits = session.run([OUTPUT_NAME], {INPUT_NAME: input_array})[0][0]
    base_probs = _softmax(np.asarray(base_logits, dtype=np.float64))
    target_class = 1 if base_probs[1] >= PNEUMONIA_THRESHOLD else 0
    base_score = float(base_probs[target_class])

    cam = np.zeros((grid, grid), dtype=np.float32)
    patch = max(1, IMG_SIZE // grid)
    for row in range(grid):
        for col in range(grid):
            occluded = input_array.copy()
            top = row * patch
            left = col * patch
            occluded[:, :, top : top + patch, left : left + patch] = 0.0
            logits = session.run([OUTPUT_NAME], {INPUT_NAME: occluded})[0][0]
            score = float(_softmax(np.asarray(logits, dtype=np.float64))[target_class])
            cam[row, col] = max(0.0, base_score - score)

    cam_max = float(cam.max())
    if cam_max > 1e-8:
        cam /= cam_max
    return cam


def _resize_cam(cam: np.ndarray, size: Tuple[int, int]) -> np.ndarray:
    """将低分辨率 CAM 双线性插值到原图尺寸，返回 0~1 float。"""

    width, height = size
    cam_img = Image.fromarray((np.clip(cam, 0.0, 1.0) * 255).astype(np.uint8))
    cam_img = cam_img.resize((width, height), Image.BILINEAR)
    return np.asarray(cam_img, dtype=np.float32) / 255.0


def generate_gradcam(image_bytes: bytes) -> Optional[str]:
    """为单张胸片生成 Grad-CAM 热力图并保存为 JPG。

    优先使用 PyTorch `.pt` checkpoint 计算真实梯度；若 checkpoint 缺失，
    则退回 ONNX 遮挡敏感度近似，保证接口始终能返回热力图。

    返回：
        保存的文件名（位于 uploads/heatmaps/ 下）；失败时返回 None。
    """

    if not image_bytes:
        return None

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            gray_image = image.convert("L")
            original_size = image.size
            tensor = _transform(gray_image).unsqueeze(0)
    except (UnidentifiedImageError, OSError, ValueError):
        logger.warning("Grad-CAM 输入图片解析失败")
        return None

    try:
        net = _get_torch_model()
        with _torch_lock:
            if net is not None:
                cam = _gradcam_cam(net, tensor)
            else:
                cam = _onnx_occlusion_cam(tensor)

        cam_resized = _resize_cam(cam, original_size)
        from PIL import ImageFilter

        smoothed = Image.fromarray(
            (np.clip(cam_resized, 0.0, 1.0) * 255).astype(np.uint8)
        ).filter(ImageFilter.GaussianBlur(radius=7))
        cam_resized = np.asarray(smoothed, dtype=np.float32) / 255.0
        heatmap_rgb = (_jet(cam_resized) * 255.0).clip(0, 255).astype(np.uint8)

        HEATMAP_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4()}.jpg"
        Image.fromarray(heatmap_rgb, mode="RGB").save(
            HEATMAP_DIR / filename,
            format="JPEG",
            quality=92,
        )
        return filename
    except Exception:
        logger.exception("Grad-CAM 热力图生成失败")
        return None