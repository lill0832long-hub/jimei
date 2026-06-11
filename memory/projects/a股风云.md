---
name: a股风云
description: A股实时行情看板系统，端口9200，含Serenity评分
metadata:
  type: project
---

## A股风云

- **路径**: `F:\学习\A股风云`
- **端口**: 9200
- **入口**: `api_server.py`
- **描述**: A股风云看板（实时行情 + Serenity评分）
- **仓库**: git branch `main`
- **启动**: `python api_server.py`

### 核心模块
- `api_server.py` — 主服务
- `tdx_service.py` — 通达信数据服务
- `dashboard/index.html` + `dashboard.js` — 前端看板
- `eastmoney_fundflow.py` — 东方财富资金流向
- `eastmoney_research.py` — 东方财富研报
- `research_scorer.py` — 研报评分
- `sentiment_aggregator.py` — 情绪聚合
- `sina_news.py` — 新浪新闻
- `summary_generator.py` — 摘要生成
- `realtime_pusher.py` — 实时推送

### 关联项目
- **Lucianus Portal** `D:\网关启动开关 2` — 统一门户，管理所有服务
- Portal 配置: `config.json` 中注册，端口 9200
