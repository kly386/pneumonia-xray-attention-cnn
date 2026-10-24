# kly - 工作日志

- **日期：** 2026-10-24
- **项目名称：** 基于注意力机制增强 CNN 的肺炎 X 光片智能辅助诊断系统
- **身份：** 组长 / 项目统筹 / 数据工程
- **工作地点：** `D:\QQ\肺炎X光片智能辅助诊断系统\`
- **今日状态：** 数据工程阶段已基本收尾，准备转入接口约定与文档整理

## 一、今日完成事项

| 序号 | 事项 | 状态 | 备注 |
|---|---|---|---|
| 1 | **项目目录搭建** | ✅ 完成 | 新建 `data/raw/`、`data/interim/`、`data/processed/`、`src/data/`、`notebooks/`、`reports/` 等目录结构 |
| 2 | **数据集查找与确认** | ✅ 完成 | 在 `data/raw/chest_xray/` 找到 Kermany 团队提供的 Chest X-Ray Images (Pneumonia) 数据集，确认结构为 `train/val/test` 且分类文件夹为 `NORMAL/`、`PNEUMONIA/` |
| 3 | **原始数据统计** | ✅ 完成 | 编写并运行 `src/data/check_raw.py`，统计官方划分分布，确认官方 `val` 仅 16 张（NORMAL 8 / PNEUMONIA 8），**不可直接使用** |
| 4 | **数据清洗与划分** | ✅ 完成 | 编写 `src/data/make_split.py`，实现完整性校验（PIL.verify/load）、MD5 精确去重、分层抽样（Stratified）按 **8:1:1** 重新划分，固定随机种子 `1234` 保证可复现 |
| 5 | **生成最终数据集** | ✅ 完成 | 将划分后的图像复制至 `data/processed/train/val/test/`，并生成 `data/splits/split_manifest.csv`、`data/splits/cleaning_log.csv` |
| 6 | **数据统计与可视化** | ✅ 完成 | 编写并运行 `src/data/data_stats.py`，生成 `reports/data_stats.md` 及 `reports/figures/` 下的 `class_dist.png`、`size_dist.png`、`aspect_dist.png`、`samples.png` |
| 7 | **数据管道验证** | ✅ 完成 | 编写并运行 `src/data/verify_loader.py`，验证 `torchvision.datasets.ImageFolder` 可正常加载，batch 形状 `(8,3,224,224)` 正确，且已计算训练集类别权重 `[1.8444, 0.6860]` |
| 8 | **合规与交接文档** | ✅ 完成 | 编写 `docs/数据合规说明.md`、`data/README.md`，并补充 `requirements.txt`、`.gitignore` |

## 二、今日关键数据结论

| 项目 | 结果 |
|---|---|
| **原始总数** | 5856 张（合并 train/val/test） |
| **损坏图像** | 0 张（全部可正常解码） |
| **重复图像（MD5去重）** | **32 张**（已剔除） |
| **最终有效样本** | **5824 张** |
| **重新划分（8:1:1）** | `train: 4659`（1263 NORMAL / 3396 PNEUMONIA） \| `val: 582`（158 NORMAL / 424 PNEUMONIA） \| `test: 583`（158 NORMAL / 425 PNEUMONIA） |
| **类别比例** | **NORMAL : PNEUMONIA ≈ 1 : 2.69**（存在类别不平衡） |
| **数据泄漏** | **通过 ✅**（各划分间 MD5 无重叠） |
| **图像尺寸** | 极不统一，范围 `384×127` ~ `2916×2713`，需统一 Resize 至 `224×224` |
| **划分可复现性** | 固定 `random_state=1234`，分层抽样，完全可复现 |

## 三、今日产出文件清单

```text
├── data/
│   ├── raw/chest_xray/        # 原始数据（只读）
│   ├── processed/             # ★ 最终训练集（train/val/test）
│   ├── splits/                # split_manifest.csv、cleaning_log.csv
│   └── README.md              # 数据说明
├── src/data/
│   ├── check_raw.py
│   ├── make_split.py
│   ├── data_stats.py
│   ├── make_samples.py
│   └── verify_loader.py
├── reports/
│   ├── data_stats.md          # ★ 数据统计报告（可直接写进总结报告）
│   └── figures/               # 可视化图表 + 样本预览（class_dist、size_dist、aspect_dist、samples）
├── docs/
│   ├── 01_选题与技术方案书.md
│   └── 数据合规说明.md         # 合规声明
├── requirements.txt
├── .gitignore
└── kly.md                     # 本工作日志
```

## 四、明天/接下来需要做的事（优先级排序）

| 优先级 | 事项 | 目标 | 备注 |
|---|---|---|---|
| **P0（最紧急）** | **数据交接** | 将 `data/processed/`、`data/README.md`、`reports/data_stats.md` 发至组群，告知算法组（闵娟、伍梦圆）可直接用 `ImageFolder` 加载数据 | 建议重点强调：**别用官方 val、注意类别不平衡 1:2.7、增强只做在训练集、评估要用 Recall/F1/AUC** |
| **P0（最紧急）** | **编写需求分析文档** | 新建 `docs/需求分析.md`，梳理用户需求、功能需求、非功能需求、界面需求以及系统定位（**仅辅助参考，不替代医生诊断**） | 对应交付物清单里的《系统文档》部分 |
| **P0（最紧急）** | **编写 REST API 接口文档** | 新建 `docs/API接口文档.md`，统一定义前后端接口（上传影像、AI推理、历史记录、用户登录等） | 按照技术方案书第4.1、4.3节来定，优先定好路径、请求体、响应体，方便杨思彤（全栈）并行开发 |
| **P1（重要）** | **整理进项目总结报告** | 将 `reports/data_stats.md` 的内容（数据来源、清洗、划分、泄漏检查、类别不平衡）整合到项目总结报告的「数据集与预处理」章节 | 节省后续汇总时间 |
| **P1（重要）** | **更新里程碑进度** | 对照第七章里程碑计划，标记「第1周」「第2周-数据预处理与划分」已完成，更新组内进度表 | 保持进度可视，便于组长统筹 |
| **P2（后续）** | **跟进联调预案** | 提前想好数据与后端的对接细节（模型输入格式、返回字段），为后续系统联调做准备 | 等算法组交出首版模型再细化即可 |

## 五、今日心得与避坑提醒

- **别被官方划分迷惑。** `chest-xray-pneumonia` 官方的 `val` 只有 16 张，根本不够做验证。**必须合并后重新划分**才有说服力。
- **去重比想象中更重要。** 今天清出了 32 张 MD5 完全相同的图像。如果漏掉这一步，测试集里极有可能混入训练集样本，导致模型效果虚高。
- **类别不平衡要提早说清。** 1:2.7 的比例下，"全预测为 PNEUMONIA"就能拿到 ~72.9% 准确率。后续训练一定要用类别权重或者调整评价思路，**不能只盯着 Accuracy**。
- **用脚本复现比手动操作强太多。** 全部流程都写进 `src/data/` 里了，换台电脑只要把数据放对位置跑三条命令就能复现一模一样的划分，特别适合课程项目也方便答辩时说明。
- **合规要先行。** 已经先写好《数据合规说明》，把数据来源、去标识化、科研用途这些都讲清楚，避免踩到方案书里提到的合规红线。

**明天首要任务：先发数据交接消息，再着手写《需求分析.md》和《API接口文档》。**
