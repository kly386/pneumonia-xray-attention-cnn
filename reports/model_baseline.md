# ResNet50 保底基线 · 训练与评估

> 训练环境: conda `pytorch` (torch 2.7.1+cu118, RTX 4060 Laptop)  seed=1234

## 配置
| 参数 | 值 |
|---|---|
| 骨干 | torchvision ResNet50（ImageNet1K_V2 预训练） |
| 阶段 A | 冻结骨干，只训分类头，epochs=3，lr_head=0.001 |
| 阶段 B | 全网微调，epochs≤15，lr_body=0.0003，余弦退火 |
| 损失 | CrossEntropy + 类别权重 [1.8444, 0.6860] + label_smoothing=0.05 |
| 优化 | AdamW + AMP 混合精度 + 早停 patience=4 |
| 选模指标 | **val F1(macro)**（非 Accuracy） |
| batch | 32，输入 224×224，增强仅 train |

## 阶段表现
| 阶段 | 最佳 val F1(macro) | epoch |
|---|---|---|
| A（head only） | 0.8725 | 2 |
| B（finetune） | 0.9826 | 6 |

## TEST 一次性评估（最终报告用）

```
── ResNet50 保底基线 · TEST (val F1=0.9826) ─────────────────────────
  Accuracy          : 0.9743
  Precision(macro)  : 0.9666
  Recall(macro)     : 0.9684
  F1(macro)         : 0.9675
  AUC               : 0.9946
  ── 按类别 ──
    NORMAL      P=0.9497  R=0.9557  F1=0.9527
    PNEUMONIA   P=0.9835  R=0.9812  F1=0.9823
  ── 混淆矩阵（行=真实，列=预测，顺序 NORMAL, PNEUMONIA）──
       151       7
         8     417
  最佳 F1 阈值      : 0.4084（该阈值下 F1=0.9836）
```

> 阈值说明：类别 1:2.69 不平衡下，默认 0.5 阈值非最优，以上 test 结果
> 使用「val 最佳 F1 阈值」在 test 同样阈值下评估；部署时如需更高 PNEUMONIA
> Recall（灵敏度），可在 val 曲线上再调低阈值。

## 结论与下一步
- 保底版验收线：Accuracy ≥ 0.90、AUC ≥ 0.95、PNEUMONIA Recall ≥ 0.92
- 达标后按既定策略冻结本版；下一步叠加 SE / CBAM 注意力消融（实验 E2）。
