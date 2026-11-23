export const modelMetrics = [
  {
    label: 'Accuracy',
    value: 0.9743,
    display: '97.43%',
    caption: '测试集一次性评估',
  },
  {
    label: 'AUC',
    value: 0.9946,
    display: '99.46%',
    caption: '类别排序能力',
  },
  {
    label: 'PNEUMONIA Recall',
    value: 0.9812,
    display: '98.12%',
    caption: '医学场景第一优先',
  },
  {
    label: 'F1 Macro',
    value: 0.9675,
    display: '96.75%',
    caption: '综合分类表现',
  },
]

export const datasetFacts = [
  { label: '数据集', value: 'Chest X-Ray Images (Pneumonia)' },
  { label: '影像数量', value: '5,824 张' },
  { label: '训练 / 验证 / 测试', value: '4,659 / 582 / 583' },
  { label: '划分方式', value: '8:1:1 分层抽样' },
  { label: '随机种子', value: 'seed = 1234' },
  { label: '评估纪律', value: '测试集仅一次性评估' },
]

export const trainingProtocol = [
  {
    title: '骨干网络',
    value: 'ResNet50',
    detail: 'ImageNet1K_V2 预训练权重',
  },
  {
    title: '阶段 A',
    value: '冻结骨干',
    detail: '仅训练分类头，3 epochs',
  },
  {
    title: '阶段 B',
    value: '全网微调',
    detail: '最多 15 epochs，Cosine Annealing',
  },
  {
    title: '损失函数',
    value: 'Weighted CE',
    detail: '类别权重 + label smoothing 0.05',
  },
  {
    title: '优化策略',
    value: 'AdamW + AMP',
    detail: 'Early Stopping patience = 4',
  },
  {
    title: '选模指标',
    value: 'Val F1 Macro',
    detail: '部署阈值由验证集选择',
  },
]

export const e1Rows = [
  {
    backbone: 'ResNet50 Baseline',
    acc: 0.9743,
    f1: 0.9675,
    auc: 0.9946,
    positiveRecall: 0.9812,
    normalRecall: 0.9557,
    selected: true,
  },
  {
    backbone: 'ResNet18 Baseline',
    acc: 0.8868,
    f1: 0.8705,
    auc: 0.9751,
    positiveRecall: 0.8518,
    normalRecall: 0.981,
  },
  {
    backbone: 'ResNet34 Baseline',
    acc: 0.8645,
    f1: 0.8456,
    auc: 0.968,
    positiveRecall: 0.8329,
    normalRecall: 0.9494,
  },
  {
    backbone: 'DenseNet121 Baseline',
    acc: 0.8645,
    f1: 0.8452,
    auc: 0.9624,
    positiveRecall: 0.8353,
    normalRecall: 0.943,
  },
  {
    backbone: 'EfficientNet-B0 Baseline',
    acc: 0.8456,
    f1: 0.8292,
    auc: 0.9766,
    positiveRecall: 0.7929,
    normalRecall: 0.9873,
  },
]

export const e2Rows = [
  {
    variant: 'Baseline（无注意力）',
    valF1: 0.9826,
    acc: 0.9743,
    f1: 0.9675,
    auc: 0.9946,
    positiveRecall: 0.9812,
    selected: true,
  },
  {
    variant: 'SE v1',
    valF1: 0.968,
    acc: 0.9708,
    f1: 0.9637,
    auc: 0.9901,
    positiveRecall: 0.9694,
  },
  {
    variant: 'CBAM v1',
    valF1: 0.9721,
    acc: 0.9743,
    f1: 0.9678,
    auc: 0.9919,
    positiveRecall: 0.9765,
  },
  {
    variant: 'CBAM v2（恒等初始化）',
    valF1: 0.9615,
    acc: 0.9657,
    f1: 0.9574,
    auc: 0.9901,
    positiveRecall: 0.9647,
  },
  {
    variant: 'CBAM v3（恒等初始化 + 低学习率）',
    valF1: 0.963,
    acc: 0.9708,
    f1: 0.9635,
    auc: 0.9906,
    positiveRecall: 0.9741,
  },
]

export const e3Rows = [
  {
    variant: 'Baseline（全量增强）',
    acc: 0.9743,
    f1: 0.9675,
    auc: 0.9946,
    positiveRecall: 0.9812,
    selected: true,
  },
  {
    variant: '无增强',
    acc: 0.9177,
    f1: 0.9017,
    auc: 0.9775,
    positiveRecall: 0.9059,
  },
  {
    variant: '仅几何增强',
    acc: 0.8491,
    f1: 0.8317,
    auc: 0.9653,
    positiveRecall: 0.8024,
  },
  {
    variant: '仅颜色增强',
    acc: 0.916,
    f1: 0.9008,
    auc: 0.9774,
    positiveRecall: 0.8965,
  },
  {
    variant: '强增强',
    acc: 0.8319,
    f1: 0.8153,
    auc: 0.9562,
    positiveRecall: 0.7765,
  },
  {
    variant: '仅翻转',
    acc: 0.9177,
    f1: 0.902,
    auc: 0.9779,
    positiveRecall: 0.9035,
  },
]

export const e7Rows = [
  {
    format: 'PyTorch .pt',
    size: '94.4 MB',
    latency: '56.1 ms',
    valAcc: 0.9845,
    valF1: 0.9805,
    valAuc: 0.9983,
    positiveRecall: 0.9882,
    note: '训练与对照',
  },
  {
    format: 'ONNX FP32',
    size: '94.0 MB',
    latency: '28.3 ms',
    valAcc: 0.9845,
    valF1: 0.9805,
    valAuc: 0.9983,
    positiveRecall: 0.9882,
    note: '在线联调主用',
    selected: true,
  },
  {
    format: 'ONNX 动态 INT8',
    size: '94.0 MB',
    latency: '26.8 ms',
    valAcc: 0.9845,
    valF1: 0.9805,
    valAuc: 0.9983,
    positiveRecall: 0.9882,
    note: '精度无损备选',
  },
  {
    format: 'ONNX 静态 INT8',
    size: '24.0 MB',
    latency: '25.2 ms',
    valAcc: 0.9828,
    valF1: 0.9783,
    valAuc: 0.9972,
    positiveRecall: 0.9882,
    note: '体积敏感备选',
  },
]

export const e2Diagnosis = [
  {
    step: '01',
    title: '初始化塌方',
    description:
      'CBAM v1 阶段 A 的 val AUC 约 0.59，随机空间门在 ImageNet 预训练特征上形成噪声窗。',
  },
  {
    step: '02',
    title: '恒等初始化修复',
    description:
      '门控末层清零并对 bias 加偏移后，阶段 A val F1 从约 0.59 回升到 0.91，归因得到验证。',
  },
  {
    step: '03',
    title: '学习率震荡仍在',
    description:
      '注意力参数单独使用 1e-4 学习率后，CBAM v3 的 F1 从 0.9574 回升到 0.9635，但仍未超过基线。',
  },
]

export const gradcamSamples = [
  {
    title: 'NORMAL 样例',
    label: 'NORMAL',
    description: '模型判定正确，关注区域主要位于肺野结构。',
    image: '/model-samples/normal-gradcam.png',
    tone: 'normal',
  },
  {
    title: 'PNEUMONIA 样例',
    label: 'PNEUMONIA',
    description: '模型判定正确，热力区域与肺部异常表现存在关联。',
    image: '/model-samples/pneumonia-gradcam.png',
    tone: 'danger',
  },
]