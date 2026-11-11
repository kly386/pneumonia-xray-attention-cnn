# mj - 工作日志（成员2：闵娟）

- **日期：** 2026-11-03
- **项目名称：** 基于注意力机制增强 CNN 的肺炎 X 光片智能辅助诊断系统
- **身份：** 成员2 / 算法-模型（主）
- **工作地点：** `E:\Pycharm\project\pneumonia-xray-attention-cnn-main\`
- **今日状态：** ✅ **E2 注意力消融（SE/CBAM，三轮）完成并定稿** —— 注意力均未超过基线，`resnet50_baseline.pt` 定为最终最佳模型；"第3周（模型实验）"主体任务完成

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

**⚠️ 阈值纪律说明**：部署与后续报告统一使用 **val 上选定的阈值**（已存入 checkpoint，基线 = **0.5101**）；test 上事后计算的 0.4084 仅作参考、不参与任何选择（"test 只评一次"红线）。

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
     "threshold": 0.5101,
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

## 五、E2 注意力消融（2026-11-03 完成，定稿）

### 结论一句话
三轮单变量实验（朴素插入 → 恒等初始化 → 降学习率），SE/CBAM 均未超过基线；`resnet50_baseline.pt` 定为**最终最佳模型**。

### 消融表（test 口径）
| 变体 | 最佳 val F1 | test F1 | test AUC | P-Recall（漏诊） | checkpoint |
|---|---|---|---|---|---|
| **基线（无注意力）** | **0.9826** | **0.9675** | **0.9946** | **0.9812（漏8）** | resnet50_baseline.pt |
| SE v1 | 0.9680 | 0.9637 | 0.9901 | 0.9694（漏13） | resnet50_se_v1.pt |
| CBAM v1（朴素） | 0.9721 | 0.9678 | 0.9919 | 0.9765（漏10） | resnet50_cbam_v1.pt |
| CBAM v2（恒等初始化） | 0.9615 | 0.9574 | 0.9901 | 0.9647（漏15） | resnet50_cbam_v2.pt |
| CBAM v3（恒等初始化+降lr） | 0.9630 | 0.9635 | 0.9906 | 0.9741（漏11） | resnet50_cbam_v3.pt |

### 三段式诊断链（答辩素材）
1. **塌方**：CBAM v1 阶段 A 的 val AUC≈0.59（随机水平）——空间门随机初始化在预训练特征上打噪声窗
2. **救起步**：v2 恒等初始化（门控 bias=+4）后阶段 A val F1 0.59→0.91，塌方归因被证实
3. **部分改善**：v3 注意力单列学习率 1e-4 后 test F1 0.9574→0.9635、漏诊 15→11，方向正确但未根治震荡

### 最终结论
注意力参数 +2.37M（占全网 23.5M 的 ~10%）在本数据集/协议下不升反降；**瓶颈在数据规模（train 4659）而非模型结构**。完整报告见 `reports/model_E2_attention.md`。

### 交接清单（给下游，最终模型 = 基线）
- 模型文件：`models/checkpoints/resnet50_baseline.pt`（含 val 选定阈值 **0.5101**）
- 输入：224×224 三通道，ImageNet 归一化（复用 `src/train/common.py::eval_tf`）
- 输出 JSON：见本日志第四节第 2 点
- Grad-CAM 目标层：`layer4[-1]`

### 接下来（优先级）
| 优先级 | 事项 | 负责 |
|---|---|---|
| P0 | 把 `resnet50_baseline.pt` 交接给伍梦圆（Grad-CAM / ONNX）与杨思彤（FastAPI） | 闵娟（我） |
| P0 | ONNX 导出 + 动态量化对比（E7） | 伍梦圆 |
| P1 | E1 骨干对比、E3 增强消融 | 伍梦圆 |
| P1 | 后端推理模块按 JSON 约定对接基线模型 | 杨思彤 |
| P2 | （可选，时间富余再做）更大骨干 / 更强数据增强 | 闵娟 |

## 六、今日心得与避坑提醒

1. **conda 环境目录不在项目盘**：conda 未配置环境落点，环境装到了 `C:\Users\29542\.conda\envs\`——不改正不影响功能，只是占 C 盘（组员自装时也留意）
2. **终端重定向时 print 要加 `flush=True`**，否则日志攒缓冲看不到实时进度（今天踩过）
3. **Windows GBK 控制台打印 ✅ 这类 emoji 会报 UnicodeEncodeError**（组长 `make_split.py` 末行崩的就是这个，不影响任何数据）；跑脚本前 `$env:PYTHONIOENCODING='utf-8'` 一劳永逸
4. **test 只评一次是红线**：选模/阈值/调参全用 val；`train_baseline.py` 已内置此纪律，大家做实验时沿用
5. **验收基准已经不低（test F1 0.9675）**：后续消融应关注 val 曲线与混淆矩阵变化，别指望每个实验都有 0.001 级别以上的显著提升——这正是要用消融表+可视化解释"注意力带来了什么"，而不是只盯着涨跌数字
6. **注意力是从零训练的新组件，对学习率敏感**：与骨干共用 lr=3e-4 会剧烈震荡（E2 阶段 B 曲线横跳的根因），单列更低 lr（1e-4）能缓解但未根治
7. **CBAM 空间门随机初始化会破坏预训练特征**（E2 v1 阶段 A 塌方到 AUC≈0.59）；恒等初始化（末层权重清零 + bias=+4，门控初始≈全通）是标准修复，一次到位

---
**后续任务**：E2 已定稿（基线 = 最终模型），份内三件套（保底基线 / 注意力消融 / 最佳模型产出）全部完成；下一步配合下游（伍梦圆 Grad-CAM/ONNX、杨思彤 FastAPI）做好模型交接，时间富余再按第五节"接下来"表做可选拓展实验。
