# AI 财务系统 — 开发日志

## V3.0.0 (2026-05-14) — 当前版本

### 架构重构（Week 1-5）
- **Week 1**: SQLAlchemy ORM 模型层（32 表，含 mixins、索引、外键约束）
- **Week 2**: Repository 层 + Service 层迁移
- **Week 3**: 消除所有 database_v3 直接依赖
- **Week 4**: 固定资产 CRUD + 残余依赖清理
- **Week 5**: UI 精美修改 — 统一组件库 + CSS 动画

### 凭证系统
- 凭证表单 v4 — 传统 Excel 记账凭证风格（原生 HTML 表格）
- 凭证钻取功能
- 凭证列表月份筛选修复
- 凭证号生成逻辑优化

### 服务层修复
- LedgerService 字段映射修复
- FixedAsset 导入修复
- 报表对比函数修复
- user_id/operator_name 传给 ORM 构造函数导致 TypeError 修复
- Service 层 ORM 对象转 dict 修复（V3.2 崩溃修复）

### UI/UX 改进
- 登录/登出后页面跳转修复（改用 ui.navigate.to 整页刷新）
- 科目下拉菜单内联新增科目（去掉弹窗）
- 联想下拉框高度加大
- Dashboard / 导航 / 侧边栏改进
- 图文操作手册

### 其他
- 添加 Bug 追踪系统页面
- 财务系统端口恢复 8090
- 版本号系统建立（V3.0.0）

---

## V2 及更早
- V3 财务系统框架初始版本
- 账务处理模块全面 Bug 修复（15 个问题）
- 架构迁移：27 个页面从 database_v3 切换到服务层
