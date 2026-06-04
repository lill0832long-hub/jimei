# 每日工作日志

## 2026-05-17

### 完成的工作

#### 1. 登录页面 CSS 缺失修复
- **问题**: `auth.py` 使用了 12 个 CSS 类，但 `style.css` 中完全没有对应规则
- **根因**: sidebar CSS 重写时，登录页样式被遗漏
- **修复**: 追加完整登录页样式块（`.login-page` 全屏覆盖深蓝渐变、`.login-card` 白色 400px 卡片、`.login-submit-btn` 紫色渐变按钮等 12 个类）
- **验证**: 12 个 CSS 类与 auth.py 逐一交叉检查匹配，服务 HTTP 200

#### 2. Sidebar CSS 全面重设计
- 设计语言: Revolut（深色金融科技）+ Linear（极简 SaaS）
- 背景 `#0a0e27`，强调色 `#6366f1`，宽度 `210px`

#### 3. 15 个 Bug 修复（多 Agent 交叉检测）
- `report_repository.py`: N+1 查询 → 批量 GROUP BY
- `voucher_repository.py`: 借贷平衡校验、ledger_id 过滤、update_status 同事务
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

1. **CSS 类遗漏是静默故障** — HTML 引用了不存在的 CSS 类不会报错，只表现为样式不对。应建立交叉检查机制。
2. **Edit 工具 tab 编码陷阱** — Windows 文件 tab/space 编码问题可导致 Edit old_string 静默匹配失败。用 Python 脚本通过 Bash 做文件替换更可靠。
3. **版本号多处硬编码** — 版本信息分散在多个文件，未来应考虑单一来源 `__version__.py`。
4. **WSL 同步路径** — `E:\ClaudeCode/my-project` ↔ `/mnt/e/ClaudeCode/my-project`
