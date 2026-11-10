# wmy - 工作日志（成员3：伍梦圆）

- **日期：** 2026-11-10
- **项目名称：** 基于注意力机制增强 CNN 的肺炎 X 光片智能辅助诊断系统
- **身份：** 成员3 / 算法-模型（副）/ 可解释性 / 部署导出
- **工作地点：** `D:\pneumonia-xray-attention-cnn\`
- **今日状态：** ✅ **份内四件套全部收官** —— E7 部署三件（定稿）+ Grad-CAM 首批热力图 + **E1 骨干对比** + **E3 增强消融**（均为单变量协议，test 一次终评，报告已产出）

---

## 一、今日完成事项

| 序号 | 事项 | 状态 | 备注 |
|---|---|---|---|
| 1 | 仓库克隆到本地 | ✅ 完成 | main 分支（组长状态），另建个人分支 `wumengyuan` 工作 |
| 2 | **接收 P0 交接物 `resnet50_baseline.pt`** | ✅ 完成 | 94.4MB，元数据核验一致：val_f1=0.9826、阈值 0.5101、seed 1234（与 `logs/mj.md` 交接清单完全吻合） |
| 3 | **训练环境确认** | ✅ 完成 | 未新装。复用本机已有 conda 环境 `D:\Miniconda3\envs\dl-env`（Python 3.10 / torch 2.14.0+cu126 / timm 1.0.30 / grad-cam 1.5.7 / onnx + onnxruntime 1.23 / sklearn），GPU（RTX 3060 Laptop 6G）验证通过 |
| 4 | **Grad-CAM 可视化脚本** | ✅ 完成 | 新建 `src/train/gradcam.py`：目标层 layer4[-1]、预处理复用 `common::eval_tf`、阈值读 checkpoint；输出三联图（原图\|Jet 热力\|叠加）+ 部署 JSON，支持 SE/CBAM 变体 ckpt |
| 5 | **E7：ONNX 导出 + 量化对比** | ✅ 完成 | 新建 `src/train/export_onnx.py`，交付 3 个模型文件，对比表见第三节 |
| 6 | **数据接入 + 划分复现** | ✅ 完成 | 原始数据（组长群文件）拷入 `data/raw/chest_xray/`，跑 `make_split.py`：本地复现的 `split_manifest.csv` 与仓库入库版**逐行内容完全一致**（5824 张，train 4659 / val 582 / test 583），复现成功 |
| 7 | **E7 收尾：val 精度无退化验证** | ✅ 完成 | fp32 / 动态 int8 与 torch 精度完全一致；静态 int8 仅 -0.17pp（P-Recall 不变），详见第三节与 `reports/e7_onnx.md` |
| 8 | **Grad-CAM 首批真图** | ✅ 完成 | val 一负一正两张（NORMAL / PNEUMONIA 各一），判定正确、热区聚焦合理（`reports/figures/gradcam/`）；正式成批出图待与报告排版对齐 |
| 9 | **E1 骨干对比（4 个新骨干）** | ✅ 完成 | 新建 `src/train/exp_utils.py`（通用骨干/头替换/两阶段）+ `src/train/train_e1.py`；resnet18/34、densenet121、efficientnet_b0 同协议各训一轮，**ResNet50 全面最优**（test F1 0.9675 vs 0.8292~0.8705），报告 `reports/e1_backbone.md` |
| 10 | **E3 增强消融（5 个变体）** | ✅ 完成 | 新建 `src/train/train_e3.py`（自定义 train transform 单变量）；none/geo/color/strong/flip 五变体，**全量增强组合不可替代**（test F1 0.9675 vs 0.8153~0.9020），报告 `reports/e3_augment.md` |

## 二、Git 与分支约定（自用备忘）

- 个人分支：`wumengyuan`（照闵娟 `minjuan` 分支的惯例，main 不直接动）
- 本仓库级 git 身份已配置 `user.name = 伍梦圆`
- 注意：`*.pt / *.onnx / data 大文件` 均在 `.gitignore`，交接靠群文件/网盘，commit 里不会有

## 三、E7 对比表（本机实测：批量 1 / 单会话 4 线程 / 50 次平均；精度 = val 582 张）

| 模型形态 | 体积 | CPU 时延 | val Acc | val F1 | val AUC | P-Recall |
|---|---|---|---|---|---|---|
| pt_torch（torch CPU） | 94.4MB | 56.1ms | 0.9845 | 0.9805 | 0.9983 | 0.9882 |
| **onnx FP32** | 94.0MB | 28.3ms | 0.9845 | 0.9805 | 0.9983 | 0.9882 |
| onnx 动态 int8（Gemm/MatMul） | 94.0MB | 26.8ms | 0.9845 | 0.9805 | 0.9983 | 0.9882 |
| onnx 静态 int8（QDQ 真样张校准） | **24.0MB** | **25.2ms** | 0.9828 | 0.9783 | 0.9972 | 0.9882 |

**结论**：FP32 ONNX 比 torch 直接推理快 ~2 倍且精度零损失 → **联调主用，可交杨思彤**；静态 int8 体积 94→24MB、再快 ~11%，代价仅 -0.17pp Acc（P-Recall 不变），作体积优化选项。正式报告：`reports/e7_onnx.md`。

## 四、避坑记录（给后来人）

1. **动态量化别对 Conv 下手**：`quantize_dynamic` 默认连 Conv 一起转成 `ConvInteger`，onnxruntime CPU 根本不支持（NOT_IMPLEMENTED 崩溃）。已限定 `nodes_to_quantize` 只限 Gemm/MatMul；CNN 真压缩走静态量化 QDQ（`QLinearConv` 全支持）
2. **静态量化校准要用真样张**：随机张量校准的 int8 概率最大偏 0.7 级，不可作精度口径；改用 64 张 val 真样张（`_CalibReader` 自动切换）后 val 指标几乎追平（-0.17pp）。Entropy 校准试跑与 MinMax 结果完全相同，采用 MinMax
3. **grad-cam 包**：本机(dl-env)已装 `grad-cam 1.5.7`；1.5.x 的 `cam(input_tensor)` 要求显式传 `targets=None`（否则 TypeError），旧教程代码会踩
4. **torch 2.14 的 legacy ONNX 导出**：`torch.onnx.export` 需手动 `dynamo=False` 走老 exporter，已验证 batch 动轴 OK
5. **评估三重_check**：曾把 softmax 误施加到输入图像（4D）而非 logits，sklearn 报 "mix of binary and unknown" —— 指标前先确认概率是一维 (N,)
6. **Windows spawn**：`DataLoader(num_workers>0)` 的脚本必须有 `if __name__ == "__main__":` 保护；走 `-m src.xxx` 的模块入口天然安全，临时调试脚本用 num_workers=0 稳
7. **Windows GBK emoji**：跑脚本前 `$env:PYTHONIOENCODING='utf-8'`（照抄 mj 日志第六节第 3 条）

## 五、接下来（按优先级）

| 优先级 | 事项 | 阻塞点 |
|---|---|---|
| P0 | 把 `models/onnx/resnet50_baseline.onnx`（+两件 int8）交给杨思彤联调；约定见 `reports/e7_onnx.md` 第 2 节 | 无，随时可交 |
| P0 | Grad-CAM 正式成批出图（按 test/val 选取代表性样张：NORMAL/PNEUMONIA/难例 若干），并入总结报告"可解释性"章节 | 无；等报告排版需求确定张数 |
| P2（可选） | E1/E3 稳健性复跑（对差距小的对子做双 seed） | 时间允许时 |
| ~~P0~~ | ~~E7~~ / ~~E1 骨干对比~~ / ~~E3 增强消融~~ ✅ 全部完成 | — |

**份内份外交接提示**：我的三份报告（`e7_onnx.md` / `e1_backbone.md` / `e3_augment.md`）可直接并入总结报告对应章节（部署 / 模型选型依据 / 增强消融）。
