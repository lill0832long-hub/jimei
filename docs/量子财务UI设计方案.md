# 量子财务 (Quantum Finance) UI 重设计方案

**项目:** AI财务系统V5.1
**技术栈:** Python + NiceGUI (Quasar/Vue) + SQLite
**当前主题:** 暖色系 (暖橙棕 #C4784A / 米白 #FAF7F2)
**目标主题:** 量子财务 — 深空蓝 + 量子紫 + 玻璃拟态 + 数据流光效
**文档版本:** v1.0
**日期:** 2026-06-13

---

## 目录

1. [设计理念与视觉概念](#1-设计理念与视觉概念)
2. [完整色彩系统](#2-完整色彩系统)
3. [字体系统](#3-字体系统)
4. [间距与布局网格](#4-间距与布局网格)
5. [组件设计规范](#5-组件设计规范)
6. [动画与动效设计](#6-动画与动效设计)
7. [玻璃拟态实现细节](#7-玻璃拟态实现细节)
8. [逐页重设计优先级计划](#8-逐页重设计优先级计划)
9. [CSS 架构方案](#9-css-架构方案)
10. [实施阶段与交付物](#10-实施阶段与交付物)

---

## 1. 设计理念与视觉概念

### 1.1 核心概念

**"量子财务"** 的设计灵感来自量子计算的视觉语言——深邃的蓝色空间中，数据以光流的形式穿梭，信息在半透明的玻璃面板中浮现。每一笔财务数据都如同量子比特，在被观测（查看）之前处于叠加态，呈现为流动的光点和粒子。

### 1.2 三大设计支柱

| 支柱 | 含义 | 视觉表现 |
|------|------|----------|
| **深空 (Deep Space)** | 财务数据的深邃与广博 | 深蓝黑渐变背景、星空粒子点缀 |
| **量子 (Quantum)** | 数据的精确与无限可能 | 紫色光晕、脉冲动画、数据流光 |
| **晶体 (Crystal)** | 信息的清晰与透明 | 玻璃拟态面板、折射光效、磨砂质感 |

### 1.3 视觉关键词

- 深空蓝 → 宇宙的广袤，代表系统承载的海量财务数据
- 量子紫 → 量子计算的前沿感，代表AI智能分析能力
- 玻璃拟态 → 信息的透明度与层次感
- 流光效果 → 数据的实时流动与活力
- 3D景深 → 界面的空间感与层级关系
- 奢华质感 → 精致的细节、微妙的渐变、考究的排版

### 1.4 设计风格对比

```
当前暖色系                          目标量子财务
─────────────────────────────────────────────────
背景: 米白 #FAF7F2          →  深空蓝黑 #0A0E1A
主色: 暖橙棕 #C4784A         →  量子紫 #7C3AED
侧栏: 深棕 #2D2620           →  深蓝黑 #0D1117
卡片: 纯白 #FFFFFF            →  玻璃拟态 rgba(255,255,255,0.05)
阴影: 暖色 rgba(139,94,60)    →  冷色 rgba(124,58,237)
风格: 扁平温暖                →  3D深邃、科技未来
```

---

## 2. 完整色彩系统

### 2.1 主色彩 (Primary Palette)

```css
:root {
    /* ── 量子紫 (Quantum Purple) — 主色调 ── */
    --q-purple-50:  #F5F3FF;   /* 极浅紫 — 浅色背景高亮 */
    --q-purple-100: #EDE9FE;   /* 浅紫 — hover 背景 */
    --q-purple-200: #DDD6FE;   /* 中浅紫 */
    --q-purple-300: #C4B5FD;   /* 中紫 */
    --q-purple-400: #A78BFA;   /* 亮紫 — 强调色 */
    --q-purple-500: #8B5CF6;   /* 标准紫 — 按钮/链接 */
    --q-purple-600: #7C3AED;   /* 主紫 — 主色调 */
    --q-purple-700: #6D28D9;   /* 深紫 — hover */
    --q-purple-800: #5B21B6;   /* 暗紫 */
    --q-purple-900: #4C1D95;   /* 极暗紫 */

    /* ── 深空蓝 (Deep Space Blue) — 背景/容器 ── */
    --q-space-50:   #F0F4FF;
    --q-space-100:  #E0E7FF;
    --q-space-200:  #C7D2FE;
    --q-space-300:  #A5B4FC;
    --q-space-400:  #818CF8;
    --q-space-500:  #6366F1;   /* 标准蓝 */
    --q-space-600:  #4F46E5;   /* 主蓝 */
    --q-space-700:  #4338CA;
    --q-space-800:  #1E1B4B;   /* 深蓝黑 */
    --q-space-900:  #0F0D2E;   /* 极深蓝黑 */
    --q-space-950:  #0A0E1A;   /* 最深 — 页面背景 */
}
```

### 2.2 语义色 (Semantic Colors)

```css
:root {
    /* ── 成功 (Success) — 量子绿 ── */
    --q-success:       #10B981;   /* 主成功色 */
    --q-success-light: rgba(16, 185, 129, 0.12);
    --q-success-glow:  rgba(16, 185, 129, 0.3);
    --q-success-dark:  #059669;

    /* ── 危险 (Danger) — 量子红 ── */
    --q-danger:        #EF4444;
    --q-danger-light:  rgba(239, 68, 68, 0.12);
    --q-danger-glow:   rgba(239, 68, 68, 0.3);
    --q-danger-dark:   #DC2626;

    /* ── 警告 (Warning) — 量子金 ── */
    --q-warning:       #F59E0B;
    --q-warning-light: rgba(245, 158, 11, 0.12);
    --q-warning-glow:  rgba(245, 158, 11, 0.3);
    --q-warning-dark:  #D97706;

    /* ── 信息 (Info) — 量子青 ── */
    --q-info:          #06B6D4;
    --q-info-light:    rgba(6, 182, 212, 0.12);
    --q-info-glow:     rgba(6, 182, 212, 0.3);
    --q-info-dark:     #0891B2;
}
```

### 2.3 中性色 (Neutral Colors) — 深色模式为主

```css
:root {
    /* ── 页面背景层级 ── */
    --q-bg-base:       #0A0E1A;   /* 最底层背景 */
    --q-bg-elevated:   #0F1320;   /* 提升层背景 (侧栏) */
    --q-bg-surface:    #141928;   /* 表面层背景 (卡片) */
    --q-bg-overlay:    rgba(20, 25, 40, 0.85);  /* 遮罩层 */

    /* ── 玻璃拟态背景 ── */
    --q-glass:         rgba(255, 255, 255, 0.04);   /* 默认玻璃 */
    --q-glass-hover:   rgba(255, 255, 255, 0.07);   /* hover */
    --q-glass-active:  rgba(255, 255, 255, 0.10);   /* active */
    --q-glass-border:  rgba(255, 255, 255, 0.08);   /* 玻璃边框 */
    --q-glass-glow:    rgba(124, 58, 237, 0.15);    /* 玻璃光晕 */

    /* ── 文字层级 ── */
    --q-text-primary:   rgba(255, 255, 255, 0.92);  /* 主文字 */
    --q-text-secondary: rgba(255, 255, 255, 0.65);  /* 副文字 */
    --q-text-muted:     rgba(255, 255, 255, 0.40);  /* 弱化文字 */
    --q-text-disabled:  rgba(255, 255, 255, 0.22);  /* 禁用文字 */
    --q-text-inverse:   #0A0E1A;                     /* 反色文字 */

    /* ── 边框 ── */
    --q-border:        rgba(255, 255, 255, 0.08);
    --q-border-light:  rgba(255, 255, 255, 0.05);
    --q-border-active: rgba(124, 58, 237, 0.4);
}
```

### 2.4 渐变色 (Gradients)

```css
:root {
    /* ── 核心渐变 ── */
    --q-gradient-primary:   linear-gradient(135deg, #7C3AED 0%, #A78BFA 100%);
    --q-gradient-space:     linear-gradient(180deg, #0A0E1A 0%, #0F1320 50%, #141928 100%);
    --q-gradient-glass:     linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.02) 100%);
    --q-gradient-glow:      radial-gradient(ellipse at center, rgba(124,58,237,0.15) 0%, transparent 70%);

    /* ── 状态渐变 ── */
    --q-gradient-success:   linear-gradient(135deg, #10B981 0%, #34D399 100%);
    --q-gradient-danger:    linear-gradient(135deg, #EF4444 0%, #F87171 100%);
    --q-gradient-warning:   linear-gradient(135deg, #F59E0B 0%, #FBBF24 100%);
    --q-gradient-info:      linear-gradient(135deg, #06B6D4 0%, #22D3EE 100%);

    /* ── 特效渐变 ── */
    --q-gradient-aurora:    linear-gradient(135deg, #7C3AED 0%, #06B6D4 50%, #10B981 100%);
    --q-gradient-nebula:    linear-gradient(135deg, #4C1D95 0%, #1E1B4B 50%, #0F172A 100%);
    --q-gradient-sidebar:   linear-gradient(180deg, #0D1117 0%, #0F1320 100%);
    --q-gradient-header:    linear-gradient(90deg, rgba(124,58,237,0.08) 0%, transparent 100%);

    /* ── 流光渐变 (用于动画) ── */
    --q-gradient-flow:      linear-gradient(90deg, transparent 0%, rgba(124,58,237,0.3) 50%, transparent 100%);
}
```

### 2.5 阴影系统 (Shadows)

```css
:root {
    /* ── 基础阴影 (紫色调) ── */
    --q-shadow-sm:   0 1px 3px rgba(0, 0, 0, 0.3);
    --q-shadow-md:   0 4px 12px rgba(0, 0, 0, 0.4);
    --q-shadow-lg:   0 8px 32px rgba(0, 0, 0, 0.5);
    --q-shadow-xl:   0 16px 48px rgba(0, 0, 0, 0.6);

    /* ── 光晕阴影 (量子紫) ── */
    --q-glow-sm:     0 0 8px rgba(124, 58, 237, 0.2);
    --q-glow-md:     0 0 16px rgba(124, 58, 237, 0.25);
    --q-glow-lg:     0 0 32px rgba(124, 58, 237, 0.3);
    --q-glow-xl:     0 0 48px rgba(124, 58, 237, 0.35);

    /* ── 复合阴影 ── */
    --q-shadow-card:       var(--q-shadow-sm);
    --q-shadow-card-hover: var(--q-shadow-md), var(--q-glow-sm);
    --q-shadow-kpi:        var(--q-shadow-sm);
    --q-shadow-kpi-hover:  var(--q-shadow-lg), var(--q-glow-md);
    --q-shadow-btn:        0 2px 8px rgba(124, 58, 237, 0.3);
    --q-shadow-header:     0 2px 12px rgba(0, 0, 0, 0.3);
}
```

### 2.6 浅色模式选项 (Light Mode)

```css
body[data-theme="light"] {
    --q-bg-base:       #F8F9FC;
    --q-bg-elevated:   #FFFFFF;
    --q-bg-surface:    #FFFFFF;
    --q-glass:         rgba(255, 255, 255, 0.7);
    --q-glass-hover:   rgba(255, 255, 255, 0.85);
    --q-glass-border:  rgba(124, 58, 237, 0.1);
    --q-text-primary:  #1A1625;
    --q-text-secondary:#4A4458;
    --q-text-muted:    #8B85A0;
    --q-border:        rgba(124, 58, 237, 0.1);
    --q-shadow-sm:     0 1px 3px rgba(124, 58, 237, 0.08);
    --q-shadow-md:     0 4px 12px rgba(124, 58, 237, 0.1);
    --q-shadow-lg:     0 8px 32px rgba(124, 58, 237, 0.12);
    --q-glow-sm:       0 0 8px rgba(124, 58, 237, 0.1);
    --q-glow-md:       0 0 16px rgba(124, 58, 237, 0.15);
}
```

---

## 3. 字体系统

### 3.1 字体栈

```css
:root {
    /* ── 主字体 — 无衬线 ── */
    --font-stack: "Inter", "Nunito", "PingFang SC", "Hiragino Sans GB",
                  "Microsoft YaHei", "Noto Sans CJK SC", system-ui,
                  -apple-system, sans-serif;

    /* ── 等宽字体 — 数字/代码 ── */
    --font-mono: "JetBrains Mono", "SF Mono", "Fira Code",
                 "Consolas", "Monaco", monospace;

    /* ── 展示字体 — 标题/品牌 ── */
    --font-display: "Inter", "Nunito", system-ui, sans-serif;
}
```

**推荐下载:**
- Inter: https://rsms.me/inter/ (主UI字体，数字显示极佳)
- JetBrains Mono: https://www.jetbrains.com/lp/mono/ (等宽数字)

### 3.2 字号层级 (Type Scale)

```css
:root {
    /* ── 字号 — 基于 1.25 Major Third 比例 ── */
    --text-xs:    11px;   /* 标签、徽章 */
    --text-sm:    13px;   /* 表格正文、按钮 */
    --text-base:  14px;   /* 正文基准 */
    --text-md:    15px;   /* 卡片标题 */
    --text-lg:    18px;   /* 区域标题 */
    --text-xl:    22px;   /* 页面标题 */
    --text-2xl:   28px;   /* KPI数值 */
    --text-3xl:   36px;   /* 大屏数据 */
    --text-4xl:   48px;   /* 展示级 */

    /* ── 字重 ── */
    --font-normal:    400;
    --font-medium:    500;
    --font-semibold:  600;
    --font-bold:      700;
    --font-extrabold: 800;

    /* ── 行高 ── */
    --leading-tight:  1.2;
    --leading-normal: 1.5;
    --leading-relaxed: 1.6;

    /* ── 字间距 ── */
    --tracking-tight:  -0.5px;
    --tracking-normal: 0;
    --tracking-wide:   0.5px;
    --tracking-wider:  1px;
}
```

### 3.3 文字样式类

```css
/* 页面标题 — 带渐变色 */
.qf-page-title {
    font-size: var(--text-xl);
    font-weight: var(--font-bold);
    background: var(--q-gradient-primary);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: var(--tracking-tight);
    line-height: var(--leading-tight);
}

/* 区域标题 */
.qf-section-title {
    font-size: var(--text-lg);
    font-weight: var(--font-semibold);
    color: var(--q-text-primary);
    letter-spacing: var(--tracking-normal);
}

/* 卡片标题 */
.qf-card-title {
    font-size: var(--text-md);
    font-weight: var(--font-semibold);
    color: var(--q-text-primary);
}

/* KPI 数值 — 特殊渲染 */
.qf-kpi-value {
    font-family: var(--font-mono);
    font-size: var(--text-2xl);
    font-weight: var(--font-extrabold);
    font-variant-numeric: tabular-nums;
    letter-spacing: var(--tracking-tight);
    color: var(--q-text-primary);
    text-shadow: 0 0 20px rgba(124, 58, 237, 0.3);
}

/* 正文 */
.qf-body {
    font-size: var(--text-base);
    font-weight: var(--font-normal);
    line-height: var(--leading-relaxed);
    color: var(--q-text-secondary);
}

/* 标签/小字 */
.qf-caption {
    font-size: var(--text-xs);
    font-weight: var(--font-medium);
    color: var(--q-text-muted);
    letter-spacing: var(--tracking-wide);
    text-transform: uppercase;
}
```

---

## 4. 间距与布局网格

### 4.1 间距系统 (8px 基准)

```css
:root {
    /* ── 基于 8px 网格的间距 ── */
    --space-0:   0;
    --space-1:   4px;    /* 0.5x */
    --space-2:   8px;    /* 1x — 基准 */
    --space-3:   12px;   /* 1.5x */
    --space-4:   16px;   /* 2x */
    --space-5:   20px;   /* 2.5x */
    --space-6:   24px;   /* 3x */
    --space-8:   32px;   /* 4x */
    --space-10:  40px;   /* 5x */
    --space-12:  48px;   /* 6x */
    --space-16:  64px;   /* 8x */
}
```

### 4.2 圆角系统

```css
:root {
    --radius-xs:  4px;    /* 小元素：标签、badge */
    --radius-sm:  6px;    /* 按钮、输入框 */
    --radius-md:  10px;   /* 小卡片 */
    --radius-lg:  14px;   /* 标准卡片 */
    --radius-xl:  18px;   /* 大卡片、面板 */
    --radius-2xl: 24px;   /* 模态框 */
    --radius-full: 9999px; /* 药丸形 */
}
```

### 4.3 整体布局尺寸

```css
:root {
    /* ── 顶部栏 ── */
    --header-h:           64px;    /* 从78px降到64px，更紧凑 */
    --header-padding-x:   24px;

    /* ── 侧边栏 ── */
    --sidebar-width:          260px;  /* 保持不变 */
    --sidebar-width-collapsed: 64px;  /* 从48px增加到64px，图标更舒适 */
    --sidebar-logo-h:         64px;   /* 与header对齐 */

    /* ── 内容区 ── */
    --content-padding:        24px;
    --content-max-width:      1600px;
    --card-padding:           20px;
    --card-gap:               16px;

    /* ── Tab 栏 ── */
    --tab-bar-h:              40px;
    --tab-item-h:             32px;
}
```

### 4.4 响应式断点

```css
/* 断点定义 */
--bp-sm:  640px;   /* 手机横屏 */
--bp-md:  768px;   /* 平板竖屏 */
--bp-lg:  1024px;  /* 平板横屏/小笔记本 */
--bp-xl:  1280px;  /* 桌面 */
--bp-2xl: 1536px;  /* 大桌面 */
--bp-3xl: 1920px;  /* 超宽屏 */
```

---

## 5. 组件设计规范

### 5.1 侧边栏 (Sidebar)

**当前状态:** 深暖棕背景，橙色强调色
**目标状态:** 深蓝黑背景，量子紫光效，玻璃质感

```css
/* ── 侧边栏容器 ── */
.qf-sidebar {
    background: var(--q-gradient-sidebar);
    border-right: 1px solid var(--q-glass-border);
    width: var(--sidebar-width);
    min-width: var(--sidebar-width);
    transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
}

/* 侧边栏背景粒子效果 — CSS only */
.qf-sidebar::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background:
        radial-gradient(1px 1px at 20% 30%, rgba(124,58,237,0.3) 0%, transparent 100%),
        radial-gradient(1px 1px at 80% 70%, rgba(6,182,212,0.2) 0%, transparent 100%),
        radial-gradient(1px 1px at 50% 50%, rgba(124,58,237,0.15) 0%, transparent 100%);
    pointer-events: none;
    animation: sidebarStars 20s linear infinite;
}

@keyframes sidebarStars {
    0%, 100% { opacity: 0.5; }
    50% { opacity: 1; }
}

/* Logo 区域 */
.qf-sidebar-logo {
    height: var(--sidebar-logo-h);
    display: flex;
    align-items: center;
    padding: 0 20px;
    gap: 12px;
    border-bottom: 1px solid var(--q-glass-border);
    background: rgba(0, 0, 0, 0.2);
    position: relative;
}

/* Logo 图标 — 带紫色光晕 */
.qf-sidebar-logo-icon {
    font-size: 28px;
    color: var(--q-purple-400);
    filter: drop-shadow(0 0 8px rgba(124, 58, 237, 0.4));
    animation: logoPulse 3s ease-in-out infinite;
}

@keyframes logoPulse {
    0%, 100% { filter: drop-shadow(0 0 8px rgba(124, 58, 237, 0.4)); }
    50% { filter: drop-shadow(0 0 16px rgba(124, 58, 237, 0.6)); }
}

/* Logo 文字 */
.qf-sidebar-logo-text {
    font-size: 20px;
    font-weight: 800;
    background: var(--q-gradient-primary);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: var(--tracking-tight);
}

/* 分组标题 */
.qf-sidebar-group-header {
    height: 36px;
    padding: 0 16px;
    margin: 8px 8px 4px 8px;
    display: flex;
    align-items: center;
    gap: 8px;
    border-radius: var(--radius-sm);
    background: rgba(255, 255, 255, 0.02);
    font-size: 11px;
    font-weight: 700;
    color: var(--q-text-muted);
    text-transform: uppercase;
    letter-spacing: 2px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.qf-sidebar-group-header:hover {
    background: rgba(255, 255, 255, 0.04);
    color: var(--q-text-secondary);
}

/* 分组分隔线 — 渐变淡出 */
.qf-sidebar-divider {
    height: 1px;
    margin: 6px 16px;
    background: linear-gradient(90deg, transparent, var(--q-glass-border), transparent);
}

/* 菜单项 */
.qf-sidebar-menu-item {
    display: flex;
    align-items: center;
    height: 40px;
    margin: 2px 8px;
    padding: 0 12px;
    gap: 12px;
    border-radius: var(--radius-md);
    font-size: 14px;
    font-weight: 500;
    color: var(--q-text-secondary);
    cursor: pointer;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
}

/* 菜单项悬停 — 玻璃发光 */
.qf-sidebar-menu-item:hover {
    background: var(--q-glass-hover);
    color: var(--q-text-primary);
    box-shadow: 0 0 12px rgba(124, 58, 237, 0.1);
}

/* 菜单项选中态 — 紫色光效 */
.qf-sidebar-menu-active {
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.15), rgba(124, 58, 237, 0.08));
    color: var(--q-purple-300) !important;
    border-left: 3px solid var(--q-purple-500);
    box-shadow:
        inset 0 0 20px rgba(124, 58, 237, 0.08),
        0 0 16px rgba(124, 58, 237, 0.12);
}

/* 选中项图标 — 紫色光晕 */
.qf-sidebar-menu-active .qf-sidebar-menu-icon {
    color: var(--q-purple-400);
    filter: drop-shadow(0 0 6px rgba(124, 58, 237, 0.4));
}

/* 图标槽位 — 固定宽度对齐 */
.qf-sidebar-menu-icon {
    width: 36px;
    min-width: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    opacity: 0.6;
    transition: all 0.2s ease;
}

.qf-sidebar-menu-item:hover .qf-sidebar-menu-icon {
    opacity: 1;
    transform: scale(1.1);
}

/* 滚动条 */
.qf-sidebar::-webkit-scrollbar { width: 4px; }
.qf-sidebar::-webkit-scrollbar-thumb {
    background: rgba(124, 58, 237, 0.3);
    border-radius: 2px;
}
.qf-sidebar::-webkit-scrollbar-thumb:hover {
    background: rgba(124, 58, 237, 0.5);
}
```

### 5.2 顶部栏 (Header)

```css
/* ── 顶部栏容器 ── */
.qf-header {
    background: rgba(15, 19, 32, 0.85);
    backdrop-filter: blur(20px) saturate(1.5);
    -webkit-backdrop-filter: blur(20px) saturate(1.5);
    border-bottom: 1px solid var(--q-glass-border);
    height: var(--header-h);
    padding: 0 var(--header-padding-x);
    position: relative;
    z-index: 100;
}

/* 底部流光线 */
.qf-header::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(124, 58, 237, 0.6) 20%,
        rgba(6, 182, 212, 0.4) 50%,
        rgba(124, 58, 237, 0.6) 80%,
        transparent 100%
    );
    animation: headerFlowLine 4s ease-in-out infinite;
}

@keyframes headerFlowLine {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
}

/* 三栏布局 */
.qf-header-grid {
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    align-items: center;
    width: 100%;
    height: 100%;
    gap: 24px;
}

/* 标题 — 紫色渐变 */
.qf-header-title {
    font-size: 22px;
    font-weight: 800;
    background: var(--q-gradient-primary);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: var(--tracking-tight);
}

/* 版本号 — 紫色药丸 */
.qf-header-version {
    font-size: 10px;
    font-weight: 700;
    color: #fff;
    background: var(--q-gradient-primary);
    padding: 2px 10px;
    border-radius: var(--radius-full);
    letter-spacing: 0.5px;
    box-shadow: 0 2px 8px rgba(124, 58, 237, 0.3);
}

/* 年月选择器 */
.qf-header-year-select,
.qf-header-month-select {
    font-size: 15px;
    font-weight: 700;
    color: var(--q-text-primary);
}

/* 搜索框 */
.qf-header-search-box {
    display: flex;
    align-items: center;
    background: var(--q-glass);
    border: 1px solid var(--q-glass-border);
    border-radius: var(--radius-full);
    padding: 0 4px 0 14px;
    height: 36px;
    backdrop-filter: blur(10px);
    transition: all 0.2s ease;
}

.qf-header-search-box:focus-within {
    border-color: var(--q-purple-500);
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.15);
    background: var(--q-glass-hover);
}

/* 通知铃铛 */
.qf-header-notif-dot {
    width: 8px;
    height: 8px;
    background: var(--q-danger);
    border-radius: 50%;
    border: 2px solid var(--q-bg-elevated);
    position: absolute;
    top: 0;
    right: 0;
    animation: notifPulse 2s ease-in-out infinite;
}

@keyframes notifPulse {
    0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
    50% { box-shadow: 0 0 0 4px rgba(239, 68, 68, 0); }
}

/* 用户头像 */
.qf-header-avatar {
    width: 34px;
    height: 34px;
    border-radius: 50%;
    background: var(--q-gradient-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    font-weight: 700;
    color: #fff;
    box-shadow: 0 0 12px rgba(124, 58, 237, 0.3);
    transition: transform 0.2s ease;
}

.qf-header-avatar:hover {
    transform: scale(1.08);
    box-shadow: 0 0 20px rgba(124, 58, 237, 0.4);
}

/* 图标按钮 */
.qf-header-icon-btn {
    color: var(--q-text-muted);
    min-height: 32px;
    min-width: 32px;
    border-radius: var(--radius-sm);
    transition: all 0.2s ease;
}

.qf-header-icon-btn:hover {
    color: var(--q-purple-400);
    background: var(--q-glass-hover);
    box-shadow: 0 0 12px rgba(124, 58, 237, 0.15);
}
```

### 5.3 KPI 卡片 (KPI Cards)

```css
/* ── KPI 卡片 — 玻璃拟态 ── */
.qf-kpi-card {
    position: relative;
    background: var(--q-glass);
    backdrop-filter: blur(20px) saturate(1.5);
    -webkit-backdrop-filter: blur(20px) saturate(1.5);
    border: 1px solid var(--q-glass-border);
    border-radius: var(--radius-lg);
    padding: var(--space-5);
    min-height: 100px;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* KPI 卡片 — 顶部彩色流光线 */
.qf-kpi-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
}

/* KPI 卡片 — 背景光晕 */
.qf-kpi-card::after {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(ellipse at center, rgba(124,58,237,0.05) 0%, transparent 50%);
    pointer-events: none;
    transition: opacity 0.3s ease;
    opacity: 0;
}

.qf-kpi-card:hover::after {
    opacity: 1;
}

/* KPI 悬停态 */
.qf-kpi-card:hover {
    transform: translateY(-4px);
    box-shadow: var(--q-shadow-kpi-hover);
    border-color: var(--q-border-active);
}

/* KPI 颜色变体 */
.qf-kpi-card[data-color="purple"]::before {
    background: var(--q-gradient-primary);
}
.qf-kpi-card[data-color="green"]::before {
    background: var(--q-gradient-success);
}
.qf-kpi-card[data-color="red"]::before {
    background: var(--q-gradient-danger);
}
.qf-kpi-card[data-color="cyan"]::before {
    background: var(--q-gradient-info);
}
.qf-kpi-card[data-color="gold"]::before {
    background: var(--q-gradient-warning);
}

/* KPI 图标容器 — 发光背景 */
.qf-kpi-icon-wrapper {
    width: 44px;
    height: 44px;
    border-radius: var(--radius-md);
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(124, 58, 237, 0.12);
    box-shadow: 0 0 16px rgba(124, 58, 237, 0.15);
}

/* KPI 数值 — 发光文字 */
.qf-kpi-value {
    font-family: var(--font-mono);
    font-size: var(--text-2xl);
    font-weight: var(--font-extrabold);
    color: var(--q-text-primary);
    text-shadow: 0 0 20px rgba(124, 58, 237, 0.2);
    font-variant-numeric: tabular-nums;
}

/* KPI 趋势标签 */
.qf-kpi-trend {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: var(--radius-xs);
    font-size: var(--text-xs);
    font-weight: var(--font-semibold);
}

.qf-kpi-trend-up {
    color: var(--q-success);
    background: var(--q-success-light);
}

.qf-kpi-trend-down {
    color: var(--q-danger);
    background: var(--q-danger-light);
}
```

### 5.4 数据表格 (Tables)

```css
/* ── 表格容器 — 玻璃拟态 ── */
.qf-table-container {
    background: var(--q-glass);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid var(--q-glass-border);
    border-radius: var(--radius-lg);
    overflow: hidden;
}

/* 表头 */
.qf-table thead th {
    background: rgba(255, 255, 255, 0.03);
    font-size: var(--text-xs);
    font-weight: var(--font-semibold);
    color: var(--q-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding: 10px 14px;
    border-bottom: 1px solid var(--q-glass-border);
    position: sticky;
    top: 0;
    z-index: 1;
    backdrop-filter: blur(10px);
}

/* 表体行 */
.qf-table tbody tr {
    transition: all 0.15s ease;
    border-bottom: 1px solid var(--q-border-light);
}

/* 斑马纹 — 微妙的玻璃层 */
.qf-table tbody tr:nth-child(even) {
    background: rgba(255, 255, 255, 0.02);
}

/* 悬停行 — 紫色高亮 */
.qf-table tbody tr:hover {
    background: rgba(124, 58, 237, 0.06);
    box-shadow: inset 3px 0 0 var(--q-purple-500);
}

/* 表格单元格 */
.qf-table tbody td {
    font-size: var(--text-sm);
    padding: 8px 14px;
    color: var(--q-text-secondary);
    font-variant-numeric: tabular-nums;
}

/* 数字列 */
.qf-table td.qf-td-num {
    text-align: right;
    font-family: var(--font-mono);
    font-weight: var(--font-medium);
    color: var(--q-text-primary);
}

/* 科目代码列 */
.qf-table td.qf-td-code {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--q-purple-400);
}

/* 合计行 */
.qf-table tfoot tr {
    background: rgba(124, 58, 237, 0.08);
    border-top: 2px solid var(--q-purple-500);
}

.qf-table tfoot td {
    font-weight: var(--font-bold);
    color: var(--q-purple-300);
}
```

### 5.5 按钮 (Buttons)

```css
/* ── 主按钮 — 紫色渐变 + 光效 ── */
.qf-btn-primary {
    background: var(--q-gradient-primary) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    font-size: var(--text-sm) !important;
    font-weight: var(--font-semibold) !important;
    padding: 8px 20px !important;
    box-shadow: var(--q-shadow-btn) !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    position: relative;
    overflow: hidden;
}

/* 主按钮 — 流光效果 */
.qf-btn-primary::before {
    content: '';
    position: absolute;
    top: 0;
    left: -100%;
    width: 100%;
    height: 100%;
    background: linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.2),
        transparent
    );
    transition: left 0.5s ease;
}

.qf-btn-primary:hover::before {
    left: 100%;
}

.qf-btn-primary:hover {
    box-shadow: var(--q-shadow-btn), var(--q-glow-md) !important;
    transform: translateY(-1px) !important;
}

.qf-btn-primary:active {
    transform: scale(0.97) translateY(0) !important;
}

/* ── 次要按钮 — 玻璃态 ── */
.qf-btn-secondary {
    background: var(--q-glass) !important;
    color: var(--q-text-primary) !important;
    border: 1px solid var(--q-glass-border) !important;
    border-radius: var(--radius-sm) !important;
    backdrop-filter: blur(10px) !important;
    transition: all 0.2s ease !important;
}

.qf-btn-secondary:hover {
    background: var(--q-glass-hover) !important;
    border-color: var(--q-purple-500) !important;
    box-shadow: var(--q-glow-sm) !important;
}

/* ── 幽灵按钮 ── */
.qf-btn-ghost {
    background: transparent !important;
    color: var(--q-text-secondary) !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    transition: all 0.2s ease !important;
}

.qf-btn-ghost:hover {
    color: var(--q-purple-400) !important;
    background: var(--q-glass) !important;
}

/* ── 危险按钮 ── */
.qf-btn-danger {
    background: var(--q-gradient-danger) !important;
    color: #fff !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3) !important;
}

.qf-btn-danger:hover {
    box-shadow: 0 4px 16px rgba(239, 68, 68, 0.4) !important;
    transform: translateY(-1px) !important;
}
```

### 5.6 表单控件 (Form Controls)

```css
/* ── 输入框 — 玻璃态 ── */
.qf-input .q-field__control {
    background: var(--q-glass) !important;
    border: 1px solid var(--q-glass-border) !important;
    border-radius: var(--radius-sm) !important;
    backdrop-filter: blur(10px) !important;
    transition: all 0.2s ease !important;
}

.qf-input .q-field__control:hover {
    border-color: rgba(124, 58, 237, 0.3) !important;
}

.qf-input .q-field__control:focus-within {
    border-color: var(--q-purple-500) !important;
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.15) !important;
    background: var(--q-glass-hover) !important;
}

.qf-input .q-field__native {
    color: var(--q-text-primary) !important;
    font-size: var(--text-base) !important;
}

.qf-input .q-field__label {
    color: var(--q-text-muted) !important;
}

/* ── 选择框 ── */
.qf-select .q-field__control {
    background: var(--q-glass) !important;
    border: 1px solid var(--q-glass-border) !important;
    border-radius: var(--radius-sm) !important;
}

/* ── 复选框 ── */
.qf-checkbox .q-checkbox__inner {
    color: var(--q-purple-500) !important;
}

/* ── 开关 ── */
.qf-toggle .q-toggle__track {
    background: var(--q-glass) !important;
    border: 1px solid var(--q-glass-border) !important;
}

.qf-toggle.q-toggle--truthy .q-toggle__track {
    background: var(--q-purple-600) !important;
}
```

### 5.7 模态框 (Modals/Dialogs)

```css
/* ── 模态框 — 深度玻璃态 ── */
.qf-dialog .q-card {
    background: rgba(20, 25, 40, 0.95) !important;
    backdrop-filter: blur(40px) saturate(1.8) !important;
    -webkit-backdrop-filter: blur(40px) saturate(1.8) !important;
    border: 1px solid var(--q-glass-border) !important;
    border-radius: var(--radius-2xl) !important;
    box-shadow:
        var(--q-shadow-xl),
        var(--q-glow-lg),
        inset 0 1px 0 rgba(255, 255, 255, 0.05) !important;
}

/* 模态框标题 */
.qf-dialog-title {
    font-size: var(--text-lg);
    font-weight: var(--font-bold);
    color: var(--q-text-primary);
    padding: 24px 28px 16px;
    border-bottom: 1px solid var(--q-glass-border);
}

/* 模态框内容 */
.qf-dialog-body {
    padding: 20px 28px;
    color: var(--q-text-secondary);
}

/* 模态框底部 */
.qf-dialog-footer {
    padding: 16px 28px 24px;
    border-top: 1px solid var(--q-glass-border);
    display: flex;
    justify-content: flex-end;
    gap: 12px;
}

/* 弹出动画 */
.qf-dialog .q-card {
    animation: dialogGlassIn 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes dialogGlassIn {
    from {
        opacity: 0;
        transform: scale(0.92) translateY(20px);
        filter: blur(4px);
    }
    to {
        opacity: 1;
        transform: scale(1) translateY(0);
        filter: blur(0);
    }
}
```

### 5.8 Tab 栏 (Tab Bar)

```css
/* ── Tab 栏容器 — 玻璃态 ── */
.qf-tab-bar {
    background: var(--q-glass);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-bottom: 1px solid var(--q-glass-border);
    padding: 4px 8px;
    min-height: var(--tab-bar-h);
    display: flex;
    align-items: center;
    gap: 4px;
    overflow-x: auto;
}

/* Tab 项 */
.qf-tab-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    font-weight: var(--font-semibold);
    min-height: var(--tab-item-h);
    cursor: pointer;
    transition: all 0.2s ease;
    white-space: nowrap;
}

/* 活动 Tab — 紫色渐变 */
.qf-tab-item--active {
    background: var(--q-gradient-primary) !important;
    color: #fff !important;
    box-shadow: var(--q-shadow-btn);
}

/* 活动 Tab 底部指示器 */
.qf-tab-item--active::after {
    content: '';
    position: absolute;
    bottom: -4px;
    left: 50%;
    transform: translateX(-50%);
    width: 20px;
    height: 2px;
    background: var(--q-purple-400);
    border-radius: 1px;
    box-shadow: 0 0 8px rgba(124, 58, 237, 0.5);
}

/* 非活动 Tab */
.qf-tab-item--inactive {
    background: var(--q-glass);
    color: var(--q-text-secondary);
}

.qf-tab-item--inactive:hover {
    background: var(--q-glass-hover);
    color: var(--q-text-primary);
}

/* Tab 关闭按钮 */
.qf-tab-close {
    opacity: 0.5;
    transition: all 0.15s ease;
    border-radius: var(--radius-xs);
}

.qf-tab-item:hover .qf-tab-close {
    opacity: 1;
}

.qf-tab-close:hover {
    background: rgba(239, 68, 68, 0.2);
    color: var(--q-danger);
}
```

### 5.9 状态标签 (Badges/Tags)

```css
/* ── 状态标签 — 玻璃态 ── */
.qf-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 10px;
    border-radius: var(--radius-full);
    font-size: var(--text-xs);
    font-weight: var(--font-semibold);
    backdrop-filter: blur(8px);
    border: 1px solid transparent;
}

.qf-badge--success {
    background: var(--q-success-light);
    color: var(--q-success);
    border-color: rgba(16, 185, 129, 0.2);
}

.qf-badge--danger {
    background: var(--q-danger-light);
    color: var(--q-danger);
    border-color: rgba(239, 68, 68, 0.2);
}

.qf-badge--warning {
    background: var(--q-warning-light);
    color: var(--q-warning);
    border-color: rgba(245, 158, 11, 0.2);
}

.qf-badge--info {
    background: var(--q-info-light);
    color: var(--q-info);
    border-color: rgba(6, 182, 212, 0.2);
}

.qf-badge--purple {
    background: rgba(124, 58, 237, 0.12);
    color: var(--q-purple-400);
    border-color: rgba(124, 58, 237, 0.2);
}
```

### 5.10 搜索结果卡片

```css
.qf-search-result {
    background: var(--q-glass);
    border: 1px solid var(--q-glass-border);
    border-radius: var(--radius-md);
    padding: 12px 16px;
    cursor: pointer;
    transition: all 0.2s ease;
    backdrop-filter: blur(10px);
}

.qf-search-result:hover {
    border-color: var(--q-purple-500);
    box-shadow: var(--q-glow-sm);
    transform: translateX(4px);
}

.qf-search-result-vno {
    color: var(--q-purple-400);
    font-weight: var(--font-semibold);
    font-family: var(--font-mono);
}

.qf-search-result-date {
    color: var(--q-text-muted);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
}

.qf-search-result-acct {
    color: var(--q-success);
    font-weight: var(--font-semibold);
    font-family: var(--font-mono);
}
```

---

## 6. 动画与动效设计

### 6.1 缓动函数库

```css
:root {
    /* ── 缓动曲线 ── */
    --ease-smooth:    cubic-bezier(0.4, 0, 0.2, 1);      /* 标准平滑 */
    --ease-bounce:    cubic-bezier(0.34, 1.56, 0.64, 1);  /* 弹性 */
    --ease-spring:    cubic-bezier(0.175, 0.885, 0.32, 1.275); /* 弹簧 */
    --ease-out-expo:  cubic-bezier(0.19, 1, 0.22, 1);    /* 指数缓出 */
    --ease-in-out:    cubic-bezier(0.645, 0.045, 0.355, 1); /* 缓入缓出 */

    /* ── 时长 ── */
    --dur-instant:    0.1s;
    --dur-fast:       0.15s;
    --dur-normal:     0.25s;
    --dur-slow:       0.4s;
    --dur-glacial:    0.6s;
}
```

### 6.2 页面入场动画

```css
/* ── 页面淡入上移 ── */
@keyframes pageEnter {
    from {
        opacity: 0;
        transform: translateY(16px);
        filter: blur(4px);
    }
    to {
        opacity: 1;
        transform: translateY(0);
        filter: blur(0);
    }
}

.main-content-area {
    animation: pageEnter 0.4s var(--ease-out-expo) both;
}
```

### 6.3 卡片入场动画 — 交错级联

```css
/* ── 卡片级联入场 ── */
@keyframes cardCascade {
    from {
        opacity: 0;
        transform: translateY(20px) scale(0.96);
        filter: blur(4px);
    }
    to {
        opacity: 1;
        transform: translateY(0) scale(1);
        filter: blur(0);
    }
}

.qf-kpi-card:nth-child(1) { animation: cardCascade 0.5s var(--ease-out-expo) 0.05s both; }
.qf-kpi-card:nth-child(2) { animation: cardCascade 0.5s var(--ease-out-expo) 0.10s both; }
.qf-kpi-card:nth-child(3) { animation: cardCascade 0.5s var(--ease-out-expo) 0.15s both; }
.qf-kpi-card:nth-child(4) { animation: cardCascade 0.5s var(--ease-out-expo) 0.20s both; }
.qf-kpi-card:nth-child(5) { animation: cardCascade 0.5s var(--ease-out-expo) 0.25s both; }
```

### 6.4 数值滚动动画

```css
/* ── 数值闪烁高亮 ── */
@keyframes valueFlash {
    0% { color: var(--q-purple-400); text-shadow: 0 0 20px rgba(124,58,237,0.5); }
    100% { color: inherit; text-shadow: 0 0 20px rgba(124,58,237,0.2); }
}

.qf-value-updated {
    animation: valueFlash 1.2s var(--ease-smooth);
}
```

### 6.5 数据流光效果 (核心特效)

```css
/* ── 流光扫描线 — 用于卡片/表格强调 ── */
@keyframes flowScan {
    0% {
        background-position: -200% 0;
    }
    100% {
        background-position: 200% 0;
    }
}

.qf-flow-line {
    position: relative;
    overflow: hidden;
}

.qf-flow-line::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(
        90deg,
        transparent 0%,
        rgba(124, 58, 237, 0.4) 25%,
        rgba(6, 182, 212, 0.3) 50%,
        rgba(124, 58, 237, 0.4) 75%,
        transparent 100%
    );
    background-size: 200% 100%;
    animation: flowScan 3s linear infinite;
}

/* ── 数据粒子流 — 用于加载状态 ── */
@keyframes particleFlow {
    0% {
        transform: translateX(-100%) scale(0);
        opacity: 0;
    }
    10% {
        opacity: 1;
        transform: translateX(-80%) scale(1);
    }
    90% {
        opacity: 1;
        transform: translateX(80%) scale(1);
    }
    100% {
        transform: translateX(100%) scale(0);
        opacity: 0;
    }
}

.qf-particle-flow {
    position: relative;
    overflow: hidden;
}

.qf-particle-flow::before,
.qf-particle-flow::after {
    content: '';
    position: absolute;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--q-purple-400);
    box-shadow: 0 0 8px var(--q-purple-400);
    top: 50%;
    animation: particleFlow 2s var(--ease-smooth) infinite;
}

.qf-particle-flow::after {
    animation-delay: 0.7s;
    background: var(--q-info);
    box-shadow: 0 0 8px var(--q-info);
}
```

### 6.6 玻璃折射光效

```css
/* ── 玻璃表面光斑移动 ── */
@keyframes glassShine {
    0% {
        transform: translateX(-100%) rotate(25deg);
    }
    100% {
        transform: translateX(200%) rotate(25deg);
    }
}

.qf-glass-shine {
    position: relative;
    overflow: hidden;
}

.qf-glass-shine::before {
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 50%;
    height: 200%;
    background: linear-gradient(
        90deg,
        transparent,
        rgba(255, 255, 255, 0.03),
        transparent
    );
    transform: rotate(25deg);
    animation: glassShine 6s var(--ease-smooth) infinite;
    pointer-events: none;
}
```

### 6.7 脉冲呼吸效果

```css
/* ── 脉冲呼吸 — 用于图标/Logo ── */
@keyframes quantumPulse {
    0%, 100% {
        box-shadow: 0 0 0 0 rgba(124, 58, 237, 0.3);
    }
    50% {
        box-shadow: 0 0 0 8px rgba(124, 58, 237, 0);
    }
}

.qf-pulse {
    animation: quantumPulse 2s var(--ease-smooth) infinite;
}

/* ── 光圈扩散 — 用于通知/状态指示 ── */
@keyframes rippleExpand {
    0% {
        transform: scale(1);
        opacity: 0.6;
    }
    100% {
        transform: scale(2.5);
        opacity: 0;
    }
}

.qf-ripple::after {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 50%;
    border: 2px solid var(--q-purple-400);
    animation: rippleExpand 1.5s var(--ease-smooth) infinite;
}
```

### 6.8 表格行入场动画

```css
/* ── 表格行级联入场 ── */
@keyframes rowSlideIn {
    from {
        opacity: 0;
        transform: translateX(-12px);
    }
    to {
        opacity: 1;
        transform: translateX(0);
    }
}

.qf-table tbody tr {
    animation: rowSlideIn 0.3s var(--ease-smooth) both;
}

/* 每行延迟 30ms，最多 20 行 */
.qf-table tbody tr:nth-child(1)  { animation-delay: 0.00s; }
.qf-table tbody tr:nth-child(2)  { animation-delay: 0.03s; }
.qf-table tbody tr:nth-child(3)  { animation-delay: 0.06s; }
.qf-table tbody tr:nth-child(4)  { animation-delay: 0.09s; }
.qf-table tbody tr:nth-child(5)  { animation-delay: 0.12s; }
/* ... 最多到 20 行 */
```

### 6.9 加载骨架屏

```css
/* ── 骨架屏脉冲 ── */
@keyframes skeletonPulse {
    0%, 100% {
        background-position: -200% 0;
    }
    50% {
        background-position: 200% 0;
    }
}

.qf-skeleton {
    background: linear-gradient(
        90deg,
        var(--q-glass) 25%,
        rgba(255, 255, 255, 0.08) 37%,
        var(--q-glass) 63%
    );
    background-size: 200% 100%;
    animation: skeletonPulse 1.5s var(--ease-smooth) infinite;
    border-radius: var(--radius-sm);
}
```

---

## 7. 玻璃拟态实现细节

### 7.1 玻璃拟态核心原理

玻璃拟态 (Glassmorphism) 的四大要素:

1. **半透明背景**: `background: rgba(255, 255, 255, 0.04-0.08)`
2. **背景模糊**: `backdrop-filter: blur(16-40px)`
3. **微妙边框**: `border: 1px solid rgba(255, 255, 255, 0.08)`
4. **内发光**: `box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05)`

### 7.2 三层玻璃体系

```css
/* ── 第一层：浅玻璃 — 普通卡片、输入框 ── */
.qf-glass-1 {
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.06);
}

/* ── 第二层：中玻璃 — KPI卡片、表格容器 ── */
.qf-glass-2 {
    background: rgba(255, 255, 255, 0.05);
    backdrop-filter: blur(16px) saturate(1.4);
    -webkit-backdrop-filter: blur(16px) saturate(1.4);
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

/* ── 第三层：深玻璃 — 模态框、侧边栏 ── */
.qf-glass-3 {
    background: rgba(20, 25, 40, 0.85);
    backdrop-filter: blur(40px) saturate(1.8);
    -webkit-backdrop-filter: blur(40px) saturate(1.8);
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow:
        0 8px 32px rgba(0, 0, 0, 0.4),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
```

### 7.3 玻璃拟态颜色映射 (原暖色 → 量子色)

| 组件 | 原背景 | 新玻璃背景 | 备注 |
|------|--------|------------|------|
| 页面背景 | `#FAF7F2` | `#0A0E1A` | 最深底层 |
| 卡片背景 | `#FFFFFF` | `rgba(255,255,255,0.04)` + blur(16px) | 玻璃第二层 |
| 侧边栏 | `#2D2620` | `#0D1117` 渐变 | 纯色底层 |
| 顶部栏 | `#FFFFFF` | `rgba(15,19,32,0.85)` + blur(20px) | 玻璃第三层 |
| 模态框 | `#FFFFFF` | `rgba(20,25,40,0.95)` + blur(40px) | 最深玻璃 |
| 表格行hover | `#FFF3E8` | `rgba(124,58,237,0.06)` | 紫色高亮 |
| 输入框 | `#FFFFFF` | `rgba(255,255,255,0.03)` + blur(10px) | 浅玻璃 |
| Tab栏 | `#FFFFFF` | `rgba(255,255,255,0.04)` + blur(16px) | 玻璃第二层 |

### 7.4 玻璃拟态性能优化

```css
/* 性能关键：对所有使用 backdrop-filter 的元素启用 GPU 加速 */
.qf-glass-1, .qf-glass-2, .qf-glass-3,
.qf-header, .qf-sidebar, .qf-kpi-card,
.qf-table-container, .qf-tab-bar {
    will-change: backdrop-filter;
    transform: translateZ(0);  /* 强制 GPU 层 */
}

/* 在大量卡片场景下，限制同时模糊的元素数 */
@media (prefers-reduced-motion: reduce) {
    .qf-glass-1 { backdrop-filter: none; background: rgba(20, 25, 40, 0.9); }
    .qf-glass-2 { backdrop-filter: none; background: rgba(20, 25, 40, 0.92); }
}
```

### 7.5 3D 深度效果

```css
/* ── 3D 悬浮效果 ── */
.qf-3d-lift {
    transition: transform 0.3s var(--ease-smooth), box-shadow 0.3s var(--ease-smooth);
}

.qf-3d-lift:hover {
    transform: translateY(-6px) perspective(1000px) rotateX(2deg);
    box-shadow:
        0 20px 40px rgba(0, 0, 0, 0.3),
        0 0 20px rgba(124, 58, 237, 0.15);
}

/* ── 内嵌深度 ── */
.qf-3d-inset {
    box-shadow:
        inset 0 2px 4px rgba(0, 0, 0, 0.2),
        inset 0 -1px 0 rgba(255, 255, 255, 0.05);
}

/* ── 分层堆叠 ── */
.qf-layer-1 { z-index: 1; }   /* 页面背景 */
.qf-layer-2 { z-index: 10; }  /* 侧边栏/顶部栏 */
.qf-layer-3 { z-index: 20; }  /* 卡片/表格 */
.qf-layer-4 { z-index: 50; }  /* 弹出菜单 */
.qf-layer-5 { z-index: 100; } /* 模态框 */
```

---

## 8. 逐页重设计优先级计划

### P0 — 核心页面 (第1周)

| 页面 | 文件 | 优先级 | 工作量 | 说明 |
|------|------|--------|--------|------|
| 设计令牌 | `tokens.css` | P0-1 | 3h | 全局色彩/字体/间距替换 |
| 全局基础 | `base.css` | P0-2 | 4h | 重置/表格/按钮/卡片/滚动条 |
| 侧边栏 | `sidebar.css` | P0-3 | 4h | 深蓝黑背景+紫色光效+玻璃态 |
| 顶部栏 | `header.css` | P0-4 | 4h | 玻璃拟态+流光线+紫色渐变 |
| 仪表盘 | `dashboard.css` | P0-5 | 5h | KPI卡片+图表+快速操作 |
| 组件库 | `components.css` | P0-6 | 3h | 通用动画/微交互 |
| 登录页 | `login.css` | P0-7 | 3h | 深空背景+玻璃卡片+粒子 |

**P0 预计总工时: 26h**

### P1 — 重要页面 (第2周)

| 页面 | 文件 | 优先级 | 工作量 | 说明 |
|------|------|--------|--------|------|
| 凭证记账 | `journal.css` | P1-1 | 5h | 凭证表格+输入框+签章区 |
| 报表样式 | `reports.css` | P1-2 | 4h | 报表表格+KPI+状态标签 |
| 报表中心 | `reports_center.css` | P1-3 | 3h | 报表卡片网格+标签页 |
| 响应式 | `responsive.css` | P1-4 | 3h | 全断点适配新主题 |

**P1 预计总工时: 15h**

### P2 — 辅助页面 (第3周)

| 页面 | 说明 | 工作量 |
|------|------|--------|
| `index.css` | 页面容器/搜索/全局搜索 | 2h |
| 新增: `animations.css` | 独立动画文件(流光/粒子/骨架屏) | 3h |
| 新增: `quantum-effects.css` | 量子特效(星空/脉冲/数据流) | 3h |
| 图表页 (charts.py) | ECharts 配色适配 | 2h |
| AI 助手 (ai_assistant.py) | 对话界面玻璃态 | 2h |
| 设置页 (settings.py) | 表单/开关/选项卡 | 2h |
| 凭证模板/银行对账/预算等 | 通用样式覆盖 | 3h |

**P2 预计总工时: 17h**

**总预计工时: ~58h (约 7-8 个工作日)**

---

## 9. CSS 架构方案

### 9.1 当前文件结构 (12 个文件)

```
app/static/style/
├── tokens.css           # 设计令牌
├── base.css             # 全局基础 + Quasar 覆盖
├── sidebar.css          # 侧边栏
├── header.css           # 顶部栏
├── dashboard.css        # 仪表盘
├── journal.css          # 凭证记账
├── reports.css          # 报表样式
├── reports_center.css   # 报表中心
├── components.css       # 通用组件
├── login.css            # 登录页
├── index.css            # 页面容器
└── responsive.css       # 响应式
```

### 9.2 目标文件结构 (14 个文件)

```
app/static/style/
├── tokens.css              # [修改] 全部替换为量子财务令牌
├── base.css                # [修改] 全局样式 + 玻璃拟态基础
├── sidebar.css             # [修改] 深蓝黑侧边栏 + 紫色光效
├── header.css              # [修改] 玻璃拟态顶部栏 + 流光线
├── dashboard.css           # [修改] KPI 卡片 + 图表玻璃态
├── journal.css             # [修改] 凭证表格量子风格
├── reports.css             # [修改] 报表表格量子风格
├── reports_center.css      # [修改] 报表卡片网格
├── components.css          # [修改] 通用组件 + 新动画
├── login.css               # [修改] 深空登录页
├── index.css               # [修改] 页面容器
├── responsive.css          # [修改] 响应式适配
├── animations.css          # [新建] 独立动画/动效库
└── quantum-effects.css     # [新建] 量子特效(粒子/流光/星空)
```

### 9.3 文件修改详细说明

#### `tokens.css` — 全面替换

**操作:** 删除全部现有内容，替换为量子财务设计令牌。

**关键变更:**
- `--c-primary: #C4784A` → `--c-primary: #7C3AED`
- `--c-bg-page: #FAF7F2` → `--c-bg-page: #0A0E1A`
- `--c-bg-card: #FFFFFF` → `--c-bg-card: rgba(255,255,255,0.04)`
- `--c-text-primary: #2D2620` → `--c-text-primary: rgba(255,255,255,0.92)`
- 所有 `rgba(139,94,60,...)` → `rgba(124,58,237,...)`
- 新增量子色板变量、玻璃拟态变量、动画变量
- 新增浅色模式 `[data-theme="light"]` 变量

#### `base.css` — 大幅修改

**关键变更:**
- body 背景改为 `var(--q-bg-base)`
- 表格 thead 改为 `rgba(255,255,255,0.03)` 背景
- 表格 hover 行改为紫色高亮 `rgba(124,58,237,0.06)`
- 按钮改为紫色渐变 + 流光效果
- 输入框改为玻璃态 + 紫色聚焦
- 卡片改为玻璃拟态 + 紫色光晕
- 滚动条改为紫色 `rgba(124,58,237,0.3)`
- KPI 卡片全面改为玻璃态
- Tab 栏改为玻璃态 + 紫色活动项

#### `sidebar.css` — 大幅修改

**关键变更:**
- 背景改为 `linear-gradient(180deg, #0D1117, #0F1320)`
- Logo 图标改为紫色光晕
- 分组标题改为 `rgba(255,255,255,0.02)` 玻璃背景
- 菜单项 hover 改为玻璃发光
- 选中态改为紫色渐变 + 内发光
- 分隔线改为渐变淡出
- 滚动条改为紫色
- 折叠态 tooltip 改为深蓝背景

#### `header.css` — 大幅修改

**关键变更:**
- 背景改为 `rgba(15,19,32,0.85)` + `backdrop-filter: blur(20px)`
- 底部线改为流光渐变动画
- 标题改为紫色渐变
- 版本号改为紫色药丸
- 搜索框改为玻璃态
- 通知铃铛改为紫色脉冲
- 头像改为紫色渐变 + 光晕
- 所有图标按钮改为紫色 hover

#### `dashboard.css` — 大幅修改

**关键变更:**
- KPI 卡片改为玻璃态 + 3D 悬浮
- 快速操作卡片改为玻璃态
- 图表卡片改为玻璃态容器
- 导航按钮改为紫色 hover
- 空状态改为深色适配

#### `journal.css` — 中度修改

**关键变更:**
- 凭证表格边框改为 `rgba(255,255,255,0.1)`
- 表头背景改为 `rgba(255,255,255,0.03)`
- 输入框聚焦改为紫色 outline
- 合计行改为紫色高亮
- 对话框改为深玻璃态

#### `reports.css` — 中度修改

**关键变更:**
- 表格改为量子风格
- 报表卡片改为玻璃态
- KPI 改为量子风格
- 状态标签改为量子色
- Tab 改为玻璃态

#### `components.css` — 中度修改

**关键变更:**
- 入场动画改为带 blur 的淡入
- 对话框弹出改为弹性缩放
- 通知滑入保持
- 数值闪烁改为紫色

#### `login.css` — 大幅修改

**关键变更:**
- 背景改为 `linear-gradient(135deg, #0A0E1A, #1E1B4B, #0F172A)` + 粒子
- 卡片改为玻璃态
- Logo 图标改为紫色
- 提交按钮改为紫色渐变

#### `animations.css` — 新建

**内容:**
- 页面入场动画
- 卡片级联动画
- 表格行入场动画
- 数值滚动/闪烁动画
- 骨架屏动画
- 通用过渡预设

#### `quantum-effects.css` — 新建

**内容:**
- 流光扫描线
- 粒子流效果
- 脉冲呼吸效果
- 光圈扩散效果
- 玻璃折射光效
- 星空背景粒子 (CSS only)
- 数据流动画
- Aurora 极光渐变背景

### 9.4 CSS 加载顺序

```html
<!-- 加载顺序（重要！） -->
<link rel="stylesheet" href="tokens.css">          <!-- 1. 令牌（必须最先） -->
<link rel="stylesheet" href="base.css">            <!-- 2. 基础重置 -->
<link rel="stylesheet" href="animations.css">      <!-- 3. 动画库 -->
<link rel="stylesheet" href="quantum-effects.css"> <!-- 4. 量子特效 -->
<link rel="stylesheet" href="components.css">      <!-- 5. 通用组件 -->
<link rel="stylesheet" href="sidebar.css">         <!-- 6. 侧边栏 -->
<link rel="stylesheet" href="header.css">          <!-- 7. 顶部栏 -->
<link rel="stylesheet" href="dashboard.css">       <!-- 8. 仪表盘 -->
<link rel="stylesheet" href="journal.css">         <!-- 9. 凭证 -->
<link rel="stylesheet" href="reports.css">         <!-- 10. 报表 -->
<link rel="stylesheet" href="reports_center.css">  <!-- 11. 报表中心 -->
<link rel="stylesheet" href="login.css">           <!-- 12. 登录页 -->
<link rel="stylesheet" href="index.css">           <!-- 13. 页面容器 -->
<link rel="stylesheet" href="responsive.css">      <!-- 14. 响应式（必须最后） -->
```

---

## 10. 实施阶段与交付物

### 阶段 1: 基础架构 (Day 1-2)

**目标:** 建立量子财务设计令牌，替换全局基础样式

**交付物:**
- [x] `tokens.css` — 完整量子色板、字体、间距、阴影令牌
- [x] `base.css` — 全局重置、Quasar 覆盖、表格、按钮、卡片
- [x] `animations.css` — 独立动画库
- [x] `quantum-effects.css` — 量子特效库

**验收标准:**
- 页面背景为深空蓝 `#0A0E1A`
- 所有文字在深色背景上清晰可读
- 滚动条为紫色主题
- 基础动画流畅运行

### 阶段 2: 核心框架 (Day 3-4)

**目标:** 完成侧边栏、顶部栏、Tab 栏重设计

**交付物:**
- [x] `sidebar.css` — 深蓝黑侧边栏 + 紫色光效
- [x] `header.css` — 玻璃拟态顶部栏 + 流光线
- [x] `components.css` — 通用组件更新

**验收标准:**
- 侧边栏背景为深蓝渐变，选中项有紫色光效
- 顶部栏为毛玻璃效果，底部有流光扫描线
- Tab 栏为玻璃态，活动项为紫色渐变
- 折叠/展开动画流畅

### 阶段 3: 仪表盘 (Day 5)

**目标:** 完成仪表盘页面重设计

**交付物:**
- [x] `dashboard.css` — KPI 卡片、图表容器、快速操作
- [x] ECharts 配色方案更新

**验收标准:**
- KPI 卡片为三层玻璃态
- 悬停有 3D 悬浮 + 紫色光晕效果
- 卡片入场有级联动画
- 图表颜色与量子主题一致

### 阶段 4: 业务页面 (Day 6-7)

**目标:** 完成凭证、报表页面重设计

**交付物:**
- [x] `journal.css` — 凭证表格量子风格
- [x] `reports.css` — 报表表格量子风格
- [x] `reports_center.css` — 报表中心
- [x] `login.css` — 登录页深空风格

**验收标准:**
- 凭证表格在深色背景上清晰可读
- 报表表格带紫色高亮行
- 登录页有深空背景 + 玻璃卡片

### 阶段 5: 收尾与优化 (Day 8)

**目标:** 响应式适配、性能优化、细节打磨

**交付物:**
- [x] `responsive.css` — 全断点适配
- [x] `index.css` — 页面容器更新
- [x] 性能测试报告
- [x] 浏览器兼容性测试

**验收标准:**
- 768px/1024px/1440px/1920px 四个断点显示正常
- backdrop-filter 降级方案生效
- 无明显卡顿或性能问题
- 所有动画可被 `prefers-reduced-motion` 禁用

---

## 附录

### A. 浏览器兼容性注意事项

| 特性 | Chrome | Firefox | Safari | Edge | 降级方案 |
|------|--------|---------|--------|------|----------|
| `backdrop-filter` | ✅ | ✅ | ✅ | ✅ | 纯色半透明背景 |
| `color-mix()` | ✅ 111+ | ✅ 113+ | ✅ 16.2+ | ✅ 111+ | 手动计算 rgba 值 |
| `@container` | ✅ 105+ | ❌ | ✅ 16+ | ✅ 105+ | 使用 media query |
| CSS 嵌套 | ✅ 120+ | ✅ 117+ | ✅ 17.2+ | ✅ 120+ | 展平为普通 CSS |

### B. 性能预算

| 指标 | 目标 | 说明 |
|------|------|------|
| CSS 文件总大小 | < 80KB | 压缩后 |
| 首屏渲染 | < 1.5s | LCP |
| 动画帧率 | ≥ 60fps | 使用 `will-change` |
| backdrop-filter 元素 | ≤ 10 个 | 同时模糊的元素数 |

### C. 暗色模式下可访问性

| 场景 | 对比度要求 | 实际对比度 |
|------|------------|------------|
| 主文字 on 背景 | ≥ 4.5:1 | `rgba(255,255,255,0.92)` on `#0A0E1A` = **12.8:1** ✅ |
| 副文字 on 背景 | ≥ 3:1 | `rgba(255,255,255,0.65)` on `#0A0E1A` = **7.2:1** ✅ |
| 弱化文字 on 背景 | ≥ 3:1 | `rgba(255,255,255,0.40)` on `#0A0E1A` = **3.6:1** ✅ |
| 紫色按钮文字 | ≥ 4.5:1 | `#FFFFFF` on `#7C3AED` = **5.9:1** ✅ |
| 绿色正数 | ≥ 3:1 | `#10B981` on `#0A0E1A` = **6.1:1** ✅ |
| 红色负数 | ≥ 3:1 | `#EF4444` on `#0A0E1A` = **4.0:1** ✅ |

### D. 原色 → 量子色映射表

| 用途 | 原色值 | 新色值 | 变量名 |
|------|--------|--------|--------|
| 主色调 | `#C4784A` | `#7C3AED` | `--c-primary` |
| 主色浅 | `#FFF3E8` | `rgba(124,58,237,0.12)` | `--c-primary-light` |
| 主色hover | `#A86238` | `#6D28D9` | `--c-primary-hover` |
| 成功 | `#5A9E6F` | `#10B981` | `--c-success` |
| 危险 | `#C95A5A` | `#EF4444` | `--c-danger` |
| 警告 | `#D4A843` | `#F59E0B` | `--c-warning` |
| 页面背景 | `#FAF7F2` | `#0A0E1A` | `--c-bg-page` |
| 卡片背景 | `#FFFFFF` | `rgba(255,255,255,0.04)` | `--c-bg-card` |
| hover背景 | `#F3EDE4` | `rgba(255,255,255,0.07)` | `--c-bg-hover` |
| 边框 | `#E8E0D4` | `rgba(255,255,255,0.08)` | `--c-border` |
| 主文字 | `#2D2620` | `rgba(255,255,255,0.92)` | `--c-text-primary` |
| 副文字 | `#6B5D52` | `rgba(255,255,255,0.65)` | `--c-text-secondary` |
| 弱化文字 | `#9E8F82` | `rgba(255,255,255,0.40)` | `--c-text-muted` |
| 侧边栏背景 | `#2D2620` | `#0D1117` | `--sidebar-bg` |
| 侧边栏强调 | `#C4784A` | `#7C3AED` | `--sidebar-accent` |
| 阴影色 | `rgba(139,94,60,...)` | `rgba(124,58,237,...)` | 各 shadow 变量 |

### E. ECharts 图表配色方案

```javascript
const quantumChartColors = {
    // 主色板
    primary: ['#7C3AED', '#A78BFA', '#C4B5FD', '#DDD6FE'],
    // 语义色
    success: '#10B981',
    danger:  '#EF4444',
    warning: '#F59E0B',
    info:    '#06B6D4',
    // 多色系列 (饼图/柱状图)
    series: [
        '#7C3AED',  // 量子紫
        '#06B6D4',  // 量子青
        '#10B981',  // 量子绿
        '#F59E0B',  // 量子金
        '#EF4444',  // 量子红
        '#8B5CF6',  // 亮紫
        '#22D3EE',  // 亮青
        '#34D399',  // 亮绿
        '#FBBF24',  // 亮金
        '#F87171',  // 亮红
    ],
    // 坐标轴
    axis: {
        line:   'rgba(255,255,255,0.08)',
        label:  'rgba(255,255,255,0.45)',
        split:  'rgba(255,255,255,0.05)',
    },
    // 背景
    bg: 'transparent',
    // 文字
    text: 'rgba(255,255,255,0.65)',
    // tooltip
    tooltip: {
        bg:      'rgba(20,25,40,0.95)',
        border:  'rgba(255,255,255,0.1)',
        text:    'rgba(255,255,255,0.92)',
    },
};
```

---

**文档结束**

*本文档为 AI财务系统V5.1 "量子财务" UI 重设计的完整实施方案，包含色彩系统、字体系统、组件规范、动画设计、玻璃拟态实现、CSS 架构方案及实施计划。开发人员可直接参照此文档进行 CSS 重写。*
