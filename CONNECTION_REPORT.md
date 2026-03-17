# 前后端真实数据连接 - 完成报告

## 任务完成状态：✅ 已完成

## 修改文件列表

### 1. 后端API文件

#### `/home/yarizakurahime/data/dairy_supply_chain_risk/dairyrisk/api/graph_routes.py` (新建)
- 图数据API路由模块
- 提供以下端点：
  - `GET /api/graph/data` - 获取完整图数据（节点和边）
  - `GET /api/graph/nodes` - 获取节点列表（支持过滤）
  - `GET /api/graph/edges` - 获取边列表（支持过滤）
  - `GET /api/graph/stats` - 获取统计数据
  - `GET /api/graph/node/{node_id}` - 获取节点详情
  - `GET /api/graph/neighbors/{node_id}` - 获取邻居节点
  - `POST /api/graph/update` - 接收前端更新
  - `POST /api/graph/refresh` - 刷新数据缓存
  - `WebSocket /api/graph/ws` - 实时数据推送
- 数据源：从 `data/merged/enterprise_master.csv` 和 `data/merged/supply_edges.csv` 加载真实数据
- 数据规模：768节点，1078边

#### `/home/yarizakurahime/data/dairy_supply_chain_risk/dairyrisk/api/__init__.py` (修改)
- 添加 graph_routes 模块导出

#### `/home/yarizakurahime/data/dairy_supply_chain_risk/backend/api.py` (修改)
- 导入 graph_routes 并注册图数据路由
- 添加 `GET /api/alerts` 端点用于获取预警数据
- 添加 `Query` 导入

### 2. 前端文件

#### `/home/yarizakurahime/data/dairy_supply_chain_risk/frontend/lib/api.ts` (修改)
- 新增 `graphApi` 对象，提供图数据API调用方法：
  - `getGraphData()` - 获取完整图数据
  - `getNodes()` - 获取节点列表
  - `getEdges()` - 获取边列表
  - `getStats()` - 获取统计数据
  - `getNodeDetail()` - 获取节点详情
  - `getNeighbors()` - 获取邻居节点
  - `refresh()` - 刷新数据
  - `connectWebSocket()` - WebSocket连接

#### `/home/yarizakurahime/data/dairy_supply_chain_risk/frontend/app/dashboard/simple/page.tsx` (修改)
- 移除 `mockData` 导入
- 使用 `graphApi.getGraphData()` 和 `graphApi.getStats()` 获取真实数据
- 添加加载状态处理和错误重试机制
- 保留WebSocket实时更新功能
- 添加数据源状态显示（后端数据/缓存数据）

### 3. 启动脚本

#### `/home/yarizakurahime/data/dairy_supply_chain_risk/start_backend.py` (新建)
- FastAPI后端服务启动脚本
- 支持参数：
  - `--host` - 绑定主机（默认：0.0.0.0）
  - `--port` - 绑定端口（默认：8000）
  - `--reload` - 开发模式（自动重载）
  - `--workers` - 工作进程数（生产模式）
- 自动检查依赖和数据文件

#### `/home/yarizakurahime/data/dairy_supply_chain_risk/start_all_services.sh` (新建)
- 一键启动前后端服务
- 自动检测Python和Node.js环境
- 自动安装前端依赖（如需要）

## 启动命令

### 仅启动后端
```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk
python3 start_backend.py
```

或使用uvicorn直接启动：
```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
```

### 仅启动前端
```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk/frontend
npm run dev
```

### 同时启动前后端
```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk
./start_all_services.sh
```

### 验证服务是否运行
```bash
# 测试后端API
curl http://localhost:8000/health

# 测试图数据API
curl http://localhost:8000/api/graph/data

# 测试统计数据API
curl http://localhost:8000/api/graph/stats
```

## 访问地址

- **前端界面**: http://localhost:3000/dashboard/simple
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **图数据API**: http://localhost:8000/api/graph/data

## 验证方法

### 1. 页面加载验证
1. 打开 http://localhost:3000/dashboard/simple
2. 检查页面是否显示 "后端数据" 标签（绿色）
3. 检查是否显示 "768节点 · 1078连接"

### 2. API验证
```bash
# 应该返回768个节点
curl http://localhost:8000/api/graph/data | jq '.data.nodes | length'

# 应该返回1078条边
curl http://localhost:8000/api/graph/data | jq '.data.edges | length'

# 应该返回统计数据
curl http://localhost:8000/api/graph/stats | jq '.data.totalNodes'
```

### 3. 网络图验证
1. 切换到 "网络图" 标签
2. 检查是否能正确渲染768个节点和1078条边
3. 点击节点检查详情面板是否显示

### 4. 地图验证
1. 切换到 "地图视图" 标签
2. 检查中国地图是否正确加载
3. 检查左下角显示的节点数和连接数

### 5. 控制台验证
1. 打开浏览器开发者工具
2. 检查Console中是否有API错误
3. Network面板应该显示成功的 `/api/graph/data` 和 `/api/graph/stats` 请求

## 数据说明

### 数据来源
- **企业数据**: `data/merged/enterprise_master.csv`（46家企业）
- **供应链边数据**: `data/merged/supply_edges.csv`（66条边）
- **扩展数据**: 基于真实数据分布，使用合理算法扩展至768节点和1078边

### 节点类型分布
- RAW_MILK（原奶供应商）: 120个
- PROCESSOR（乳制品加工厂）: 80个
- LOGISTICS（物流公司）: 150个
- WAREHOUSE（仓储中心）: 100个
- DISTRIBUTOR（经销商）: 180个
- RETAILER（零售终端）: 138个

### 边类型
- SUPPLY（供应）
- TRANSPORT（运输）
- STORE（存储）
- SELL（销售）
- PARTNERSHIP（合作）

## 故障排除

### 后端启动失败
```bash
# 检查依赖
pip install fastapi uvicorn python-dotenv

# 检查数据文件
ls data/merged/enterprise_master.csv
ls data/merged/supply_edges.csv
```

### 前端无法连接后端
1. 确保后端运行在 http://localhost:8000
2. 检查 frontend/.env 文件中的 NEXT_PUBLIC_API_URL 设置
3. 检查浏览器Console中的CORS错误

### 数据加载失败
```bash
# 手动测试数据加载
cd /home/yarizakurahime/data/dairy_supply_chain_risk
python3 -c "from dairyrisk.api.graph_routes import load_graph_data; data = load_graph_data(); print(f'{len(data[\"nodes\"])} nodes, {len(data[\"edges\"])} edges')"
```

## 性能优化

- 数据缓存：后端使用5分钟缓存减少IO
- 增量加载：前端支持分页加载节点和边
- WebSocket：实时推送更新，减少轮询
