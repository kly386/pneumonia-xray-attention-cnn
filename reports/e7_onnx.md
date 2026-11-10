# E7 报告：ONNX 导出与量化对比（模型部署侧）

> 负责人：伍梦圆（成员3 / 部署导出）
> 日期：2026-11-10
> 上游：`resnet50_baseline.pt`（闵娟交付，val 阈值 0.5101，冻结勿动）
> 下游：杨思彤（FastAPI 联调）、kly（总结报告"部署"章节）

## 1. 一句话结论

**联调用 `models/onnx/resnet50_baseline.onnx`（FP32）**：比 torch 直接推理 CPU 快约 2 倍（56→28ms）、精度与 torch 完全一致；若在意体积可换 `*_int8_sta.onnx`（94→24MB，再快 ~11%，val 精度仅 -0.17pp、PNEUMONIA Recall 不变）。

## 2. 交付物（models/onnx/）

| 文件 | 形态 | 状态 |
|---|---|---|
| `resnet50_baseline.onnx` | FP32 全精度 | ✅ 联调主用 |
| `resnet50_baseline_int8_dyn.onnx` | 动态量化（仅 Gemm/MatMul 权重 int8） | ✅ 精度零损失 |
| `resnet50_baseline_int8_sta.onnx` | 静态量化 QDQ 全网 int8（64 张 val 真样张 MinMax 校准） | ✅ 体积优化选项 |

`*.onnx` 在 `.gitignore`，走群文件/网盘交接。

### 输入/输出约定（联调以此为准，与 `logs/mj.md` 第四节对齐）

- 输入名 **`images`**：`(B, 3, 224, 224)` float32，灰度转三通道 + ImageNet 归一化（mean=[0.485,0.456,0.406]，std=[0.229,0.224,0.225]），预处理可照抄 `src/train/common.py::eval_tf`
- 输出名 **`logits`**：`(B, 2)`，索引 0=NORMAL、1=PNEUMONIA；概率 = `softmax(logits)`
- **阈值用 checkpoint 里 val 选定的 0.5101**（不要用 0.5）
- batch 为动态轴，后端可自由批大小
- 输出 JSON 字段建议照 mj 第四节：`probs / label / threshold / model_version`

## 3. 对比表（本机 CPU 实测：批量 1，单会话 4 线程，50 次平均）

| 形态 | 体积 | CPU 时延 | val Acc | val F1(macro) | val AUC | PNEUMONIA Recall |
|---|---|---|---|---|---|---|
| .pt（torch CPU 直接推理） | 94.4MB | 56.1ms | 0.9845 | 0.9805 | 0.9983 | 0.9882 |
| onnx FP32 | 94.0MB | 28.3ms | 0.9845 | 0.9805 | 0.9983 | 0.9882 |
| int8 动态（Gemm/MatMul） | 94.0MB | 26.8ms | 0.9845 | 0.9805 | 0.9983 | 0.9882 |
| int8 静态（QDQ，64 张校准） | **24.0MB** | **25.2ms** | 0.9828 | 0.9783 | 0.9972 | 0.9882 |

- logits 数值一致性（vs torch，随机与真图输入）：FP32 ≤1.7e-06，动态 int8 同级；静态 int8 概率最大偏 ~0.3（置信度会漂，但判定行为见上表影响极小）
- 与基线口径的关系：val F1 0.9805 系给定阈值 0.5101 下的复评；选模时的 0.9826 是最优阈值口径，两者不矛盾（阈值纪律见 `reports/model_baseline.md`）
- 附注：Entropy 校准试跑与 MinMax 的 val 指标完全相同，采用更简单的 MinMax 口径

**结论**：
1. 后端优先用 FP32 ONNX / 动态 int8（精度全零损）；
2. 体积敏感场景（打包进安装包、网页端）用静态 int8：4 倍体积缩减 + 11% 提速，代价 -0.17pp Acc，Recall（医学第一优先）不变；
3. Grad-CAM 热力图首批已产出（`reports/figures/gradcam/`，val 一正一负两张，判定正确、聚焦病灶/肺野合理），成图规范：原图 | Jet 热力 | 叠加三联。

## 4. 复现命令（dl-env 环境，仓库根目录）

```powershell
$env:PYTHONIOENCODING='utf-8'
D:\Miniconda3\envs\dl-env\python.exe -m src.train.export_onnx --eval-dir data/processed/val
D:\Miniconda3\envs\dl-env\python.exe -m src.train.gradcam --image <样张1> --image <样张2>
```

## 5. 避坑记录（详见 `logs/wmy.md` 第四节）

1. `quantize_dynamic` 默认把 Conv 转 `ConvInteger`，onnxruntime CPU 不支持 → 必须限定 Gemm/MatMul
2. CNN 真压缩走静态量化（QDQ + `QLinearConv`）；随机张量校准不可用于精度口径（概率最大偏 0.7 级），必须真样张
3. 评估脚本曾把 softmax 误施加在输入图像而非 logits 上（4D 数组导致 sklearn 报 mix of binary/unknown）——已修复于 `export_onnx.py::eval_metrics`
