# 验证报告 — 2026-05-19 14:09:16

## 总览

| 指标 | 值 |
|------|-----|
| 总计 | 3 |
| ✅ 通过 | 2 |
| ❌ 失败 | 1 |
| 耗时 | 13.0s |
| 结果 | 💥 存在失败 |

## 详细结果

| # | 测试 | 状态 | 耗时 |
|---|------|------|------|
| 1 | CSS 模块化结构检查 | ✅ PASS | 3.8s |
| 2 | 页面渲染测试（28页面 + 3组件） | ❌ FAIL | 4.0s |
| 3 | 浏览器 UI 验证（登录/Sidebar/导航/样式） | ✅ PASS | 2.8s |

## 失败详情

### 页面渲染测试（28页面 + 3组件）

```
eader-ba
  ✅ sidebar
  ❌ login: 
     Traceback (most recent call last):
  File "E:\ClaudeCode\my-project\tests\test_render.py", line 142, in test_components
    render_fn()
    ~~~~~~~~~^^
  File "E:\ClaudeCode\my-project\app\pages\auth.py", line 74, in render_login
    ui.run_javascript("""
    ~~~~~~~~~~~~~~~~~^^^^
        const save

结果: ✅ 1 / ❌ 2 / 总计 3

============================================================
💥 存在失败项，请检查上方输出
============================================================

```


## 截图

无截图。