# 基于注意力机制增强 CNN 的肺炎 X 光片智能辅助诊断系统

> 面向医生的肺炎胸片二分类辅助筛查 Web 系统，包含 ResNet50 + ONNX 推理、JWT 鉴权、诊断历史、数据看板、模型实验信息以及 Three.js 全息人体解剖科普模块。

---

## 一、项目简介

本项目是《人工智能原理与实践》课程期末大作业，完成胸部 X 光片 `NORMAL / PNEUMONIA` 二分类辅助筛查，输出两类概率、判定类别、置信度与固定阈值，并提供历史记录、统计看板、模型实验信息和全息人体交互科普。

> **重要说明：** 项目名称保留“注意力机制增强 CNN”，但 E2 注意力消融实验表明 SE/CBAM 均未超过无注意力基线。因此在线模型如实采用实验最优的 `resnet50_baseline`，不虚假宣称使用了注意力增强模型。

---

## 二、医疗边界与免责声明

本系统仅用于课程演示、教学和科研参考。

- 仅提供 `NORMAL / PNEUMONIA` 二分类概率；
- 不提供临床诊断、治疗建议或处方；
- 不解析 DICOM，不接入 PACS/HIS；
- 不建立患者主索引，不管理挂号、住院、随访等流程；
- Grad-CAM 仅表示模型关注区域，不代表病灶边界；
- 系统结果不得替代执业医师结合病史、体征、实验室检查和影像学作出的综合判断。

---

## 三、当前完成度

| 模块 | 状态 | 说明 |
|---|---|---|
| 数据处理与划分 | 已完成 | 5,824 张公开胸片，8:1:1 分层划分，seed=1234 |
| ResNet50 基线 | 已完成 | Test Acc 0.9743，AUC 0.9946 |
| E1 骨干对比 | 已完成 | ResNet18/34、DenseNet121、EfficientNet-B0 |
| E2 注意力消融 | 已完成 | SE/CBAM 三轮实验，负结果完整保留 |
| E3 数据增强消融 | 已完成 | 全量增强组合最优 |
| E7 ONNX 部署与量化 | 已完成 | FP32、动态 INT8、静态 INT8 |
| FastAPI 后端 | 已完成 | JWT、预测、历史、统计、模型信息 |
| Vue3 前端 | 已完成 | 登录、工作台、历史、看板、模型信息 |
| Three.js 全息人体 | 已完成 | GLB 模型、全息材质、OrbitControls、胸部热区 |
| 结果图片导出 | 已完成 | html2canvas 2 倍分辨率 PNG 导出 |

---

## 四、核心功能

### 1. 医生登录与 JWT 鉴权

- 预置演示账号：`doctor / 123456`；
- 登录成功后签发 JWT；
- Token 保存在 `sessionStorage`，不使用 `localStorage`；
- 路由守卫保护业务页面；
- Token 过期或接口返回 401 时自动清理会话并跳转登录页。

### 2. AI 辅助筛查工作台

- 支持拖拽或点击上传 JPG/JPEG/PNG；
- 单文件大小限制 10 MB；
- 本地图片预览；
- CSS X 光扫描线分析动画；
- 调用 `/api/predict` 完成推理；
- NORMAL 绿色、PNEUMONIA 红色分类徽章；
- 置信度数字递增动画；
- 展示两类概率与固定阈值 `0.5101`；
- 原图与 Grad-CAM 区域对比；
- Grad-CAM 不可用时明确降级；
- 结果卡片导出 PNG；
- 结果自动写入当前医生历史记录。

### 3. 历史记录

- Element Plus 表格；
- 按 NORMAL / PNEUMONIA 筛选；
- 分页、详情弹窗、删除二次确认；
- 只展示当前登录医生数据；
- 删除当前页最后一条记录时自动回退页码。

### 4. 数据看板

- 总筛查数、肺炎数、正常数、肺炎占比；
- ECharts 阴阳性环形图；
- 最近 7 天 NORMAL / PNEUMONIA 趋势折线图；
- 缺失日期自动补零。

### 5. 模型信息看板

- 在线模型与部署格式；
- Accuracy、AUC、PNEUMONIA Recall、F1；
- 数据划分与训练协议；
- E1 骨干对比、E2 注意力负结果、E3 增强消融、E7 部署量化；
- 真实 Grad-CAM 样例。

### 6. Three.js 全息人体科普

- 加载 `frontend/public/models/human.glb`；
- 保留原始骨骼与肌肉贴图和法线贴图；
- 进行青色科技感着色，不破坏纹理细节；
- 环境光、主光、青色轮廓背光和蓝色补光；
- 轻微 Bloom 边缘发光；
- OrbitControls 拖拽旋转与滚轮缩放；
- 左侧 45° 左右翻转和正面重置；
- 胸部 3D 热区使用 CSS2DObject 跟随模型；
- 点击热区显示呼吸系统与肺炎科普卡片。

---

## 五、页面路由

| 路由 | 页面 | 说明 |
|---|---|---|
| `/login` | 登录页 | 磨砂玻璃卡片、演示账号、免责声明 |
| `/workspace` | 辅助筛查工作台 | 上传、分析、结果、Grad-CAM、导出 |
| `/holo-body` | 全息人体科普 | GLB 3D 人体、胸部热区、科普卡片 |
| `/history` | 历史记录 | 分页、筛选、详情、删除 |
| `/dashboard` | 数据看板 | 阴阳性饼图与 7 天趋势 |
| `/model-info` | 模型信息 | 指标与 E1/E2/E3/E7 实验结论 |
---

## 六、技术栈

### 前端

- Vue 3 Composition API
- Vite
- Vue Router
- Pinia
- Axios
- Element Plus
- ECharts
- Three.js
- html2canvas

### 后端

- FastAPI
- SQLAlchemy 2.x
- SQLite
- Pydantic 2.x
- PyJWT
- passlib + bcrypt
- ONNX Runtime
- Pillow
- torchvision

### 算法与模型

- PyTorch
- torchvision ResNet50
- ImageNet1K_V2 预训练
- ONNX FP32
- 两阶段迁移学习
- Weighted CrossEntropy
- AdamW、AMP、Cosine Annealing、Early Stopping
- Grad-CAM

---

## 七、系统架构

```text
┌─────────────────────────────────────────────────────────────┐
│                        Vue 3 前端                           │
│ Login ─ Workspace ─ HoloBody ─ History ─ Dashboard ─ Model  │
│              │                    │                         │
│              ├─ Three.js 3D 人体   ├─ ECharts                │
│              └─ Axios              └─ Element Plus           │
└──────────────────────────┬──────────────────────────────────┘
                           │ REST API / JWT
┌──────────────────────────▼──────────────────────────────────┐
│                        FastAPI 后端                         │
│ Auth Router ─ Predict ─ History ─ Stats ─ Model Info        │
│       │           │         │                               │
│       ├─ JWT      ├─ ONNX   ├─ SQLAlchemy                   │
│       └─ bcrypt   └─ PIL    └─ SQLite                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
                 ┌─────────▼─────────┐
                 │ ResNet50 ONNX FP32 │
                 │ threshold = 0.5101 │
                 └───────────────────┘
```

---

## 八、项目目录

```text
2026pneumonia-xray-attention-cnn Public/
├─ README.md
├─ requirements.txt
├─ run_backend.ps1
├─ run_frontend.ps1
├─ data/
├─ docs/
├─ models/
│  ├─ checkpoints/
│  └─ onnx/
│     └─ resnet50_baseline.onnx
├─ reports/
├─ src/
│  ├─ backend/
│  │  ├─ main.py
│  │  ├─ auth.py
│  │  ├─ database.py
│  │  ├─ model_loader.py
│  │  ├─ schemas.py
│  │  └─ utils.py
│  └─ train/
└─ frontend/
   ├─ public/
   │  ├─ models/
   │  │  └─ human.glb
   │  └─ model-samples/
   └─ src/
      ├─ api/
      ├─ assets/
      ├─ components/
      ├─ constants/
      ├─ data/
      ├─ layouts/
      ├─ router/
      ├─ stores/
      └─ views/
```

---

## 九、数据集与实验口径

| 项目 | 内容 |
|---|---|
| 数据集 | Chest X-Ray Images (Pneumonia) |
| 来源 | Kermany et al., Cell, 2018 |
| 任务 | NORMAL / PNEUMONIA 二分类 |
| 清洗后规模 | 5,824 张 |
| 数据划分 | 8:1:1 分层抽样 |
| 训练 / 验证 / 测试 | 4,659 / 582 / 583 |
| 随机种子 | 1234 |
| 测试纪律 | 测试集只做最终一次性评估 |
| 类别顺序 | 0 = NORMAL，1 = PNEUMONIA |

数据为公开、去标识化数据，仅用于课程学习、科研与教学演示。

---

## 十、最终模型指标

| 指标 | 测试集结果 |
|---|---:|
| Accuracy | **0.9743 / 97.43%** |
| AUC | **0.9946 / 99.46%** |
| PNEUMONIA Recall | **0.9812 / 98.12%** |
| NORMAL Recall | 0.9557 / 95.57% |
| Precision Macro | 0.9666 / 96.66% |
| Recall Macro | 0.9684 / 96.84% |
| F1 Macro | **0.9675 / 96.75%** |
| 部署阈值 | **0.5101** |

判定规则：

```text
p = softmax(logits)[PNEUMONIA]
if p >= 0.5101: PNEUMONIA
else: NORMAL
```
---

## 十一、关键实验结论

### E1 骨干对比

- ResNet50 Baseline：Test F1 0.9675，AUC 0.9946；
- ResNet18：Test F1 0.8705；
- ResNet34：Test F1 0.8456；
- DenseNet121：Test F1 0.8452；
- EfficientNet-B0：Test F1 0.8292；
- 结论：ResNet50 在本数据和训练协议下综合表现最优。

### E2 注意力消融

| 变体 | Test F1 | Test AUC | PNEUMONIA Recall |
|---|---:|---:|---:|
| Baseline 无注意力 | **0.9675** | **0.9946** | **0.9812** |
| SE v1 | 0.9637 | 0.9901 | 0.9694 |
| CBAM v1 | 0.9678 | 0.9919 | 0.9765 |
| CBAM v2 | 0.9574 | 0.9901 | 0.9647 |
| CBAM v3 | 0.9635 | 0.9906 | 0.9741 |

结论：

- SE/CBAM 均未超过无注意力基线的综合表现；
- 基线在 PNEUMONIA Recall 上漏诊 8 例，少于所有注意力变体；
- 负结果结合初始化塌方、恒等初始化修复、学习率震荡诊断链完整保留；
- 最终采用 `resnet50_baseline`。

### E3 数据增强消融

- 全量增强：Test F1 0.9675；
- 无增强：0.9017；
- 仅几何增强：0.8317；
- 仅颜色增强：0.9008；
- 强增强：0.8153；
- 仅翻转：0.9020；
- 结论：全量增强组合优于任一单项子集。

### E7 部署与量化

| 形态 | 体积 | CPU 时延 | Val Acc | PNEUMONIA Recall |
|---|---:|---:|---:|---:|
| PyTorch `.pt` | 94.4 MB | 56.1 ms | 0.9845 | 0.9882 |
| ONNX FP32 | 94.0 MB | 28.3 ms | 0.9845 | 0.9882 |
| ONNX 动态 INT8 | 94.0 MB | 26.8 ms | 0.9845 | 0.9882 |
| ONNX 静态 INT8 | 24.0 MB | 25.2 ms | 0.9828 | 0.9882 |

在线系统采用 ONNX FP32，静态 INT8 作为体积敏感场景备选。
---

## 十二、核心 API

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/auth/register` | 注册用户 |
| `POST` | `/api/auth/login` | 登录并获取 JWT |
| `POST` | `/api/predict` | 上传胸片并执行 ONNX 推理 |
| `GET` | `/api/history` | 分页查询当前用户历史 |
| `DELETE` | `/api/history/{id}` | 删除当前用户历史记录 |
| `GET` | `/api/stats/dashboard` | 获取 KPI、分布和 7 天趋势 |
| `GET` | `/api/model/info` | 获取在线模型信息 |
| `GET` | `/api/health` | 后端健康检查 |
| `GET` | `/docs` | Swagger API 文档 |

预测接口核心返回：

```json
{
  "prediction": {
    "probs": {
      "NORMAL": 0.4212,
      "PNEUMONIA": 0.5788
    },
    "label": "PNEUMONIA",
    "threshold": 0.5101,
    "confidence": 0.5788
  },
  "gradcam": {
    "status": "UNAVAILABLE",
    "original_url": "",
    "heatmap_url": "",
    "overlay_url": ""
  },
  "model_version": "resnet50_baseline",
  "inference_ms": 28
}
```

---

## 十三、数据库设计

### User

```text
id
username
hashed_password
created_at
```

### HistoryRecord

```text
id
user_id
filename
prediction
confidence
prob_pneumonia
created_at
```

- 数据库：SQLite；
- 默认文件：`data/app.db`；
- 外键开启；
- 删除用户时级联删除历史记录；
- 历史记录只允许当前用户访问和删除。
---

## 十四、本地运行

### 1. 后端环境

推荐使用项目内 Python 3.12 环境：

```powershell
cd "E:\2026pneumonia-xray-attention-cnn Public"
.\.backend-venv\python.exe -m pip install -r requirements.txt
```

启动后端：

```powershell
cd "E:\2026pneumonia-xray-attention-cnn Public"
powershell -ExecutionPolicy Bypass -File .\run_backend.ps1
```

或直接运行：

```powershell
.\.backend-venv\python.exe -m uvicorn src.backend.main:app --host 127.0.0.1 --port 18080 --reload
```
### 2. 前端

```powershell
cd "E:\2026pneumonia-xray-attention-cnn Public\frontend"
npm install
npm run dev
```

或使用脚本：

```powershell
cd "E:\2026pneumonia-xray-attention-cnn Public"
powershell -ExecutionPolicy Bypass -File .\run_frontend.ps1
```

### 3. 访问地址

```text
前端：http://127.0.0.1:15173
后端：http://127.0.0.1:18080
Swagger：http://127.0.0.1:18080/docs
```

### 4. 演示账号

```text
账号：doctor
密码：123456
```

后端首次启动时会自动创建该账号。
---

## 十五、关键配置

| 环境变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///.../data/app.db` | SQLite 地址 |
| `JWT_SECRET_KEY` | 课程演示密钥 | 生产环境必须修改 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `120` | JWT 有效期 |
| `CORS_ORIGINS` | `http://localhost:15173,http://127.0.0.1:15173` | 允许跨域前端 |
| `VITE_API_BASE_URL` | `/api` | 前端 Axios 基础路径 |

Vite 开发代理：

```text
/api -> http://127.0.0.1:18080
```

---

## 十六、安全与隐私

- 密码使用 bcrypt 哈希，不保存明文；
- 正式环境必须使用 HTTPS；
- JWT 只保存于 `sessionStorage`；
- 前端路由守卫与后端接口鉴权双重控制；
- 上传文件进行扩展名、MIME、文件头、解码和大小校验；
- 文件使用随机名称，禁止路径穿越；
- 历史记录与影像访问必须校验归属；
- 不采集患者姓名、身份证号、住院号等身份信息；
- 上传影像仅用于本地辅助筛查，不发送到第三方云服务。

---

## 十七、已知限制

1. 系统仅支持 JPG/JPEG/PNG，不支持 DICOM、PACS、HIS。
2. 只做 NORMAL/PNEUMONIA 二分类，不做多疾病分类。
3. 在线 Grad-CAM 当前为占位状态，模型信息页展示离线真实样例。
4. 历史记录未持久化原图和热力图，仅保存分类与概率信息。
5. `human.glb` 为单一人体网格，没有独立肺和气管节点；当前胸部热区使用 3D 锚点。
6. 3D 模型约 18 MB，首次加载时间受网络和磁盘性能影响。
7. 项目为课程演示系统，不具备医疗器械注册或临床使用资质。
---

## 十八、测试与验收要点

- 登录成功、失败、Token 过期与退出登录；
- 未登录访问业务页面自动跳转登录；
- 上传合法 JPG/PNG 成功推理；
- 非图片、伪装图片、超大文件、损坏图片被拒绝；
- 预测结果包含 `probs / label / threshold / confidence`；
- 阈值边界：`0.5100` 判 NORMAL，`0.5101` 判 PNEUMONIA；
- 历史分页、筛选、详情、删除和越权访问；
- 看板总数、分类数、7 天趋势与历史记录一致；
- 3D 模型拖拽、滚轮缩放、左右 45° 翻转和重置；
- 胸部热区点击与空白关闭卡片；
- 结果卡片 PNG 导出包含免责声明；
- Chrome/Edge 最新版和 1920×1080 分辨率正常。

---

## 十九、相关文档

- [需求规格说明书](docs/需求规格说明书.md)
- [选题与技术方案书](docs/01_选题与技术方案书.md)
- [数据合规说明](docs/数据合规说明.md)
- [项目进度总览](docs/项目进度总览.md)
- [ResNet50 基线报告](reports/model_baseline.md)
- [E2 注意力消融报告](reports/model_E2_attention.md)
- [E1 骨干对比报告](reports/e1_backbone.md)
- [E3 数据增强消融报告](reports/e3_augment.md)
- [E7 ONNX 部署报告](reports/e7_onnx.md)

---

## 二十、版本与维护

- 当前日期：2026-11-16
- 项目阶段：课程期末系统开发与答辩准备
- 在线模型：`resnet50_baseline` · ONNX FP32
- 前端主视觉：深蓝医疗科技风 + 极光青 + Glassmorphism + Three.js 全息人体

> 本项目仅用于课程学习、科研和教学演示，不用于临床诊断或商业医疗用途。