# ModeA/ModeB 合并与可视化升级结果（2026-04-06）

## 1. 本次完成内容

### 1.1 统一前端入口
- 首页已改为统一工作站：ModelA v2 闭环看板固定在上方。
- 旧版能力保留为折叠区：
  - Mode A 经典检索/流式报告
  - Mode B 症状驱动
  - A+B 联动工作流

涉及文件：
- `frontend/app/page.tsx`
- `frontend/components/modela/ModelAControlTower.tsx`
- `frontend/app/modela-v2/page.tsx`

### 1.2 ModelA v2 数据与闭环
- 基于 `dataset_3_24` 两个 CSV 构建异构图：
  - `enterprise_node.csv`
  - `graph_edges_reformatted_with_product.csv`
- 输出节点/边 7类风险概率、分层（高/中/低）与优先级。
- 支持智能抽检闭环与滚动闭环评估（T1~T6 模拟）。

涉及文件：
- `agent/modela_v2_engine.py`
- `backend/api.py`

### 1.3 风险边可视化
- 全图中边按风险等级着色与加粗：高风险边（红）/中风险边（橙）/低风险边（灰）。
- 新增“边风险等级筛选”。

涉及文件：
- `frontend/components/SupplyChainNetworkGraph.tsx`

## 2. 两个 zip 的合并状态

### 2.1 `/home/yarizakurahime/data/项目文件和要求.zip`
- **已合并（核心部分）**。
- 当前 ModelA v2 已直接使用其中的 `dataset_3_24` 两个核心 CSV 作为主数据输入。
- 在引擎中支持自动识别路径：`extracted_project_requirements/项目文件和要求/dataset_3_24`。

### 2.2 `/home/yarizakurahime/data/risk_visualization.zip`
- **部分参考，未整包并入当前 Next.js 前端主链路**。
- 该包是独立 Python/Folium 可视化工程；其中 `shanghai_districts.geojson` 和 `map_builder.py` 目前未直接接入现有 React 页面。
- 当前主前端可视化以异构图网络面板为主（节点+边风险同图显示）。

## 3. “两个中国地图选择了哪个”

当前版本结论：
- 在 `FoodDB/dairyrisk` 前端主链路中，**没有启用中国地图底图**（未接入 ECharts China map 或中国 GeoJSON 底图）。
- 若看 `risk_visualization.zip` 的独立工程，其使用的是 **上海行政区 GeoJSON**（`shanghai_districts.geojson`），不是全国中国地图。

## 4. 编译与可运行性

- 前端：`npm run build` 通过。
- 后端：`python -m py_compile backend/api.py agent/modela_v2_engine.py` 通过。

建议启动：

```bash
# backend
cd /home/yarizakurahime/data/FoodDB/dairyrisk
python backend/api.py

# frontend
cd /home/yarizakurahime/data/FoodDB/dairyrisk/frontend
export NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm run dev
```

访问：
- `http://127.0.0.1:3000/`
- `http://127.0.0.1:3000/modela-v2`
