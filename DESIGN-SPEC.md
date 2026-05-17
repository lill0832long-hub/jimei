# AI 财务系统 V5.1 — 导航栏重设计规范

> 基于 awesome-design-md 项目中 Revolut / Stripe / Coinbase / Linear 的设计语言提炼

---

## 一、设计哲学

**目标：** 打造"专业财务 SaaS"级别的导航体验——深色侧边栏如同交易终端般精准克制，浅色顶部栏如同 Stripe 控制台般清晰高效。

**核心原则：**
- Sidebar = 深色沉浸式（Revolut fintech dark mode）
- Header = 浅色功能导向（Stripe dashboard clarity）
- 动效克制，只服务于状态反馈
- 信息层级分明，一眼定位

---

## 二、颜色系统

### 侧边栏（深色主题 — Revolut 风格）

```css
/* 主背景 — 深海军蓝，比纯黑更有层次 */
--sidebar-bg:           #0B1120;   /* 比当前 #0a0e27 略深，更沉稳 */
--sidebar-bg-hover:     rgba(255,255,255,0.04);
--sidebar-bg-active:    rgba(99,102,241,0.10);

/* 强调色 — Revolut 紫蓝 #494fdf 比 Linear #6366f1 更沉稳 */
--sidebar-accent:       #494fdf;
--sidebar-accent-light: #7c83f5;
--sidebar-accent-glow:  rgba(79,79,223,0.15);

/* 文字层级 */
--sidebar-text-primary:   rgba(255,255,255,0.88);   /* 菜单项文字 */
--sidebar-text-secondary: rgba(255,255,255,0.45);   /* 分组标题 */
--sidebar-text-muted:     rgba(255,255,255,0.28);   /* 折叠态图标 */
--sidebar-text-disabled:  rgba(255,255,255,0.18);   /* 不可点击 */

/* 分隔线 — 极细，几乎不可见 */
--sidebar-divider:        rgba(255,255,255,0.05);
--sidebar-divider-hover:  rgba(255,255,255,0.08);

/* Logo 区域 */
--sidebar-logo-bg:        transparent;
--sidebar-logo-text:      rgba(255,255,255,0.95);
--sidebar-logo-icon:      #494fdf;
```

### 顶部栏（浅色主题 — Stripe 风格）

```css
/* 主背景 — 纯白到极浅灰的微渐变 */
--header-bg:              #ffffff;
--header-bg-scrolled:     rgba(255,255,255,0.95);
--header-border:          rgba(0,0,0,0.06);

/* 文字 */
--header-text-primary:    #0d253d;   /* Stripe ink */
--header-text-secondary:  #64748d;   /* Stripe mute */
--header-text-inverse:    #ffffff;

/* 强调色 — 与 sidebar 统一 */
--header-accent:          #494fdf;

/* 阴影 — 极浅，分隔 header 和内容区 */
--header-shadow:          0 1px 3px rgba(0,0,0,0.04);
```

---

## 三、排版系统

### 侧边栏字体

| 元素 | 字号 | 字重 | 行高 | 字距 | 颜色 |
|------|------|------|------|------|------|
| Logo 文字 | 15px | 700 | 1.2 | -0.3px | `--sidebar-logo-text` |
| 分组标题 | 10px | 600 | 1.4 | 1.2px uppercase | `--sidebar-text-secondary` |
| 菜单项 | 13px | 500 | 1.4 | 0 | `--sidebar-text-primary` |
| 菜单项(选中) | 13px | 600 | 1.4 | 0 | `--sidebar-accent-light` |
| 版本标签 | 9px | 500 | 1 | 0.5px | rgba(255,255,255,0.35) |

**字体族：** `"Inter", "PingFang SC", "Microsoft YaHei", system-ui, sans-serif`
（用 Inter 替代 Nunito，Inter 是 fintech 标配，数字等宽显示更整齐）

### 顶部栏字体

| 元素 | 字号 | 字重 | 行高 | 字距 | 颜色 |
|------|------|------|------|------|------|
| 标题 | 18px | 700 | 1.2 | -0.2px | `--header-text-primary` |
| 账套选择 | 13px | 500 | 1.4 | 0 | `--header-text-primary` |
| 年月选择 | 14px | 600 | 1.4 | 0 | `--header-text-primary` |
| 用户名 | 13px | 500 | 1.2 | 0 | `--header-text-primary` |
| 角色标签 | 10px | 500 | 1 | 0.5px | `--header-text-secondary` |
| 版本标签 | 9px | 500 | 1 | 0.3px | `--header-text-secondary` |

---

## 四、布局规格

### 侧边栏

```
宽度（展开）：220px（比当前 210px 略宽，呼吸感更好）
宽度（折叠）：48px（比当前 52px 更紧凑）
Logo 区域高度：44px
分组标题高度：28px
菜单项高度：34px（比当前 32px 略高，点击区域更大）
菜单项左右间距：8px
分组间距：12px（用留白代替分隔线）
```

### 顶部栏

```
高度：52px（保持不变）
左右内边距：20px
网格：三列（左 1fr / 中 auto / 右 1fr）
Logo 图标尺寸：22px
Avatar 尺寸：28px
选择框高度：32px
```

---

## 五、组件设计

### 5.1 侧边栏 Logo

```
┌────────────────────────────┐
│  ⚖️  AI 财务系统    v5.1   │  ← 44px 高，图标 22px，文字 15px bold
└────────────────────────────┘
```
- 左侧 16px 内边距
- 图标颜色 `--sidebar-accent`
- 文字颜色 `--sidebar-logo-text`
- 版本号右对齐，9px 小字，rgba(255,255,255,0.35)
- 底部 1px 分割线 `--sidebar-divider`

### 5.2 分组标题

```
  ▾  WORK                    ← 10px uppercase, letter-spacing 1.2px
```
- 高度 28px，左侧 12px 内边距
- 图标 14px（仅折叠态显示，展开态隐藏）
- 文字 10px uppercase muted
- 右侧箭头 12px
- hover 时文字变亮，无背景变化
- **分组之间用 12px 留白分隔，不用线**

### 5.3 菜单项

```
展开态：
    📊  仪表盘              ← 13px, 14px 图标, 左 16px
    🤖  AI助手

选中态：
    ▓ 📊 仪表盘  ▓          ← 左侧 2px 紫色竖条 + 淡紫背景
                              文字变亮变粗，图标完全不透明

折叠态：
    📊                       ← 图标居中，hover 显示 tooltip
    🤖
```

**交互细节：**
- 正常：文字 0.88 透明度，图标 0.5 透明度
- hover：背景 `rgba(255,255,255,0.04)`，文字 1.0，图标 0.8
- 选中：背景 `rgba(79,79,223,0.10)`，文字 `--sidebar-accent-light`，图标 `--sidebar-accent`
- 选中条：左侧 2px 实线 `--sidebar-accent`
- 过渡：`transition: all 0.12s ease`（比当前 0.1s 略慢，更优雅）

### 5.4 底部固定区域

```
─────────────────────────
  📋 审计日志
  ☁️  数据导出
  ⚙️  系统设置
  ℹ️  关于
─────────────────────────
  ◀                      ← 折叠按钮
```
- 用 `flex-grow: 1` spacer 将底部项推到底
- 顶部 1px 分隔线
- 折叠按钮居中，36px 高

### 5.5 顶部栏布局

```
┌─────────────────────────────────────────────────────────────┐
│ ☰ ⚖️ AI财务系统 │ ▾ 默认账套    │ 2026 年 ▾  5 月 ▾  │ 🔍 👤 管理员 🌙 │
│ ← 左区(Logo+账套)  →  ← 中区(年月选择) →  ← 右区(搜索+用户) →  │
└─────────────────────────────────────────────────────────────┘
```

**细节：**
- 背景纯白 `#ffffff`，底部 1px 边框 `rgba(0,0,0,0.06)`
- Logo 图标 22px，标题 18px bold，字距 -0.2px
- 账套选择框：高度 32px，背景 `rgba(0,0,0,0.04)`，圆角 6px
- 年月选择框：高度 32px，宽度 70px/55px，居中对齐
- 搜索按钮：icon only，无边框
- Avatar：28px 圆形，紫色背景，首字母大写
- 用户名 13px + 角色 10px，紧凑排列
- 暗色模式按钮 + 退出按钮：icon only，最小尺寸

---

## 六、动效规范

| 场景 | 属性 | 时长 | 缓动 |
|------|------|------|------|
| 菜单项 hover | background, color, opacity | 0.12s | ease |
| 菜单项 选中切换 | background, border-left | 0.15s | ease-out |
| 侧边栏 展开/收缩 | width, min-width | 0.2s | cubic-bezier(0.4,0,0.2,1) |
| 分组 折叠/展开 | height | 0.18s | ease-out |
| Logo 文字 显隐 | opacity | 0.1s | ease |
| Tooltip 出现 | opacity, transform | 0.15s | ease-out |
| 通知红点 | pulse | 2s | infinite |
| 页面切换 | fadeIn + translateY(8px) | 0.25s | ease-out |

**原则：** 所有动效不超过 0.25s，不阻塞交互。动效只用于状态反馈，不做装饰性动画。

---

## 七、响应式

| 断点 | 行为 |
|------|------|
| > 1280px | 侧边栏展开（220px） |
| 1024 ~ 1280px | 侧边栏展开（220px） |
| 768 ~ 1024px | 侧边栏折叠（48px），hover 临时展开 |
| < 768px | 侧边栏隐藏，变为抽屉式，顶部汉堡菜单触发 |

**侧边栏 hover 展开（中等屏幕）：**
```css
.sidebar-nav.sidebar-collapsed:hover {
    width: 220px;
    box-shadow: 4px 0 24px rgba(0,0,0,0.3);
    z-index: 100;
}
```

---

## 八、暗色/亮色主题

侧边栏始终深色（fintech 风格不需要浅色侧边栏）。

顶部栏跟随主题：
- 亮色：白底 `#ffffff`，深色文字
- 暗色：深灰底 `#1a1d23`，浅色文字

---

## 九、实现注意事项

1. **CSS 变量统一放在 `:root`**，侧边栏和 header 各自的变量用 `--sidebar-*` 和 `--header-*` 前缀区分
2. **不要使用 `!important`**（除非覆盖 NiceGUI 内联样式），用 specificity
3. **图标大小统一**：侧边栏菜单图标 14px，顶部栏图标 20-22px
4. **中文排版优化**：`text-rendering: optimizeLegibility`，`-webkit-font-smoothing: antialiased`
5. **滚动条美化**：侧边栏滚动条 4px 宽，半透明，hover 时变亮
6. **无障碍**：所有可点击元素有 `:focus-visible` 样式，键盘可导航

---

## 十、需要修改的文件

| 文件 | 改动 |
|------|------|
| `app/static/style.css` | 重写 `.header-bar` 和 `.sidebar-nav` 相关全部 CSS |
| `app/components/ui_helpers.py` | 调整 `render_header()` 和 `render_sidebar()` 的 DOM 结构和 class 名称 |
| `app/static/script.js` | 如有需要，添加侧边栏 hover 展开的 JS 辅助 |

---

## 十一、视觉参考关键词（用于 AI 图片生成）

```
fintech SaaS sidebar navigation design,
dark navy background #0B1120,
purple accent #494fdf,
minimal uppercase group headers 10px,
13px menu items with 14px material icons,
2px purple left border for active state,
light header bar #ffffff with subtle shadow,
Inter font family,
professional financial dashboard UI,
clean geometric layout,
no decorative elements,
high information density
```
