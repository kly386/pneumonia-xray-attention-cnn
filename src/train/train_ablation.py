"""实验 E2 注意力消融训练入口（单变量对照）。

对照声明：
    E2 的"none"组 = 已冻结的保底基线（configs 与本脚本完全一致：两阶段 A3+B≤15、
    AdamW+余弦、加权 CE、seed=1234、增强仅 train、val F1 选模 + 早停 patience=4）。
    故默认**不重跑 none**，直接引用其结果（来源 reports/model_baseline.md，人工抄录），
    每次只增训一条注意力变体 —— 严格满足"一次只改一个变量"。

命令（conda pytorch 环境，仓库根目录）：
    C:\\Users\\29542\\.conda\\envs\\pytorch\\python.exe -m src.train.train_ablation --attn se
    C:\\Users\\29542\\.conda\\envs\\pytorch\\python.exe -m src.train.train_ablation --attn cbam
可选：
    --epochs-a 3 --epochs-b 15 --patience 4 --batch-size 32
    --positions layer3,layer4     # 注意力插入位置（默认保底组合，勿轻易改）
    --identity-init               # CBAM v2：门控恒等初始化（修复 v1 空间门噪声窗塌方）
    --lr-attn 1e-4                # CBAM v3：注意力参数单列一组、降学习率（修复阶段B震荡）
    --rerun-none                  # 如需在本脚本内复跑 none 对照

产出：
    models/checkpoints/resnet50_{attn}_v1.pt（朴素）/ _v2.pt（恒等初始化）/ _v3.pt（+lr-attn）
    + 对应 log{A,B}.json；reports/model_E2_attention.md（消融表，自动累计追加）
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import torch

from src.train import common
from src.train.attention import build_resnet50_attn, count_params_by_group
from src.train.metrics import compute_metrics, format_metrics
from src.train.model import param_groups
from src.train import train_baseline as tb

# 基线（none）指标 —— 来自 reports/model_baseline.md（2026-11-02 冻结版），人工抄录勿改
BASELINE_ROW = {
    "variant": "none(基线)",
    "ckpt": "resnet50_baseline.pt",
    "val_f1": 0.9826,
    "val_epochs": "A3 + B6(best)/10(早停)",
    "test": {
        "accuracy": 0.9743, "f1_macro": 0.9675, "auc": 0.9946,
        "prec_macro": 0.9666, "rec_macro": 0.9684,
        "pn_rec": 0.9812,  # PNEUMONIA Recall（灵敏度）
    },
}

ABLATION_JSON = common.REPORT_DIR / "e2_ablation_results.json"
ABLATION_MD = common.REPORT_DIR / "model_E2_attention.md"


def load_rows() -> list[dict]:
    if ABLATION_JSON.exists():
        return json.loads(ABLATION_JSON.read_text(encoding="utf-8"))
    return [dict(BASELINE_ROW)]


def save_rows(rows: list[dict]) -> None:
    ABLATION_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def write_md(rows: list[dict]) -> None:
    lines = [
        "# 实验 E2 · 注意力消融（ResNet50 baseline vs +SE vs +CBAM）",
        "",
        f"> 数据 seed=1234（8:1:1 与基线完全一致）；训练协议两阶段 A3+B≤15（val F1 选模+早停4）；"
        f"插入位置默认 layer3+layer4；基线指标抄录自 reports/model_baseline.md（冻结版）。",
        "",
        "| 变体 | 骨干可训练参数(K) | 注意力参数(K) | 最佳 val F1 | test Acc | test F1 | test AUC | P-Recall(灵敏度) | checkpoint |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        t = r.get("test", {})
        lines.append(
            f"| {r['variant']} | {r.get('body_k', '—')} | {r.get('attn_k', '—')} "
            f"| {r.get('val_f1', '—')} | {t.get('accuracy', '—')} | {t.get('f1_macro', '—')} "
            f"| {t.get('auc', '—')} | {t.get('pn_rec', '—')} | {r['ckpt']} |"
        )
    lines += [
        "",
        "## 结论模板（训练完成后按数据改写，勿空泛）",
        "- 注意力模块带来/未带来 val F1 的变化幅度：__",
        "- 混淆矩阵变化（NORMAL 误报数 / PNEUMONIA 漏诊数）：__",
        "- 参数量代价：注意力模块仅 __K（占全网 23.5M 的 __%），性价比结论：__",
        "",
        f"_更新时间：{time.strftime('%Y-%m-%d %H:%M')}_",
    ]
    ABLATION_MD.write_text("\n".join(lines), encoding="utf-8")


def run_one_variant(attn: str, args) -> None:
    c = common
    c.set_seed(c.SEED)
    c.CKPT_DIR.mkdir(parents=True, exist_ok=True)

    # v1 = 朴素随机初始化；v2 = 恒等初始化；v3 = 恒等初始化 + 注意力降学习率
    ident = args.identity_init
    if args.lr_attn is not None:
        tag = "v3"
        variant_label = f"{attn.upper()} v3(恒等初始化+attn-lr={args.lr_attn:g})"
    elif ident:
        tag = "v2"
        variant_label = f"{attn.upper()} v2(恒等初始化)"
    else:
        tag = "v1"
        variant_label = attn.upper()
    if ident and attn == "se":
        print("提示: SE 没有空间门，--identity-init 对 SE 结构上无改动（等价 v1）", flush=True)

    train_loader, val_loader, test_loader = c.build_loaders(args.batch_size, args.num_workers)

    print(f"\n################ 变体 attn={attn}  tag={tag}  identity_init={ident} ################", flush=True)

    # ---------- 阶段 A ----------
    model_a = build_resnet50_attn(freeze=True, dropout=0.3, attn_type=attn,
                                  positions=tuple(args.positions),
                                  identity_init=ident).to(c.DEVICE)
    groups_info = count_params_by_group(model_a)
    print(f"[A前自检] 可训练参数: {groups_info}", flush=True)

    best_a, _ = tb.train_stage(
        model_a, train_loader, val_loader, f"{attn}{tag}-StageA",
        epochs=args.epochs_a, lr_body=0.0, lr_head=args.lr_head,
        patience=args.patience, freeze=True,
        log_path=c.CKPT_DIR / f"resnet50_{attn}_{tag}_logA.json",
    )
    print(f"阶段 A 最佳 val F1 = {best_a['f1']:.4f} (epoch {best_a['epoch']})", flush=True)

    # ---------- 阶段 B ----------
    model_b = build_resnet50_attn(freeze=False, dropout=0.3, attn_type=attn,
                                  positions=tuple(args.positions),
                                  identity_init=ident).to(c.DEVICE)
    model_b.load_state_dict(best_a["state"], strict=True)
    best_b, _ = tb.train_stage(
        model_b, train_loader, val_loader, f"{attn}{tag}-StageB",
        epochs=args.epochs_b, lr_body=args.lr_body, lr_head=args.lr_head * 0.1,
        patience=args.patience, freeze=False,
        log_path=c.CKPT_DIR / f"resnet50_{attn}_{tag}_logB.json",
        lr_attn=args.lr_attn,
    )
    print(f"阶段 B 最佳 val F1 = {best_b['f1']:.4f} (epoch {best_b['epoch']})", flush=True)

    # ---------- 保存最优 ----------
    ckpt_path = c.CKPT_DIR / f"resnet50_{attn}_{tag}.pt"
    torch.save({
        "model_state": best_b["state"],
        "arch": "resnet50_attn",
        "attn": attn,
        "init": "identity" if ident else "plain",
        "lr_attn": args.lr_attn,
        "positions": list(args.positions),
        "val_f1": best_b["f1"],
        "best_threshold": best_b["threshold"],
        "seed": c.SEED,
    }, ckpt_path)
    print(f"已保存: {ckpt_path}", flush=True)

    # ---------- test 一次性评估 ----------
    model_final = build_resnet50_attn(freeze=False, dropout=0.3, attn_type=attn,
                                      positions=tuple(args.positions),
                                      identity_init=ident).to(c.DEVICE)
    model_final.load_state_dict(best_b["state"], strict=True)
    criterion = c.make_loss()
    te = tb.run_epoch(model_final, test_loader, criterion, optimizer=None, scaler=None)
    print("\n" + format_metrics(te, title=f"{variant_label} · TEST（val F1={best_b['f1']:.4f}）"), flush=True)

    # ---------- 写入消融表 ----------
    rows = load_rows()
    per_class = te["per_class"]
    rows.append({
        "variant": variant_label,
        "ckpt": ckpt_path.name,
        "body_k": f"{groups_info['backbone(body)'] / 1e3:.0f}",
        "attn_k": f"{groups_info['attention'] / 1e3:.1f}",
        "val_f1": round(best_b["f1"], 4),
        "val_epochs": f"A3 + B{best_b['epoch']}",
        "test": {
            "accuracy": round(te["accuracy"], 4),
            "f1_macro": round(te["f1_macro"], 4),
            "auc": round(te["auc"], 4),
            "prec_macro": round(te["precision_macro"], 4),
            "rec_macro": round(te["recall_macro"], 4),
            "pn_rec": round(per_class[common.CLASSES[1]]["recall"], 4),
        },
    })
    save_rows(rows)
    write_md(rows)
    print(f"消融表已更新: {ABLATION_MD}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attn", choices=["se", "cbam", "rerun-none"],
                        required=True, help="本次训练的单一变量")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--num-workers", type=int, default=2)
    parser.add_argument("--epochs-a", type=int, default=3)
    parser.add_argument("--epochs-b", type=int, default=15)
    parser.add_argument("--patience", type=int, default=4)
    parser.add_argument("--lr-head", type=float, default=1e-3)
    parser.add_argument("--lr-body", type=float, default=3e-4)
    parser.add_argument("--positions", default="layer3,layer4")
    parser.add_argument("--identity-init", action="store_true",
                        help="CBAM v2：门控恒等初始化（空间/通道门初始≈全通）")
    parser.add_argument("--lr-attn", type=float, default=None,
                        help="注意力参数独立学习率（CBAM v3：单列一组，默认 None=与骨干同组）")
    args = parser.parse_args()
    args.positions = args.positions.split(",")

    if args.attn == "rerun-none":
        # 复跑一个纯净的 none 对照（一般不需要；baseline 已在相同协议下产出）
        run_one_variant("none", args)
    else:
        run_one_variant(args.attn, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
