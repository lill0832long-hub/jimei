# 每日工作日志

## 2026-07-17

### 完成的工作

#### 1. 项目验证
- 验证 V5.1 财务系统运行正常（端口 8090，NiceGUI 3.13.0）
- 确认依赖完整（FastAPI 0.136.3, Uvicorn 0.49.0, SQLAlchemy 2.0.50 等）
- 依赖安装在 `.pip-packages/`，通过 PYTHONPATH 注入

#### 2. Git 仓库整理（3472 文件 → 0）
- **根因**: `.gitignore` 损坏（BOM + CRLF + 第68行语法错误 `test_*.py.pip-packages/`）
- 清理并重写 `.gitignore`，提交 3 个文件
- 升级 nicegui 1.4→3.0，删除旧启动器 `run_server.py`
- 添加 `.pip-packages/` 到忽略列表

#### 3. GitHub 项目研究
- **AndrejKarpathy_2026_FocusProjects**: 7个AI系统工程项目（CodeLensAI/QueryForge/VentureMind）
- **QuantDinger**: 开源 AI 量化交易基础设施（Agent Gateway + MCP Server + 多券商）

#### 4. A股风云修复（核心工作）

**启动问题修复**:
- config.json 路径 `F:\学习` → `F:\study`（WinError 267）
- 修复 PYTHONPATH `astock-pkg` → 系统 Python + 依赖

**数据引擎重建（5项全完成）**:

| 指标 | 修复前 | 修复后 |
|------|--------|--------|
| 情绪样本 | 23 只 | **4997 只** |
| 板块覆盖 | 0 个 | **49 个** |
| 资金流 | 失真数据 | **真实北向 + 成交额** |
| 情绪加权 | 无 | **等权 + 市值加权** |
| 历史追踪 | 无 | **60天 + 均线** |

**前端修复**:
- JS 语法错误（缺引号）→ 整页崩溃
- showStockDetail 导出到 window.Dashboard → onclick 找到函数
- 折叠区域自动展开
- POST /api/refresh 实时生成 + 渲染

**API 审计**:
- 可用: `kamt.rtmin`（北向实时）+ `kamt.kline`（北向日K）
- 封锁: `clist`、`ulist.np`、`stock/fflow/daykline`

### 待明天继续
- 前端板块渲染验证
- 概念板块接入（百度 + 申万）
- 行业资金流前端展示
- 情绪历史趋势迷你图

---

## 2026-06-11

### 完成的工作

#### 1. 硬件监控尝试
- 用户要求监控 CPU 温度
- 尝试了多种方式：WMI、LibreHardwareMonitor .NET API、systeminformation npm 包
- 全部失败：LibreHardwareMonitor WMI Provider 未注册，.NET API 返回空
- **教训**: 遇到反复失败时应该更早停下来，直接问用户要结果

#### 2. 发现 A股风云项目
- 用户提醒之前做过 A股风云
- 在 `memory/portal.md` 中找到线索
- 定位到 `F:\学习\A股风云`，端口 9200
- 修改了 `api_server.py`、`tdx_service.py`、`dashboard.js`、`index.html`

#### 3. 教训：没有记录工作内容
- 用户指出 A股风云是我做的，但 memory 目录是空的
- **根因**: 每次对话结束前没有按 CLAUDE.md 规范写入 daily-log.md
- **教训**: 每次对话结束前必须检查是否有值得记录的内容
- 已创建 `memory/projects/a股风云.md` 记录项目信息

---

## 2026-06-04

### 完成的工作

#### 1. 对话连贯性问题自我审查
- **问题**: 用户说"让我直接用命令行搜索"，我却回复"你想搜什么？"
- **根因**: 对话上下文中已有足够信息（前序对话读取了多个大文件），我却丢失了连贯性
- **教训**:
  - 对话中已有明确上下文时，不要反问用户已经暗示的意图
  - 大文件被压缩后，应主动重新读取而非假装不知道
  - 先执行再确认，比先确认再执行更高效

### 关键经验

1. **主动执行 > 被动询问** — 当上下文足够时直接做，不要给用户"布置作业"的感觉
2. **对话连贯性是核心能力** — 前序对话读取的文件、用户暗示的意图，都应作为当前决策的依据
3. **工作目录复杂时先扫描** — 文件多不是问题，不主动定位才是问题

---

## 2026-05-17

### 完成的工作

#### 1. 登录页面 CSS 缺失修复
- **问题**: `auth.py` 使用了 12 个 CSS 类，但 `style.css` 中完全没有对应规则
- **根因**: sidebar CSS 重写时，登录页样式被遗漏
- **修复**: 追加完整登录页样式块（`.login-page` 全屏覆盖深蓝渐变、`.login-card` 白色 400px 卡片、`.login-submit-btn` 紫色渐变按钮等 12 个类）
- **验证**: 12 个 CSS 类与 auth.py 逐一交叉检查匹配，服务 HTTP 200

#### 2. Sidebar CSS 全面重设
- 设计语言: Revolut（深色金融科技）+ Linear（极简 SaaS）
- 背景 `#0a0e27`，强调色 `#6366f1`，宽度 `210px`

#### 3. 15 个 Bug 修复（多 Agent 交叉检测）
- `report_repository.py`: N+1 查询 → 批量 GROUP BY
- `voucher_repository.py`: 借贷平衡校验、ledger_id 过滤、update_status 同步
- `journal_form_v2.py`: JS undefined/null 守卫
- `report_service.py`: 利润表净额计算、现金流连接泄漏
- `connection.py`: `conn.close()` → `release_conn()`
- `close_period.py`: pending_review 凭证检查、缺失 import
- `reports_export.py`: 资产负债表/利润表字典迭代修复
- `ui_helpers.py`: navigate 保留 voucher_no、sidebar RuntimeError 处理
- `voucher_service.py`: 状态机校验（draft→pending_review→approved→posted）

#### 4. 版本号统一 V3 → V5.1
- `app.py`: `VERSION = "5.1.0"`, `VERSION_NAME = "V5.1"`
- `settings.py`、`ui_helpers.py` 同步更新

### 关键经验

1. **CSS 类遗漏是静默故障** — HTML 引用了不存在的 CSS 类不会报错，只表现为样式不对。应建立交叉检查机制
2. **Edit 工具 tab 编码陷阱** — Windows 文件 tab/space 编码问题可导致 Edit old_string 静默匹配失败。用 Python 脚本通过 Bash 做文件替换更可靠
3. **版本号多处硬编码** — 版本信息分散在多个文件，未来应考虑单一来源 `__version__.py`
4. **WSL 同步路径** — `E:\ClaudeCode\my-project` ↔ `/mnt/e/ClaudeCode/my-project`
