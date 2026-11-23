# 肺炎 X 光片智能辅助诊断系统 · 前端

基于 Vue 3 + Vite + Element Plus + Pinia + ECharts + Three.js 的医疗科技风前端。

## 页面

- `/login`：医生登录、演示账号填充、免责声明
- `/workspace`：影像上传、X 光扫描动画、ONNX 预测、结果与 PNG 导出
- `/holo-body`：Three.js 全息人体、OrbitControls、胸部热区、科普卡片
- `/history`：历史记录分页、筛选、详情和删除
- `/dashboard`：阴阳性饼图与最近 7 天趋势
- `/model-info`：ResNet50 指标和 E1/E2/E3/E7 实验结论

## 技术栈

- Vue 3 Composition API
- Vite
- Vue Router
- Pinia
- Axios
- Element Plus
- ECharts
- Three.js
- html2canvas

## 启动

```powershell
cd "E:\2026pneumonia-xray-attention-cnn Public\frontend"
npm install
npm run dev
```

前端默认地址：

```text
http://127.0.0.1:15173
```

Vite 会将 `/api` 代理到：

```text
http://127.0.0.1:18080
```

## 构建

```powershell
npm run build
npm run preview
```

## 关键目录

```text
src/
├─ api/           Axios 封装
├─ assets/        全局设计变量和样式
├─ components/    通用、工作台、全息人体组件
├─ constants/     项目常量与免责声明
├─ data/          模型实验数据
├─ layouts/       登录后整体布局
├─ router/        路由与鉴权守卫
├─ stores/        Pinia 用户会话
└─ views/         业务页面
```

## 演示账号

```text
doctor / 123456
```

完整项目介绍请查看仓库根目录的 `README.md`。