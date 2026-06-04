---
name: python-environment
description: 财务系统 V5.1 的 Python 环境路径和启动方式
metadata:
  type: project
---

## Python 环境

- **Python 路径**: `F:\tools\Python311\python.exe`（Python 3.11.9）← 全局工具目录
- **旧路径**: `E:\工具\Python311\python.exe`（已废弃，待清理）
- **启动方式**: `node -e "const {execSync}=require('child_process'); execSync('F:/tools/Python311/python.exe app.py', {cwd:'E:/ClaudeCode/my-project', stdio:'inherit'})"`
- **访问地址**: http://localhost:8090
- **run_server.py**: 已更新为 `F:\tools\Python311\python.exe`
- **start.bat**: 已更新为 `F:\tools\Python311\python.exe`

## 为什么 bash 直接调用 Windows 路径会失败

- bash 会把 `\` 当转义符，导致路径被破坏
- 解决方案：用 Node.js 的 `child_process` 执行（路径用正斜杠 `/`），或写 `.bat` 文件
- PowerShell 在 bash 中调用有中文编码问题，输出全部乱码
- 最佳方案：写 `.js` 文件通过 `node` 执行，完全绕过编码和转义问题

## 依赖情况

- nicegui 3.12.1 ✅
- fastapi / uvicorn / sqlalchemy / aiosqlite / bcrypt / reportlab / openpyxl 均已安装
