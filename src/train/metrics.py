"""模型评估指标（医学场景必须多指标，不能只看 Accuracy）。

⚠️ 别被"假基线"迷惑：全猜 PNEUMONIA 即可得 72.9% Accuracy，
   因此必须同时报告 Precision / Recall / F1 / AUC / 混淆矩阵，
   且医学场景漏诊代价最高 —— PNEUMONIA 的 Recall（灵敏度）为第一优先指标。
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    auc,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)

CLASSES = ["NORMAL", "PNEUMONIA"]


def compute_metrics(y_true: list[int], y_pred: list[int], y_prob1: list[float]) -> dict:
    """计算二分类的全部核心指标。

    Args:
        y_true : 真实标签（0=NORMAL, 1=PNEUMONIA）
        y_pred : 预测标签
        y_prob1 : PNEUMONIA 类概率（用于 AUC / 最佳阈值）
    Returns:
        dict：accuracy / precision / recall / f1（macro） / auc /
              confusion_matrix / per-class P & R & F1 / best_threshold & best_f1
    """
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    y_prob1 = np.asarray(y_prob1)

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])

    # 在验证集上搜索 F1 最优阈值（类别不平衡时默认 0.5 往往不是最优）
    prec_curve, rec_curve, thr = precision_recall_curve(y_true, y_prob1)
    f1_curve = np.divide(
        2 * prec_curve[:-1] * rec_curve[:-1],
        np.maximum(prec_curve[:-1] + rec_curve[:-1], 1e-9),
    )
    best_idx = int(np.argmax(f1_curve))
    best_threshold = float(thr[best_idx]) if len(thr) else 0.5
    best_f1_at_thr = float(f1_curve[best_idx])

    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision_score(y_true, y_pred, average="macro", zero_division=0)),
        "recall_macro": float(recall_score(y_true, y_pred, average="macro", zero_division=0)),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "auc": float(roc_auc_score(y_true, y_prob1)),
        "ap": float(auc(rec_curve, prec_curve)),
        "confusion_matrix": cm.tolist(),
        "per_class": {
            CLASSES[0]: {
                "precision": float(precision_score(y_true, y_pred, pos_label=0, zero_division=0)),
                "recall": float(recall_score(y_true, y_pred, pos_label=0, zero_division=0)),
                "f1": float(f1_score(y_true, y_pred, pos_label=0, zero_division=0)),
            },
            CLASSES[1]: {
                "precision": float(precision_score(y_true, y_pred, pos_label=1, zero_division=0)),
                "recall": float(recall_score(y_true, y_pred, pos_label=1, zero_division=0)),
                "f1": float(f1_score(y_true, y_pred, pos_label=1, zero_division=0)),
            },
        },
        "best_threshold": best_threshold,
        "best_f1_at_thr": best_f1_at_thr,
    }


def format_metrics(m: dict, title: str = "评估结果") -> str:
    """把 metrics dict 格式化成人可读的表格文本。"""
    cm = m["confusion_matrix"]
    lines = [
        f"── {title} ─────────────────────────",
        f"  Accuracy          : {m['accuracy']:.4f}",
        f"  Precision(macro)  : {m['precision_macro']:.4f}",
        f"  Recall(macro)     : {m['recall_macro']:.4f}",
        f"  F1(macro)         : {m['f1_macro']:.4f}",
        f"  AUC               : {m['auc']:.4f}",
        f"  ── 按类别 ──",
    ]
    for c in CLASSES:
        d = m["per_class"][c]
        lines.append(f"    {c:<10}  P={d['precision']:.4f}  R={d['recall']:.4f}  F1={d['f1']:.4f}")
    lines += [
        "  ── 混淆矩阵（行=真实，列=预测，顺序 NORMAL, PNEUMONIA）──",
        f"    {cm[0][0]:>6}  {cm[0][1]:>6}",
        f"    {cm[1][0]:>6}  {cm[1][1]:>6}",
        f"  最佳 F1 阈值      : {m['best_threshold']:.4f}（该阈值下 F1={m['best_f1_at_thr']:.4f}）",
    ]
    return "\n".join(lines)
