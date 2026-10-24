# 数据统计报告

> 由 `src/data/data_stats.py` 自动生成，数据源 `data/splits/split_manifest.csv`

## 1. 数据集来源

- **名称**：Chest X-Ray Images (Pneumonia)
- **来源**：Kermany et al., *Cell*, 2018
- **地址**：https://www.kaggle.com/datasets/paultimothymooney/chest-xray-pneumonia
- **任务**：二分类（NORMAL / PNEUMONIA）
- **合规性**：公开、已去标识化，仅用于课程教学科研。详见 `docs/数据合规说明.md`

## 2. 清洗结果

| 项目 | 数量 |
|---|---|
| 原始图像总数 | 5856 |
| 损坏 / 无法解码（剔除） | 0 |
| MD5 完全重复（剔除） | 32 |
| **最终有效样本** | **5824** |

说明：官方划分中 `val/` 仅 16 张（NORMAL 8 / PNEUMONIA 8），不具备统计意义，本项目**合并官方 train/val/test 全部样本后重新划分**。

## 3. 划分结果（8:1:1 分层抽样）

| 划分 | NORMAL | PNEUMONIA | 合计 | 占比 | 阳性占比 |
|---|---|---|---|---|---|
| train | 1263 | 3396 | 4659 | 80.00% | 72.89% |
| val | 158 | 424 | 582 | 9.99% | 72.85% |
| test | 158 | 425 | 583 | 10.01% | 72.90% |
| **合计** | **1579** | **4245** | **5824** | 100% | 72.89% |

**划分参数**：分层抽样（stratified），`random_state=1234`，两次切分（先 8:2，再对半分 val/test），可完全复现。

## 4. 数据泄漏检查

✅ 通过。各划分之间 **MD5 无重叠**，不存在同一张图像跨 train/val/test 的情况。

## 5. 类别平衡分析

- 总体 NORMAL : PNEUMONIA = 1 : 2.69（阳性占 72.89%）
- 各划分阳性占比几乎一致（分层抽样生效），说明**划分无偏**。
- ⚠️ 存在约 **1:2.7** 的类别不平衡，建议算法组采取以下措施之一：
  1. `CrossEntropyLoss(weight=[1.0, 0.37])` 或按样本数反比设置类别权重；
  2. 训练集对 NORMAL 做重采样 / 对 PNEUMONIA 做欠采样；
  3. **评价指标不要只看 Accuracy**，必须同时报告 Recall / F1 / AUC / 混淆矩阵（医学场景漏诊代价高，Recall 尤为重要）。

## 6. 图像尺寸统计

| 指标 | 宽 (W) | 高 (H) | 宽高比 W/H |
|---|---|---|---|
| 最小 | 384 | 127 | 0.835 |
| 中位数 | 1280 | 886 | 1.416 |
| 最大 | 2916 | 2713 | 3.379 |
| 均值 | 1327.5 | 970.2 | 1.443 |
| 标准差 | 363.5 | 383.3 | 0.255 |

- 图像尺寸**极不统一**（共 4803 种不同分辨率），必须在预处理阶段统一 Resize。
- 最大分辨率达 2916×2713，平均约 1.42 MP，统一缩放到 224×224 会带来明显信息压缩，属预期内的精度/成本权衡。

### 最常见的 5 种尺寸

| 尺寸 (W×H) | 数量 |
|---|---|
| 1072×648 | 7 |
| 1008×704 | 7 |
| 992×608 | 6 |
| 1216×872 | 6 |
| 992×592 | 6 |

## 7. 图表

| 图 | 文件 |
|---|---|
| 各划分类别分布 | `reports/figures/class_dist.png` |
| 原始尺寸散点 | `reports/figures/size_dist.png` |
| 宽高比分布 | `reports/figures/aspect_dist.png` |
| 样本预览（train） | `reports/figures/samples.png` |

## 8. 交付给算法组的预处理约定

```python
train_tf = transforms.Compose([
    transforms.Grayscale(num_output_channels=3),   # 灰度 -> 三通道（适配 ImageNet 预训练）
    transforms.Resize((224, 224)),                 # 统一尺寸
    transforms.RandomHorizontalFlip(p=0.5),        # ↓ 以下仅训练集
    transforms.RandomRotation(10),
    transforms.RandomResizedCrop(224, scale=(0.85, 1.0)),
    transforms.ColorJitter(brightness=0.1, contrast=0.1),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],   # ImageNet 均值/方差
                         [0.229, 0.224, 0.225]),
])

# val / test：不做随机增强，只做确定性变换
eval_tf = transforms.Compose([
    transforms.Grayscale(num_output_channels=3),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])
```

> **数据增强不落盘**：`data/processed/` 中只保存原图，增强在训练时由 `torchvision.transforms` 实时完成，避免磁盘膨胀与目录混乱。

## 9. 使用方式

```python
train_ds = datasets.ImageFolder("data/processed/train", transform=train_tf)
val_ds   = datasets.ImageFolder("data/processed/val",   transform=eval_tf)
test_ds  = datasets.ImageFolder("data/processed/test",  transform=eval_tf)
```

`ImageFolder` 会自动按文件夹名排序编码：**NORMAL=0，PNEUMONIA=1**。
