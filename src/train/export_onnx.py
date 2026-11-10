"""E7：ONNX 导出 + 量化对比（成员3：伍梦圆，P0 任务）。

交付物（models/onnx/，*.onnx 已在 .gitignore，需要时走网盘/群文件给联调组）:
    resnet50_baseline.onnx            FP32 全精度（必交，联调主用）
    resnet50_baseline_int8_dyn.onnx   动态量化（权重 int8，仅 Gemm/MatMul）
    resnet50_baseline_int8_sta.onnx   （附）静态量化 QDQ 全网 int8，真压缩
    
对比维度:
    - 体积（.pt / onnx fp32 / 动态 int8 / 静态 int8）
    - CPU 推理时延（onnxruntime，批量 1，与后端部署形态一致；含 torch CPU 基线）
    - logits 数值一致性（与 torch 相对最大误差）
    - （数据到位后）val 精度无退化验证：--eval-dir data/processed/val

量化避坑记录（给后来人）:
    - quantize_dynamic 默认会把 Conv 也转成 ConvInteger，而 onnxruntime CPU
      **不支持 ConvInteger**（报 NOT_IMPLEMENTED），CNN 下必须限定只量化
      Gemm/MatMul（这本来就是动态量化的官方适用范围）
    - 要真正压缩 CNN 卷积，走静态量化（QDQ 格式，QLinearConv 全部支持）；
      校准集用随机张量即可先出对比表，数据到位后可用样张校准重新量化

输入/输出约定（对齐 logs/mj.md 第四节，联调以此为准）:
    - 输入名 "images"：(B, 3, 224, 224) float32，ImageNet 归一化
    - 输出名 "logits"：(B, 2)，索引 0=NORMAL、1=PNEUMONIA；
      后端取 softmax(logits)[1] 与 checkpoint 阈值(0.5101) 判定
    - batch 动轴，后端可自由改批大小

用法（dl-env 环境，仓库根目录）:
    D:\\Miniconda3\\envs\\dl-env\\python.exe -m src.train.export_onnx
    数据到位后补精度对比:
    ... --eval-dir data/processed/val
    其他 checkpoint:
    ... --ckpt models/checkpoints/resnet50_cbam_v1.pt
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import onnx
import torch
from onnxruntime import InferenceSession, SessionOptions
from onnxruntime.quantization import (CalibrationDataReader, CalibrationMethod,
                                      QuantFormat, QuantType,
                                      quantize_dynamic, quantize_static)
from torchvision import datasets
from torch.utils.data import DataLoader

from src.train import common
from src.train.predict import load_model

ONNX_DIR = common.CKPT_DIR.parent / "onnx"
IMG_NAME, OUT_NAME = "images", "logits"


def export_onnx(net, ckpt_name: str, opset: int) -> Path:
    """导出 FP32 ONNX（logits 版本，batch 动轴，softmax 由后端算）。"""
    net = net.cpu().eval()
    dummy = torch.randn(1, 3, common.IMG_SIZE, common.IMG_SIZE)
    onnx_path = ONNX_DIR / f"{ckpt_name}.onnx"
    torch.onnx.export(
        net, dummy, str(onnx_path),
        input_names=[IMG_NAME], output_names=[OUT_NAME],
        dynamic_axes={IMG_NAME: {0: "batch"}, OUT_NAME: {0: "batch"}},
        opset_version=opset, dynamo=False,
    )
    return onnx_path


def make_session(path: Path, threads: int) -> InferenceSession:
    so = SessionOptions()
    so.intra_op_num_threads = threads
    return InferenceSession(str(path), so,
                            providers=["CPUExecutionProvider"])


def quantize_dynamic_gemm(onnx_path: Path) -> Path:
    """动态量化（权重 int8）：仅 Gemm/MatMul 节点。

    动态量化官方适用范围就是矩阵乘（Transformer/Linear）；CNN 的 Conv
    若一并量化会得到 ConvInteger，onnxruntime CPU 不支持（见文件头避坑记录）。
    """
    model = onnx.load(str(onnx_path))
    nodes = [n.name for n in model.graph.node if n.op_type in ("Gemm", "MatMul")]
    out = ONNX_DIR / f"{onnx_path.stem}_int8_dyn.onnx"
    quantize_dynamic(str(onnx_path), str(out), weight_type=QuantType.QInt8,
                     nodes_to_quantize=nodes)
    return out


class _CalibReader(CalibrationDataReader):
    """静态量化校准数据：优先用真实 val 样张（或指定样张目录），
    找不到目录时退回随机张量（仅应急，精度口径不可信，见文件头避坑记录）。"""

    def __init__(self, calib_dir: Path | None = None, n: int = 64):
        self._iter = None
        self._items: list[np.ndarray] = []
        self._i = 0
        if calib_dir and calib_dir.exists():
            ds = datasets.ImageFolder(calib_dir, transform=common.eval_tf)
            m = min(n, len(ds))
            for k in range(m):
                img, _ = ds[k]
                self._items.append(img.numpy()[None])
            self._items = self._items[:m]
        if not self._items:
            self._items = [np.random.randn(1, 3, common.IMG_SIZE, common.IMG_SIZE
                                           ).astype(np.float32)
                           for _ in range(n)]

    def get_next(self):
        if self._i >= len(self._items):
            return None
        out = {IMG_NAME: self._items[self._i]}
        self._i += 1
        return out

    def rewind(self):
        self._i = 0


def quantize_static_qdq(onnx_path: Path, calib_dir: Path | None = None) -> Path:
    """静态量化（QDQ 全网 int8）：对 CNN 真正有效的压缩/加速路径。"""
    out = ONNX_DIR / f"{onnx_path.stem}_int8_sta.onnx"
    quantize_static(str(onnx_path), str(out), _CalibReader(calib_dir),
                    quant_format=QuantFormat.QDQ,
                    activation_type=QuantType.QInt8,
                    weight_type=QuantType.QInt8,
                    per_channel=True,
                    calibrate_method=CalibrationMethod.MinMax)
    return out


@torch.no_grad()
def verify_consistency(net, onnx_path: Path) -> float:
    """torch vs ort 同输入最大绝对误差（FP32 应回到 1e-4 级以内）。"""
    sess = make_session(onnx_path, threads=1)
    max_diff = 0.0
    for _ in range(3):
        x = torch.randn(1, 3, common.IMG_SIZE, common.IMG_SIZE)
        ref = net(x).detach().numpy()
        got = sess.run(None, {IMG_NAME: x.numpy()})[0]
        max_diff = max(max_diff, float(np.abs(ref - got).max()))
    return max_diff


def bench_latency(net, res: dict[str, Path], runs: int, threads: int
                  ) -> dict[str, float]:
    """批量 1 CPU 时延（ms/张）：预热 10 次 + 计时 runs 次。"""
    x = np.random.randn(1, 3, common.IMG_SIZE, common.IMG_SIZE).astype(np.float32)
    lat = {}
    # torch CPU 基线（.pt 直接推理的形态）
    net_c = net.cpu()
    for _ in range(5):
        net_c(torch.from_numpy(x))
    t0 = time.perf_counter()
    for _ in range(runs):
        net_c(torch.from_numpy(x))
    lat["pt_torch"] = (time.perf_counter() - t0) / runs * 1000
    onnx_res = {k: v for k, v in res.items() if k != "pt_torch"}
    for tag, path in onnx_res.items():
        sess = make_session(path, threads)
        for _ in range(10):
            sess.run(None, {IMG_NAME: x})
        t0 = time.perf_counter()
        for _ in range(runs):
            sess.run(None, {IMG_NAME: x})
        lat[tag] = (time.perf_counter() - t0) / runs * 1000
    return lat


@torch.no_grad()
def eval_metrics(net, threshold: float, eval_dir: Path,
                 variants: dict[str, Path]) -> dict:
    """val 精度无退化验证：torch / 各 ONNX 变体（含 int8）。"""
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

    ds = datasets.ImageFolder(eval_dir, transform=common.eval_tf)
    assert ds.classes == ["NORMAL", "PNEUMONIA"], f"目录类别异常: {ds.classes}"
    loader = DataLoader(ds, batch_size=64, shuffle=False, num_workers=0)

    sessions = {tag: make_session(p, threads=4) for tag, p in variants.items()}
    probs: dict[str, list] = {t: [] for t in ["torch", *sessions]}
    ys = []
    for imgs, labels in loader:
        imgs = imgs.cpu()
        ys.append(labels.numpy())
        probs["torch"].append(
            torch.softmax(net.cpu()(imgs), dim=1)[:, 1].numpy())
        x = imgs.numpy()
        for tag, sess in sessions.items():
            probs[tag].append(
                torch.softmax(torch.from_numpy(
                    sess.run(None, {IMG_NAME: x})[0]), dim=1)[:, 1].numpy())
    ys = np.concatenate(ys)
    out = {}
    for tag, arr in probs.items():
        p1 = np.concatenate(arr)
        pred = (p1 >= threshold).astype(int)
        out[tag] = {
            "acc": accuracy_score(ys, pred),
            "f1_macro": f1_score(ys, pred, average="macro"),
            "auc": roc_auc_score(ys, p1),
            "pneumonia_recall": (pred[ys == 1] == 1).mean(),
        }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="E7 ONNX 导出+量化对比")
    parser.add_argument("--ckpt", type=Path,
                        default=common.CKPT_DIR / "resnet50_baseline.pt")
    parser.add_argument("--opset", type=int, default=17)
    parser.add_argument("--runs", type=int, default=50, help="时延计次数")
    parser.add_argument("--threads", type=int, default=4, help="ort 单会话线程")
    parser.add_argument("--eval-dir", type=Path, default=None,
                        help="如 data/processed/val；给出则补精度对比")
    args = parser.parse_args()

    print(f"设备: {common.DEVICE}")
    net, threshold, name = load_model(args.ckpt)
    print(f"模型: {name}  阈值(checkpoint/val 选定): {threshold:.4f}\n")

    ONNX_DIR.mkdir(parents=True, exist_ok=True)

    print("1) 导出 FP32...")
    onnx_path = export_onnx(net, Path(args.ckpt).stem, args.opset)
    print(f"   -> {onnx_path}")
    diff = verify_consistency(net, onnx_path)
    print(f"   torch vs ort 最大误差 = {diff:.2e}")

    print("2) 动态量化（仅 Gemm/MatMul，ConvInteger 不被 CPU 支持的避坑）...")
    dyn_path = quantize_dynamic_gemm(onnx_path)
    diff_d = verify_consistency(net, dyn_path)
    print(f"   -> {dyn_path}  (误差 {diff_d:.2e})")

    print("3) 静态量化（QDQ 全网 int8，真样张校准）...")
    sta_path = quantize_static_qdq(onnx_path, args.eval_dir)
    diff_s = verify_consistency(net, sta_path)
    print(f"   -> {sta_path}  (误差 {diff_s:.2e})")

    variants = {"pt_torch": args.ckpt, "onnx_fp32": onnx_path,
                "onnx_int8_dyn": dyn_path, "onnx_int8_sta": sta_path}
    sizes = {t: p.stat().st_size / 1e6 for t, p in variants.items()}
    print("4) 体积: " + "  ".join(f"{k}={v:.1f}MB" for k, v in sizes.items()))

    lat = bench_latency(net, variants, args.runs, args.threads)
    print("5) CPU 时延(批量1): " + "  ".join(f"{k}={v:.2f}ms"
                                           for k, v in lat.items()))

    if args.eval_dir and args.eval_dir.exists():
        print(f"6) 精度对比({args.eval_dir}):")
        for tag, m in eval_metrics(net, threshold, args.eval_dir,
                                   {"fp32": onnx_path, "int8_dyn": dyn_path,
                                    "int8_sta": sta_path}).items():
            print(f"   {tag:8}: acc={m['acc']:.4f} f1={m['f1_macro']:.4f} "
                  f"auc={m['auc']:.4f} p_recall={m['pneumonia_recall']:.4f}")
    else:
        print("6) 精度对比跳过（data/processed 未到位；数据到手后 "
              "--eval-dir data/processed/val 补一遍）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
