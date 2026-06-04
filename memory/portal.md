---
name: lucianus-portal
description: Lucianus 统一门户 — 端口 9090，系统管理 + 知识库
metadata:
  type: project
---

## Lucianus 统一门户

- **访问地址**: http://127.0.0.1:9090
- **程序目录**: `D:\网关启动开关 2\`
- **主程序**: `portal.py`
- **启动命令**: `cd /d "D:\网关启动开关 2" && pythonw portal.py`
- **端口**: 9090
- **PID**: 10200（当前运行中）

## 架构

```
/           → 门户首页（模块卡片导航）
/manager    → 系统启动管理器（服务管理、启停、日志）
/kb/*       → 知识库（iframe 嵌入）
/api/*      → 管理 API
```

## 核心文件

| 文件 | 说明 |
|------|------|
| `portal.py` | 主程序（HTTP 服务器 + 路由） |
| `portal_wrapper.py` | 启动包装器（自动重启、日志捕获） |
| `portal_control.pyw` | 控制面板 GUI |
| `dashboard.py` | 仪表盘 |
| `config.json` | 系统配置（所有服务定义） |
| `start_portal.vbs` | VBS 启动脚本 |

## Portal 子模块（`portal/`）

| 文件 | 说明 |
|------|------|
| `utils.py` | 工具函数（配置读写、端口检查、日志） |
| `wsl_manager.py` | WSL 服务管理 |
| `health.py` | 健康检查循环 |
| `kb_search.py` | 知识库搜索 |
| `templates/manager.html` | 管理器前端页面 |

## 知识库模块（`modules/knowledge_base/`）

- `repo/` — LLM 从零实现（llms_from_scratch 包 + ch02-ch07 章节代码，148+ Python 文件）
- `transformer-explainer/` — Transformer 可视化解释器
- `cnn-explainer/` — CNN 可视化解释器
- `server.py` — 知识库服务器

## config.json 中注册的服务

| 服务 | 端口 | 说明 |
|------|------|------|
| 9090 Portal | 9090 | 统一门户（自身） |
| OpenClaw | 18789 | AI Gateway |
| AI财务系统 | 8090 | AI Finance System V5.1 |
| A股风云 | 9200 | 实时行情看板 |
| Remotion Studio | 3002 | 视频编辑工作台 |

## API 接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取所有服务状态 |
| `/api/config` | GET | 获取配置 |
| `/api/log` | GET | 获取日志 |
| `/api/search` | GET | 搜索（服务 + 知识库） |
| `/api/start` | POST | 启动服务 |
| `/api/stop` | POST | 停止服务 |
| `/api/restart` | POST | 重启服务 |
| `/api/start-all` | POST | 启动所有 autoStart 服务 |
| `/api/stop-all` | POST | 停止所有服务 |
| `/api/add` | POST | 添加服务 |
| `/api/remove` | POST | 删除服务 |

## 启动方式（Node.js）

```javascript
const { execSync } = require('child_process');
execSync('cmd /c "cd /d D:\\网关启动开关 2 && F:\\tools\\Python311\\pythonw.exe portal.py"');
```

## 注意事项
- 使用 `pythonw.exe` 启动（无控制台窗口）
- wrapper 会自动重启崩溃的服务
- 日志文件：`D:\网关启动开关 2\logs\wrapper.log`
- 知识库搜索索引在启动时构建
