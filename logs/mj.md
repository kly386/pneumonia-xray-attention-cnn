# mj - 工作日志（成员2：闵娟）

- **日期：** 2026-11-02
- **项目名称：** 基于注意力机制增强 CNN 的肺炎 X 光片智能辅助诊断系统
- **身份：** 成员2 / 算法-模型（主）
- **工作地点：** `E:\Pycharm\project\pneumonia-xray-attention-cnn-main\`
- **今日状态：** ✅ **保底基线（ResNet50 二分类）训练完成并冻结，验收三项全部达标** —— 里程碑"第2周"任务（数据管道 + 基线跑通）提前完成

---

## 一、今日完成事项

| 序号 | 事项 | 状态 | 备注 |
|---|---|---|---|
| 1 | **环境确认与就绪** | ✅ 完成 | 训练用 conda 环境 `pytorch`（见第三节说明），torch 2.7.1+cu118，GPU（RTX 4060 Laptop）验证通过 |
| 2 | **数据接收与放置** | ✅ 完成 | Kaggle 原始数据放至 `data/raw/chest_xray/`，张数与官方一致（train 5216 / val 16 / test 624） |
| 3 | **数据管道复现** | ✅ 完成 | 跑 `src/data/make_split.py`（seed=1234）复现划分，结果与组长（kly）口径**完全一致**：5824 张，train 4659 / val 582 / test 583 |
| 4 | **数据统计核验** | ✅ 完成 | `data_stats.py` + `verify_loader.py` 全绿；类别编码 NORMAL=0 / PNEUMONIA=1；类别权重 [1.8444, 0.6860] |
| 5 | **训练框架搭建** | ✅ 完成 | 新建 `src/train/` 四个模块（见三节），两阶段迁移学习 + 早停 + AMP 全部封装好，后续消融实验可直接复用 |
| 6 | **保底基线训练** | ✅ 完成 | 阶段 A 冻结骨干训头（3 epoch）→ 阶段 B 全网微调（best@epoch6，早停@epoch10） |
| 7 | **模型冻结与归档** | ✅ 完成 | `models/checkpoints/resnet50_baseline.pt`（含 val 选定阈值），训练报告已生成 `reports/model_baseline.md` |

## 二、验收结果（对照方案书目标：Acc≥0.90 / AUC≥0.95）

| 指标 | TEST 实测 | 判定 |
|---|---|---|
| Accuracy | **0.9743** | ✅ ≥0.90 |
| AUC | **0.9946** | ✅ ≥0.95 |
| Precision(macro) / Recall(macro) / F1(macro) | 0.9666 / 0.9684 / 0.9675 | ✅ |
| **PNEUMONIA Recall（灵敏度，医学第一优先）** | **0.9812**（425 例阳性仅漏 8 例） | ✅ ≥0.92 |
| NORMAL Recall | 0.9557 | ✅ |
| 混淆矩阵（行=真实，列=预测） | NORMAL 151/158；PNEUMONIA 417/425 | 详见报告 |

**两阶段增益证据链（答辩可用）**：冻结头训练 val F1=0.8725 → 全网微调 val F1=0.9826，证明分阶段迁移学习有效。

**⚠️ 阈值纪律说明**：部署与后续报告统一使用 **val 上选定的阈值**（已存入 checkpoint）；test 上事后计算的 0.4084 仅作参考、不参与任何选择（"test 只评一次"红线）。

## 三、训练框架与环境说明（给全组）

### 代码结构（我新建的 `src/train/`）

| 文件 | 职责 |
|---|---|
| `src/train/common.py` | 固定种子(1234)、数据加载（增强仅 train）、加权交叉熵、设备检测 |
| `src/train/model.py` | ResNet50 迁移学习（ImageNet 预训练+二分类头），`freeze` 开关区分阶段 A/B |
| `src/train/metrics.py` | Accuracy/P/R/F1/AUC/混淆矩阵 + val 自动搜索最佳 F1 阈值 |
| `src/train/train_baseline.py` | 两阶段训练主流程：AdamW+余弦退火+AMP；**val F1(macro) 选模 + 早停**；产出 checkpoint 与报告 |

### 两套环境，分工明确（别搞混）

| 环境 | 路径 | 用途 | 已装关键包 |
|---|---|---|---|
| conda `pytorch`（**训练/评估用**） | `C:\Users\29542\.conda\envs\pytorch` | 所有 AI 实验 | torch 2.7.1+cu118、torchvision、timm 1.0.30、grad-cam、pandas、sklearn |
| 仓库 `.venv`（**数据管道用**） | 仓库根目录 | `src/data/` 脚本 | pandas / sklearn / matplotlib / pillow（**无 torch**） |

### 常用运行命令（仓库根目录下）

```powershell
# 训练/评估（注意用 conda pytorch 环境的完整路径）
C:\Users\29542\.conda\envs\pytorch\python.exe -m src.train.train_baseline

# 阶段 B 反复调试时，加 --skip-a 复用阶段 A 检查点（省约 5 分钟）
C:\Users\29542\.conda\envs\pytorch\python.exe -m src.train.train_baseline --skip-a

# 数据管道（用仓库 .venv）
.venv\Scripts\python.exe src\data\data_stats.py
```

**纪律**：`models/checkpoints/resnet50_baseline.pt` 从今天起冻结，**任何后续实验不得覆盖**，对比实验一律另命名（如 `resnet50_se_v1.pt`）。

## 四、给下游队友的交接约定（重要）

### → 伍梦圆（成员3：Grad-CAM / ONNX / E1 骨干对比 / E3 增强消融）
1. **输入约定**：224×224 三通道，ImageNet 归一化（mean=[0.485,0.456,0.406]，std=[0.229,0.224,0.225]）；预处理直接复用 `src/train/common.py::eval_tf`
2. **模型输出 JSON 约定（联调以此为准）**：
   ```json
   {
     "probs": {"NORMAL": 0.0187, "PNEUMONIA": 0.9813},
     "label": "PNEUMONIA",
     "threshold": 0.4084,
     "model_version": "baseline-v1"
   }
   ```
3. Grad-CAM 目标层：ResNet50 的 `layer4[-1]`
4. **装 grad-cam 的坑**：PyPI 包名已改为 `grad-cam`（`pip install grad-cam`），但 import 名不变：`import pytorch_grad_cam`
5. E1 / E3 实验直接复用 `train_baseline.py` 骨架，改骨干名对比即可；微调策略沿用两阶段（E1 小模型可只做一阶段，报告里说明）

### → 杨思彤（成员4：全栈）
后端 AI 推理模块按第 2 点的 JSON 约定对接；前端展示可用"准确率 97.4% / AUC 0.995"（来源 `reports/model_baseline.md`）。

### → 组长（kly）
- 里程碑第 2 周任务提前完成，请更新进度表
- `reports/model_baseline.md` 可直接并入总结报告的"基线模型"章节

## 五、接下来要做什么（优先级）

| 优先级 | 事项 | 负责 |
|---|---|---|
| **P0** | **E2 注意力消融**：新建 `src/train/attention.py`（SE/CBAM 模块，插入位置可配置，首版只插 layer3+layer4）+ `train_ablation.py`（`--attn {none,se,cbam}` 单变量开关），产出 `resnet50_se_v1.pt` / `resnet50_cbam_v1.pt`，成绩汇入消融表 | **闵娟（我）**；baseline 隔日成绩（test F1 0.9675）作对照 |
| P0 | ONNX 导出 + 动态量化对比（E7） | 伍梦圆 |
| P1 | E1 骨干对比、E3 增强消融 | 伍梦圆 |
| P1 | 后端推理模块按 JSON 约定对接基线模型 | 杨思彤 |
| P2 | E4 超参微调、E5 交叉验证（视 E2 结果决定是否必要） | 闵娟 |

## 六、今日心得与避坑提醒

1. **conda 环境目录不在项目盘**：conda 未配置环境落点，环境装到了 `C:\Users\29542\.conda\envs\`——不改正不影响功能，只是占 C 盘（组员自装时也留意）
2. **终端重定向时 print 要加 `flush=True`**，否则日志攒缓冲看不到实时进度（今天踩过）
3. **Windows GBK 控制台打印 ✅ 这类 emoji 会报 UnicodeEncodeError**（组长 `make_split.py` 末行崩的就是这个，不影响任何数据）；跑脚本前 `$env:PYTHONIOENCODING='utf-8'` 一劳永逸
4. **test 只评一次是红线**：选模/阈值/调参全用 val；`train_baseline.py` 已内置此纪律，大家做实验时沿用
5. **验收基准已经不低（test F1 0.9675）**：后续消融应关注 val 曲线与混淆矩阵变化，别指望每个实验都有 0.001 级别以上的显著提升——这正是要用消融表+可视化解释"注意力带来了什么"，而不是只盯着涨跌数字

---
**明日首要任务**：完成 E2 注意力消融代码（SE/CBAM 模块 + 单变量开关训练入口），争取明天跑完 +SE、+CBAM 两轮训练并出第一版消融表。
