# CLAUDE.md — V5.1 AI 财务系统

## gstack

Use the `/browse` skill from gstack for all web browsing. Do NOT use `mcp__claude-in-chrome__*` tools.

### Available gstack skills

`/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/design-shotgun`, `/design-html`, `/review`, `/ship`, `/land-and-deploy`, `/canary`, `/benchmark`, `/browse`, `/connect-chrome`, `/qa`, `/qa-only`, `/design-review`, `/setup-browser-cookies`, `/setup-deploy`, `/setup-gbrain`, `/retro`, `/investigate`, `/document-release`, `/codex`, `/cso`, `/autoplan`, `/plan-devex-review`, `/devex-review`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`, `/learn`, `/explore`, `/code-simplifier`

---

## 项目目录树（V5.1）

> 每次 Phase 1 Explore 时对照此树定位文件。

```
E:\ClaudeCode\my-project/
├── app.py                          # 入口（VERSION_NAME = "V5.1"）
├── requirements.txt
├── app/
│   ├── config.py                   # 页面路由注册
│   ├── routes.py                   # API 路由注册
│   ├── components/
│   │   ├── state.py                # 全局状态（含钻取通信字段）
│   │   ├── ui_components.py        # 可复用 UI 组件
│   │   └── ui_helpers.py           # UI 辅助函数（含报表钻取 JS bridge）
│   ├── pages/                      # 页面渲染（不直接调数据库）
│   │   ├── auth.py                 # 登录/认证
│   │   ├── dashboard.py            # 仪表盘
│   │   ├── settings.py             # 系统设置
│   │   ├── setup_wizard.py         # 初始化向导
│   │   ├── general_ledger.py       # 总分类账（钻取目标页）
│   │   ├── journal_list.py         # 凭证列表（钻取目标页）
│   │   ├── journal_form.py         # 凭证表单
│   │   ├── journal_form_v2.py      # 凭证表单 v2
│   │   ├── reports_center.py       # 报表中心（钻取来源页，含 tab 系统）
│   │   ├── reports.py / reports_balance_sheet.py / reports_income_statement.py
│   │   ├── account_ledger.py       # 科目明细账
│   │   ├── bank_reconciliation.py  # 银行对账
│   │   ├── budget.py               # 预算管理
│   │   ├── cash_flow.py / cash_flow_statement.py  # 现金流
│   │   ├── fixed_assets.py         # 固定资产
│   │   ├── invoices.py             # 发票管理
│   │   ├── tax.py                  # 税务管理
│   │   ├── auxiliary.py            # 辅助核算
│   │   ├── multi_currency.py       # 多币种
│   │   ├── import_export.py        # 导入导出
│   │   ├── charts.py               # 图表
│   │   ├── compare.py              # 对比分析
│   │   ├── close_period.py         # 期末结账
│   │   ├── trial_balance.py        # 试算平衡表
│   │   ├── voucher_template.py     # 凭证模板
│   │   ├── scheduled_vouchers.py   # 计划凭证
│   │   ├── ai_assistant.py         # AI 助手
│   │   └── ...
│   ├── repository/                 # 仓库层（数据库查询封装）
│   │   ├── base.py                 # 基础仓库
│   │   ├── account_repository.py
│   │   ├── budget_repository.py
│   │   ├── fixed_asset_repository.py
│   │   ├── invoice_repository.py
│   │   ├── ledger_repository.py
│   │   ├── period_repository.py
│   │   ├── report_repository.py
│   │   ├── tax_repository.py
│   │   ├── voucher_repository.py
│   │   └── ...
│   ├── services/                   # 服务层（封装仓库，供页面调用）
│   │   ├── account_service.py
│   │   ├── budget_service.py
│   │   ├── fixed_asset_service.py
│   │   ├── ledger_service.py
│   │   ├── report_service.py
│   │   ├── tax_service.py
│   │   ├── voucher_service.py
│   │   └── ...
│   ├── models/                     # ORM 模型
│   │   ├── base.py / mixins.py
│   │   ├── account.py / voucher.py / ledger.py
│   │   ├── invoice.py / tax.py / fixed_asset.py
│   │   ├── budget.py / cash_flow_category.py
│   │   └── ...
│   ├── static/
│   │   ├── script.js               # 前端主脚本（导航桥接等）
│   │   ├── annotation.js           # 页面标注工具
│   │   └── style/                  # CSS 模块化（11文件）
│   │       ├── index.css           # CSS 入口（@import 其他模块）
│   │       ├── tokens.css          # CSS 变量（设计令牌）
│   │       ├── base.css            # 基础重置
│   │       ├── header.css          # 顶部导航栏
│   │       ├── sidebar.css         # 左侧边栏
│   │       ├── components.css      # 通用组件
│   │       ├── dashboard.css       # 仪表盘
│   │       ├── journal.css         # 凭证表格
│   │       ├── reports.css         # 报表
│   │       ├── login.css           # 登录页
│   │       └── responsive.css      # 响应式
│   └── utils/
│       ├── pdf.py                  # PDF 导出
│       └── period.py               # 会计期间工具
├── database/                       # 数据库子模块（底层 SQL 操作）
│   ├── connection.py               # 数据库连接
│   ├── init_data.py                # 初始化数据
│   ├── account.py / voucher.py / ledger.py
│   ├── invoice.py / tax.py / fixed_asset.py
│   ├── budget.py / cash_flow.py / report.py
│   └── ...
└── tests/                          # 测试
    ├── conftest.py
    ├── run_all.py                  # 一键验证入口
    ├── test_render.py              # 渲染测试
    ├── test_browser_ui.py          # 浏览器 UI 测试
    └── test_css_modules.py         # CSS 模块测试
```

### 调用链路速查

```
用户点击 → pages/xx.py → services/xx_service.py → repository/xx_repository.py → database/xx.py → DB
                ↑ 返回值             ↑ 返回值               ↑ SQL 查询
```

### 关键文件速查

| 需求 | 入口文件 |
|------|---------|
| 新增页面 | `app/pages/` + `app/config.py` + `app/routes.py` |
| 新增 API | `app/routes.py` |
| 数据查询逻辑 | `app/repository/` |
| 业务逻辑 | `app/services/` |
| 页面样式 | `app/static/style/` 对应模块 CSS |
| JS 交互 | `app/static/script.js` |
| 报表钻取 | `state.py` + `ui_helpers.py` + `reports_center.py` + `general_ledger.py` |
| 全局状态 | `app/components/state.py` |

---

## 开发工作流（Development Workflow）

每次改代码必须按以下流程执行，不可跳过：

### Phase 1: Explore — 画项目地图

**接到需求后，先不动手，先建立全局视角。**

1. 识别入口：找到请求涉及的核心文件（页面、路由、服务）
2. 追调用链路：入口 → 服务层 → 数据库层，理清数据流
3. 记录依赖关系：哪些模块会受本次改动影响
4. 输出：在回复中简要说明"我读了哪些文件，调用链路是什么"

**为什么先读后写：** 避免重复造轮子，避免改了 A 坏了 B，避免在错误的地方改代码。

> 💡 调用 `/learn` 技能可以快速探索陌生代码库。

### Phase 2: Debugger — 定位根因

**有 bug 时，必须走调试流程，不可直接改。**

1. 复现：稳定复现 bug，收集日志和错误输出
2. 定位：缩小范围到具体层（UI / 服务 / 数据库）
3. 精简：创建最小复现用例
4. 修复根因：问"为什么会发生"直到找到真正原因
5. 防护：写测试/检查防止复发
6. 验证：确认修复有效

> 💡 调用 `/investigate` 技能执行系统化调试。

### Phase 3: Code Review — 查漏洞和边界条件

**改完代码后，自我审查再提交。**

按以下维度检查：
1. **正确性** — 边界情况？错误路径？
2. **可读性** — 命名清晰？控制流直接？
3. **架构** — 符合现有模式？依赖方向正确？
4. **安全性** — 输入验证？注入风险？
5. **性能** — N+1 查询？无界循环？

审查严重性标签：`Critical`（阻塞）/ `Nit`（轻微）/ `Optional`（建议）

> 💡 调用 `/review` 技能做 PR 级代码审查。

### Phase 4: Test Engineer — 判断该补哪些测试

**每次改动后评估测试策略：**

1. 这个改动的风险点在哪？
2. 现有测试能否覆盖？
3. 需要补哪些测试？（单元测试 / 集成测试 / E2E）
4. 好的测试应验证意图和行为，不是为了通过测试

> 💡 调用 `/qa` 技能测试 Web 应用并修复发现的问题。

### Phase 5: Code Simplifier — 删冗余清结构

**改动完成后，检查是否可以简化：**

1. 嵌套超过 3 层？→ 提取 guard clause
2. 函数超过 50 行？→ 拆分小函数
3. 重复逻辑？→ 提取共享函数
4. 死代码、注释掉的块？→ 直接删除
5. 通用命名（data/result/temp）→ 改为描述性命名

**注意：** 只简化本次改动相关的代码，不做无关重构。遵循 Chesterton's Fence 原则——不理解的东西先研究再动。

> 💡 使用 `/simplify` 技能（bundled）执行代码简化。

### Phase 6: Security Review — 扫安全边界

**涉及以下模块时，必须做安全审查：**

- **登录/认证** — 密码哈希、会话管理、速率限制
- **权限控制** — 每个端点检查权限、用户只能访问自己的资源
- **支付/金额** — 金额计算精度、并发控制、幂等性
- **输入验证** — 所有用户输入在边界验证、SQL 参数化
- **敏感数据** — 不在日志中记录、不在 API 响应中暴露

> 💡 调用 `/cso` 技能做安全专项审查。

---

## 调试流程（Debugging and Error Recovery）

参考 addyosmani/agent-skills 的五步调试法。

### Stop-the-Line 规则

出现任何异常时：
1. **停止**添加新功能或做其他修改
2. **保留**证据（错误输出、日志、复现步骤）
3. **诊断**使用下方检查清单
4. **修复**根因
5. **防护**防止复发
6. **验证**通过后才能继续

### 五步调试检查清单

**Step 1: 复现** — 让失败稳定复现。无法复现就无法自信修复。
- 收集日志、环境信息、对比已知正常版本
- Python: 用最小代码隔离复现问题

**Step 2: 定位** — 缩小失败范围到具体层。
- UI 层 → 检查 NiceGUI 渲染逻辑、state 状态
- 服务层 → 检查 service 函数输入输出
- 数据库层 → 检查 SQL 查询、数据完整性
- 回归定位 → `git bisect`

**Step 3: 精简** — 创建最小复现用例，移除无关代码。

**Step 4: 修复根因** — 修复根本原因，不是症状。问"为什么会发生？"直到找到真正原因。

**Step 5: 防护** — 写一个能捕获此 bug 的测试/检查，确保不会复发。

### 常见借口反驳

| 借口 | 现实 |
|------|------|
| "我直接知道 bug 在哪，直接修" | 70% 的情况下你是对的，剩下 30% 浪费数小时。先复现。 |
| "这个测试可能有问题" | 验证这个假设。如果测试有问题就修测试，不要跳过。 |
| "在我机器上能跑" | 检查环境差异、依赖版本、数据差异。 |
| "下一个 commit 再修" | 现在就修。下一个 commit 会在这个 bug 之上引入新 bug。 |
| "这是个偶发问题，忽略" | 偶发 bug 会掩盖真正的问题。找到偶发原因。 |

---

## 代码审查（Code Review and Quality）

参考 addyosmani/agent-skills 的五维审查框架。合并前必须经过审查。

### 五维审查

1. **正确性** — 代码是否做了声称要做的事？边界情况？错误路径？
2. **可读性** — 另一个工程师能否不看作者解释就理解？命名是否描述性？控制流是否直接？
3. **架构** — 是否符合现有模式？模块边界是否清晰？依赖方向是否正确？
4. **安全性** — 用户输入是否验证？是否有注入风险？敏感数据是否暴露？
5. **性能** — 是否有 N+1 查询？是否有无界循环？

### 变更大小

- ~100 行 → 理想，一次可审查完
- ~300 行 → 可接受，如果是单一逻辑变更
- ~1000 行 → 太大，必须拆分

### 提交信息格式

```
<type>: <简短描述>

<可选 body，解释为什么而不是什么>
```

type: `feat` | `fix` | `refactor` | `test` | `docs` | `chore`

### 审查严重性标签

| 标签 | 含义 | 作者必须 |
|------|------|----------|
| *(无前缀)* | 必须修改 | 合并前处理 |
| **Critical:** | 阻塞合并 | 安全漏洞/数据丢失/功能损坏 |
| **Nit:** | 轻微，可选 | 可以忽略 |
| **Optional:** / **Consider:** | 建议 | 值得考虑但不强制 |
| **FYI** | 仅信息 | 无需操作 |

### 常见借口反驳

| 借口 | 现实 |
|------|------|
| "能跑就够了" | 能跑但难读、不安全、架构错误的代码会积累债务。 |
| "我写的所以我知道是对的" | 作者对自己的假设视而不见。每份变更都需要另一双眼睛。 |
| "以后再清理" | 以后从不来。在合并前要求清理。 |
| "AI 生成的代码应该没问题" | AI 代码需要更多审查，不是更少。它自信且合理，即使是错的。 |
| "测试通过了所以没问题" | 测试是必要但不充分的。不捕获架构问题、安全问题、可读性问题。 |

---

## 代码简化（Code Simplification）

参考 addyosmani/agent-skills 的简化原则。目标是更容易理解，不是更少行。

### 五大原则

1. **精确保留行为** — 只改表达方式，不改功能。所有输入、输出、副作用、错误行为必须一致。
2. **遵循项目约定** — 先读项目代码风格，再简化。简化不等于改成你的个人偏好。
3. **清晰优于巧妙** — 显式代码优于需要脑内解析的紧凑代码。
4. **保持平衡** — 不要过度简化：不要内联有名字的 helper，不要合并不相关逻辑。
5. **范围控制** — 默认只简化最近修改的代码，不做无关的重构。

### Chesterton's Fence

修改任何代码前，先理解它为什么存在。如果看到不理解的东西，不要先拆掉它——先研究原因。

### 简化检查清单

- 嵌套超过 3 层？→ 提取为 guard clause 或 helper
- 函数超过 50 行？→ 拆分为专注的小函数
- 嵌套三元表达式？→ 用 if/else 或查找表替换
- 同一条件在多处重复？→ 提取为命名良好的 predicate 函数
- 通用命名（`data`, `result`, `temp`）→ 改为描述性命名
- 注释解释"做了什么"→ 删除（代码本身应该说明）
- 注释解释"为什么"→ 保留
- 重复逻辑 5+ 行？→ 提取为共享函数
- 死代码、不可达分支、注释掉的块？→ 删除

### 增量修改

每次只做一个简化，运行测试后再做下一个。重构变更与功能变更分开提交。

---

## 安全加固（Security and Hardening）

参考 addyosmani/agent-skills 的三层边界系统。

### 三层边界

**始终执行（无例外）：**
- 在系统边界验证所有外部输入
- 所有数据库查询参数化（不拼接用户输入）
- 敏感数据不写入日志、不提交到版本控制
- 使用 HTTPS 进行外部通信
- 运行依赖审计（`pip audit` 或 `safety check`）

**先问再做（需人工批准）：**
- 添加新的认证/授权流程
- 存储新的敏感数据类别
- 添加新的外部服务集成
- 修改 CORS 配置
- 添加文件上传处理

**永远不做：**
- 永远不在代码中提交密钥
- 永远不记录敏感数据
- 永远不信任客户端验证作为安全边界
- 永远不向用户暴露堆栈跟踪或内部错误详情
- 永远不存储明文密码

### 安全检查清单

```markdown
### 认证
- [ ] 密码哈希存储（不存明文）
- [ ] 登录有速率限制

### 授权
- [ ] 每个端点检查用户权限
- [ ] 用户只能访问自己的资源

### 输入
- [ ] 所有用户输入在边界验证
- [ ] SQL 查询参数化
- [ ] 输出编码/转义

### 数据
- [ ] 代码和 git 历史中无密钥
- [ ] API 响应中排除敏感字段
```

---

## Memory 管理

### 对话结束前必做

每次对话结束（compaction 前、用户说"结束"、或自然结束时），检查本次对话是否有值得记录的内容，有则按 `_COMPRESSION_RULES.md` 规范写入 `memory/daily/daily-log.md`。

### 反复修正检测

对话中同一文件同一位置被 Edit 2 次以上，或用户说"还是不对"/"又出问题了"，必须用 `[recurring]` 标记提炼教训，写入 daily-log.md，并在 MEMORY.md 中用 🔴 标记。

### 读取规则

每次会话启动，先读 MEMORY.md 和 user_identity.md，有 🔴 标记的条目优先处理。

---

## Git 工作流（Git Workflow）

参考 addyosmani/agent-skills 的 trunk-based 开发模式。

### 核心原则

1. **早提交，常提交** — 每个成功的增量单独提交，不要累积大量未提交变更。
2. **原子提交** — 每个提交只做一件事。
3. **描述性信息** — 提交信息解释为什么，不只是什么。
4. **关注点分离** — 格式化变更不与行为变更混合，重构不与功能混合。
5. **控制变更大小** — 目标 ~100 行/提交，超过 ~1000 行必须拆分。

### 分支策略

- `main` 始终可部署
- 功能分支短期存活（1-3 天内合并）
- 合并后删除分支
- 分支命名: `feature/<描述>` | `fix/<描述>` | `refactor/<描述>` | `chore/<描述>`

### Save Point 模式

```
开始工作
  ├── 做变更
  │   ├── 测试通过 → 提交 → 继续
  │   └── 测试失败 → 回退到最后提交 → 排查
  └── 功能完成 → 所有提交形成干净历史
```

### 变更摘要格式

修改完成后提供结构化摘要：
```
变更内容：
- 文件A：做了X
- 文件B：做了Y

有意未触碰：
- 文件C：有类似问题但超出范围

潜在顾虑：
- 改动D可能影响Z，请确认
```

### 提交前检查

1. `git diff --staged` — 检查即将提交的内容
2. 检查无密钥泄露
3. 运行测试
4. 运行 lint / 类型检查

---

## 项目约定

### 架构模式

- **服务层模式**：页面不直接调用 `database/`，通过 `app/services/` → `app/repository/` 访问数据
- **统一 UI 组件**：使用 `app/components/ui_helpers.py` 中的共享组件
- **CSS 变量**：使用 `app/static/style/tokens.css` 中定义的设计令牌（index.css 为入口）
- **版本**：V5.1，入口 `app.py` 中 `VERSION_NAME = "V5.1"`

### Python 规范

- 使用 `dict.get()` 而非 `dict['key']` 访问字典
- 浮点数转换用 `float(value or 0)` 而非 `float(value)`（防止 None 崩溃）
- 布尔值判断用 `is not None` / `is None` 而非 `or`（防止 0 被当 falsy 跳过）
- 服务层函数签名必须与底层数据库函数保持一致

### 文件结构

```
app/
├── components/       # 共享 UI 组件（state.py, ui_helpers.py, ui_components.py）
├── config.py         # 页面路由注册
├── pages/            # 页面渲染函数（不直接调数据库）
├── routes.py         # API 路由注册
├── repository/       # 仓库层（数据库查询封装）
├── services/         # 服务层（封装仓库，供页面调用）
├── models/           # ORM 模型
├── static/           # CSS / JS（style/ 下 11 个 CSS 模块）
│   ├── script.js     # 前端主脚本
│   ├── annotation.js # 标注工具
│   └── style/        # CSS 模块化
└── utils/            # 工具函数（pdf, period）
database/             # 数据库子模块（底层 SQL 操作）
```
