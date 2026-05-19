"""
一键运行所有验证 —— 生成验证报告

运行方法:
  1. 先启动服务器: python app.py
  2. 运行: python tests/run_all.py

输出:
  - 控制台实时结果
  - tests/report.md —— 完整验证报告
  - tests/screenshots/ —— 浏览器截图
"""
import subprocess
import sys
import os
import time
import datetime

REPORT_PATH = os.path.join(os.path.dirname(__file__), "report.md")
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")


def run_cmd(name, cmd, timeout=60):
    """运行命令并返回结果"""
    print(f"\n{'='*60}")
    print(f"▶ {name}")
    print(f"{'='*60}")
    start = time.time()
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=os.path.dirname(os.path.dirname(__file__))
        )
        elapsed = time.time() - start
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        status = "PASS" if passed else "FAIL"
        print(output[-2000:] if len(output) > 2000 else output)  # 最后 2000 字符
        print(f"\n[{status}] {name} ({elapsed:.1f}s)")
        return {
            "name": name,
            "status": status,
            "elapsed": elapsed,
            "output": output,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        print(f"\n[TIMEOUT] {name} ({elapsed:.1f}s)")
        return {
            "name": name,
            "status": "TIMEOUT",
            "elapsed": elapsed,
            "output": "",
            "returncode": -1,
        }
    except Exception as e:
        elapsed = time.time() - start
        print(f"\n[ERROR] {name}: {e}")
        return {
            "name": name,
            "status": "ERROR",
            "elapsed": elapsed,
            "output": str(e),
            "returncode": -1,
        }


def generate_report(results, total_time):
    """生成 Markdown 验证报告"""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] != "PASS")
    total = len(results)

    lines = [
        f"# 验证报告 — {now}",
        f"",
        f"## 总览",
        f"",
        f"| 指标 | 值 |",
        f"|------|-----|",
        f"| 总计 | {total} |",
        f"| ✅ 通过 | {passed} |",
        f"| ❌ 失败 | {failed} |",
        f"| 耗时 | {total_time:.1f}s |",
        f"| 结果 | {'🎉 全部通过' if failed == 0 else '💥 存在失败'} |",
        f"",
        f"## 详细结果",
        f"",
        f"| # | 测试 | 状态 | 耗时 |",
        f"|---|------|------|------|",
    ]

    for i, r in enumerate(results, 1):
        icon = "✅" if r["status"] == "PASS" else "❌"
        lines.append(f"| {i} | {r['name']} | {icon} {r['status']} | {r['elapsed']:.1f}s |")

    lines += [
        f"",
        f"## 失败详情",
        f"",
    ]

    fail_results = [r for r in results if r["status"] != "PASS"]
    if fail_results:
        for r in fail_results:
            lines += [
                f"### {r['name']}",
                f"",
                f"```",
                f"{r['output'][-500:]}",
                f"```",
                f"",
            ]
    else:
        lines.append("无失败项。")

    lines += [
        f"",
        f"## 截图",
        f"",
    ]

    # 列出截图文件
    if os.path.exists(SCREENSHOT_DIR):
        screenshots = sorted(os.listdir(SCREENSHOT_DIR))
        if screenshots:
            for s in screenshots:
                lines.append(f"- `{s}`")
        else:
            lines.append("无截图。")
    else:
        lines.append("截图目录不存在。")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n报告已保存: {REPORT_PATH}")


def main():
    print("=" * 60)
    print("一键验证 —— AI 财务系统 V5.1")
    print("=" * 60)
    print(f"时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    total_start = time.time()
    results = []

    # ── Level 1: 静态检查（不需要服务器）──
    results.append(run_cmd(
        "CSS 模块化结构检查",
        f"{sys.executable} -m pytest tests/test_css_modules.py -v --tb=short 2>&1",
        timeout=30,
    ))

    # ── Level 2: 渲染测试（需要 NiceGUI 环境，不需要浏览器）──
    results.append(run_cmd(
        "页面渲染测试（28页面 + 3组件）",
        f"{sys.executable} tests/test_render.py 2>&1",
        timeout=120,
    ))

    # ── Level 3: 浏览器 UI 测试（需要服务器运行）──
    # 检查服务器是否可用
    import urllib.request
    try:
        urllib.request.urlopen("http://localhost:8090/", timeout=3)
        server_ok = True
    except:
        server_ok = False

    if server_ok:
        results.append(run_cmd(
            "浏览器 UI 验证（登录/Sidebar/导航/样式）",
            f"{sys.executable} tests/test_browser_ui.py 2>&1",
            timeout=120,
        ))
    else:
        print("\n⚠️ 服务器未运行，跳过浏览器 UI 验证")
        print("   启动服务器: python app.py")
        results.append({
            "name": "浏览器 UI 验证",
            "status": "SKIP",
            "elapsed": 0,
            "output": "服务器未运行",
            "returncode": 0,
        })

    # ── 生成报告 ──
    total_time = time.time() - total_start
    generate_report(results, total_time)

    # 最终输出
    failed = sum(1 for r in results if r["status"] not in ("PASS", "SKIP"))
    print(f"\n{'='*60}")
    if failed == 0:
        print("🎉 全部验证通过")
    else:
        print(f"💥 {failed} 项失败，请查看报告: {REPORT_PATH}")
    print(f"{'='*60}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
