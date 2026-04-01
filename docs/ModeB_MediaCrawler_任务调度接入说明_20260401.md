# ModeB MediaCrawler 任务调度接入说明（2026-04-01）

## 本次新增

1. 后端新增抓取任务接口：
- `POST /modeb/opinion/crawl/start` 启动抓取（单任务模式）
- `GET /modeb/opinion/crawl/status` 查看状态与日志尾部
- `POST /modeb/opinion/crawl/stop` 停止抓取

2. 后端增强
- 增加平台映射（`weibo<->wb`、`douyin<->dy`、`kuaishou<->ks`）
- 增加 `python backend/api.py` 启动时的舆情模块回退导入，避免 `backend.opinion_module` 导入失败
- `opinion_module` 支持平台别名目录扫描（避免目录命名差异导致漏扫）

3. 前端新增
- `app/modeb-opinion/page.tsx` 增加“MediaCrawler 抓取任务”区域：
  - 配置 `MediaCrawler 根目录 / 平台 / 关键词`
  - 按钮：启动抓取、停止抓取、刷新状态
  - 实时显示任务状态、PID、命令、日志路径、日志尾部
- 保留原有“导入结果 -> Top企业 -> ModeB联动测试”流程

## 关键文件

- `backend/api.py`
- `backend/opinion_module.py`
- `frontend/app/modeb-opinion/page.tsx`
- `frontend/lib/api.ts`
- `frontend/types/index.ts`

## 自测结果

1. 后端接口
- `GET /modeb/opinion/crawl/status`：返回 `success=true`，支持 `tail_lines`
- `POST /modeb/opinion/crawl/start`：可启动任务，返回 `status=running`、`pid`、`log_path`
- `POST /modeb/opinion/crawl/stop`：可终止任务（若任务已结束则返回当前状态）

2. 舆情导入接口
- `POST /modeb/opinion/import`（`platform=all`）可正常导入，当前数据下 `matched_records=33`、`matched_enterprises=11`

3. 前端
- `npm run build` 通过
- `/modeb-opinion` 页面可打开并展示新任务面板

## 运行方式

### 后端
```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk
python backend/api.py
```

### 前端
```bash
cd /home/yarizakurahime/data/dairy_supply_chain_risk/frontend
npm run dev -- --hostname 127.0.0.1 --port 3001
```

访问：`http://127.0.0.1:3001/modeb-opinion`

## 使用建议（联调顺序）

1. 在“MediaCrawler 抓取任务”中启动抓取，确认状态为 `running`。
2. 抓取结束后，点击“抓取结果导入 ModeB”。
3. 查看“导入摘要”和“舆情风险 Top 企业”。
4. 在“Mode B 联动测试”输入症状文本，检查企业列表中的舆情增强字段。
