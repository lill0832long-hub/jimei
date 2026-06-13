---
name: all-projects
description: 当前所有项目汇总 — 端口、路径、启动方式
metadata:
  type: reference
---

## 所有项目汇总

| 项目 | 端口 | 路径 | 入口 | 说明 |
|------|------|------|------|------|
| AI财务系统 V5.1 | 8090 | `E:\ClaudeCode\my-project\` | `app.py` | NiceGUI，当前工作目录 |
| A股风云 | 9200 | `F:\学习\A股风云\` | `api_server.py` | Uvicorn，实时行情看板 + Serenity评分 |
| Lucianus 门户 | 9090 | `D:\网关启动开关 2\` | `portal.py` | HTTP 门户，统一管理系统 |
| OpenClaw | 3000 | `F:\openclaw\` | `openclaw gateway run` | AI Gateway |
| Remotion Studio | 3002 | — | — | 视频编辑工作台 |

### 启动命令

- **AI财务系统**: `cd E:\ClaudeCode\my-project && python app.py`
- **A股风云**: `python F:\学习\A股风云\api_server.py`
- **Lucianus 门户**: `cd /d "D:\网关启动开关 2" && pythonw portal.py`

### 关联关系
- Lucianus 门户（9090）统一管理所有服务的启停（通过 `config.json` 注册）
- Portal 中的 `/api/start`、`/api/stop`、`/api/restart` 可远程管理各服务
