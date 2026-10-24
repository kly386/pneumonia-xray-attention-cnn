# 数据交接说明（给算法组：闵娟、伍梦圆）

> 负责人：开璐瑶（数据工程）
> 数据版本：v1.0（清洗 + 8:1:1 分层划分完成）

## 1. 一句话说明

原始 Kaggle 数据已合并、清洗、去重，并按 **8:1:1 分层抽样** 重新划分完毕，可以直接用 `torchvision.datasets.ImageFolder` 加载，**不要再使用官方 `train/val/test` 划分**。

## 2. 目录结构

```text
data/
├── raw/                      # 原始数据（只读，勿修改）
│   └── chest_xray/
│       ├── train/{NORMAL,PNEUMONIA}
│       ├── val/{NORMAL,PNEUMONIA}      # 官方仅16张，已弃用
│       └── test/{NORMAL,PNEUMONIA}
├── processed/                # ★ 训练用这份
│   ├── train/{NORMAL,PNEUMONIA}   # 4659 张
│   ├── val/{NORMAL,PNEUMONIA}     # 582 张
│   └── test/{NORMAL,PNEUMONIA}    # 583 张
└── splits/
    ├── split_manifest.csv    # 划分清单（filepath,label,split,width,height,md5,src_path）
    └── cleaning_log.csv      # 清洗日志（剔除的损坏/重复文件）
```

## 3. 数据规模与分布

| 划分 | NORMAL | PNEUMONIA | 合计 | 占比 | 阳性占比 |
|---|---|---|---|---|---|
| train | 1263 | 3396 | 4659 | 80.00% | 72.89% |
| val | 158 | 424 | 582 | 9.99% | 72.85% |
| test | 158 | 425 | 583 | 10.01% | 72.90% |
| **合计** | **1579** | **4245** | **5824** | 100% | 72.89% |

- 原始 5856 张 → 损坏 0 张、MD5 重复 32 张 → **最终 5824 张**
- 数据泄漏检查：**通过**，三份划分之间 MD5 无重叠
- 分层抽样 `random_state=1234`，完全可复现

## 4. 加载代码

```python
from torchvision import datasets, transforms

train_tf = transforms.Compose([
    transforms.Grayscale(num_output_channels=3),   # 灰度 -> 三通道
    transforms.Resize((224, 224)),
    transforms.RandomHorizontalFlip(p=0.5),
    transforms.RandomRotation(10),
    transforms.RandomResizedCrop(224, scale=(0.85, 1.0)),
    transforms.ColorJitter(brightness=0.1, contrast=0.1),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

eval_tf = transforms.Compose([
    transforms.Grayscale(num_output_channels=3),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])

train_ds = datasets.ImageFolder("data/processed/train", transform=train_tf)
val_ds   = datasets.ImageFolder("data/processed/val",   transform=eval_tf)
test_ds  = datasets.ImageFolder("data/processed/test",  transform=eval_tf)
```

`ImageFolder` 自动编码：**NORMAL = 0，PNEUMONIA = 1**（按文件夹名首字母排序）。

## 5. ⚠️ 必须注意的三件事

1. **类别不平衡（1 : 2.7）**
   - 建议 `CrossEntropyLoss(weight=torch.tensor([2.69, 1.0]))` 或按样本数反比设置；
   - 或者用 `WeightedRandomSampler`。
2. **不要只看 Accuracy**
   - 阳性占 72.9%，全部预测为 PNEUMONIA 就有 72.9% 准确率，这个基线很危险；
   - 必须报告 **Recall（灵敏度）、F1、AUC、混淆矩阵**，医学场景漏诊代价最高。
3. **增强只在训练集做**
   - `data/processed/` 里全是原图，没有增强副本；
   - 增强由 `torchvision.transforms` 在训练时实时完成，`val`/`test` 只用 `eval_tf`。

## 6. 复现命令

```bash
python src/data/check_raw.py     # 检查原始数据
python src/data/make_split.py    # 清洗 + 划分（会重建 data/processed）
python src/data/data_stats.py    # 生成统计报告
python src/data/make_samples.py  # 生成样本预览图
```

## 7. 相关文档

- 统计数据：`reports/data_stats.md`
- 图表：`reports/figures/`（class_dist / size_dist / aspect_dist / samples）
- 合规说明：`docs/数据合规说明.md`
