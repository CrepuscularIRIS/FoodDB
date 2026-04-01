# ModeB MediaCrawler 前端使用说明（2026-04-01）

## 页面入口

- 首页入口卡片：`MediaCrawler 舆情中心 (Mode B)`
- 顶部导航入口：`ModeB 舆情`
- 直达路由：`/modeb-opinion`

## 功能说明

1. 导入配置
- MediaCrawler 数据目录
- 企业主档 CSV
- 平台（all/weibo/douyin/xhs/zhihu/bili/kuaishou）
- 时间窗口天数

2. 一键导入
- 按钮：`抓取结果导入 ModeB`
- 调用接口：`POST /modeb/opinion/import`

3. 摘要与 Top
- 导入摘要：`GET /modeb/opinion/summary`
- Top 企业：`GET /modeb/opinion/top`

4. ModeB 联动评估
- 输入症状/舆情描述
- 调用接口：`POST /symptom/assess`
- 返回中包含舆情增强字段：
  - `opinion_risk_index`
  - `opinion_mentions_30d`
  - `combined_risk_score`

## 注意

该页面负责接入 MediaCrawler 本地已抓取语料并导入分析。
若需“实时登录平台并抓取”，仍需先在 MediaCrawler 侧完成登录与抓取任务。
