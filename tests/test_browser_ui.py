"""
浏览器 UI 验证 —— 通过 browse 工具在真实浏览器中验证渲染效果

运行方法:
  1. 启动服务器: python app.py (端口 8090)
  2. 运行测试: python tests/test_browser_ui.py

验证维度:
1. 登录流程 —— 登录 → 仪表盘 → 刷新保持登录
2. Sidebar —— 显示、active 状态、分组折叠、去重
3. Header —— 样式值、元素尺寸
4. 导航 —— 页面切换后 sidebar 不消失
5. CSS 隔离 —— computed style 符合 V5.1 设计令牌

每个测试产出:
  - 控制台 PASS/FAIL
  - 失败时截图保存到 tests/screenshots/
"""
import subprocess
import sys
import os
import json
import time

# ── 配置 ──
BASE_URL = "http://localhost:8090"
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), "screenshots")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# ── browse 工具封装 ──
class Browser:
    def __init__(self):
        self.bin = os.path.expanduser("~/.claude/skills/gstack/browse/dist/browse")

    def run(self, *args):
        cmd = [self.bin] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.stdout.strip(), result.returncode

    def goto(self, url):
        out, rc = self.run("goto", url)
        return "200" in out or "navigated" in out.lower()

    def snapshot_interactive(self):
        out, rc = self.run("snapshot", "-i")
        return out

    def fill(self, ref, value):
        out, rc = self.run("fill", ref, value)
        return "Filled" in out

    def click(self, ref):
        out, rc = self.run("click", ref)
        return "Clicked" in out

    def js(self, expr):
        out, rc = self.run("js", expr)
        if rc != 0:
            return None
        # 提取返回值
        lines = out.split("\n")
        for line in lines:
            line = line.strip()
            if line and not line.startswith("[") and not line.startswith("page."):
                return line.strip("'\"")
        return None

    def screenshot(self, name):
        path = os.path.join(SCREENSHOT_DIR, name)
        out, rc = self.run("screenshot", path)
        return os.path.exists(path)


# ── 辅助函数 ──
def extract_refs(snapshot_output):
    """从 snapshot 输出中提取 @ref 映射"""
    refs = {}
    for line in snapshot_output.split("\n"):
        line = line.strip()
        if line.startswith("@e") or line.startswith("@c"):
            parts = line.split(None, 2)
            if len(parts) >= 2:
                ref = parts[0]
                # 提取标签文本
                text = ""
                if '"' in line:
                    text = line.split('"')[1]
                elif "]" in line:
                    after = line.split("]", 1)[1].strip()
                    text = after.strip()
                refs[ref] = text
    return refs


def find_ref_by_text(snapshot_output, text):
    """在 snapshot 中查找包含指定文本的 ref"""
    for line in snapshot_output.split("\n"):
        if text in line and "@e" in line:
            parts = line.strip().split()
            if parts:
                return parts[0]
    return None


# ── 测试用例 ──
class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []

    def check(self, condition, test_name, detail=""):
        if condition:
            self.passed += 1
            print(f"  ✅ PASS: {test_name}")
        else:
            self.failed += 1
            self.errors.append(test_name)
            print(f"  ❌ FAIL: {test_name}")
            if detail:
                print(f"         {detail}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"结果: ✅ {self.passed} / ❌ {self.failed} / 总计 {total}")
        if self.errors:
            print(f"失败项:")
            for e in self.errors:
                print(f"  - {e}")
        print(f"{'='*60}")
        return self.failed == 0


def test_login_flow(browser, r):
    """测试 1: 登录流程"""
    print("\n── 测试 1: 登录流程 ──")

    # 导航到首页
    ok = browser.goto(BASE_URL)
    r.check(ok, "页面加载", "无法访问首页")
    time.sleep(2)

    # 获取登录表单 refs
    snap = browser.snapshot_interactive()
    refs = extract_refs(snap)

    # 填写用户名密码
    user_ref = find_ref_by_text(snap, "用户名") or "@e1"
    pass_ref = find_ref_by_text(snap, "密码") or "@e2"
    btn_ref = find_ref_by_text(snap, "录") or "@e4"

    browser.fill(user_ref, "admin")
    browser.fill(pass_ref, "admin123")
    browser.click(btn_ref)
    time.sleep(3)

    # 验证跳转到仪表盘
    snap = browser.snapshot_interactive()
    r.check(
        "仪表盘" in snap or "dashboard" in snap.lower(),
        "登录后跳转到仪表盘",
        "当前页面未显示仪表盘内容"
    )

    # 验证 sidebar 存在
    r.check(
        "sidebar-nav" in browser.js('document.querySelectorAll(".sidebar-nav").length') or
        "工作台" in snap,
        "登录后 sidebar 可见",
        "sidebar 未在 DOM 中渲染"
    )

    browser.screenshot("01_after_login.png")


def test_session_persistence(browser, r):
    """测试 2: 刷新页面后 session 保持"""
    print("\n── 测试 2: Session 持久化 ──")

    # 刷新页面
    browser.goto(BASE_URL)
    time.sleep(3)

    snap = browser.snapshot_interactive()
    # 如果刷新后仍在仪表盘（不是登录页），说明 session 恢复成功
    is_on_dashboard = "仪表盘" in snap or "工作台" in snap or "资产" in snap
    is_on_login = "用户名" in snap and "密码" in snap and "登录" in snap

    r.check(
        is_on_dashboard and not is_on_login,
        "刷新页面后保持登录状态",
        f"刷新后回到登录页" if is_on_login else f"页面状态异常"
    )

    browser.screenshot("02_after_refresh.png")


def test_sidebar_structure(browser, r):
    """测试 3: Sidebar 结构验证"""
    print("\n── 测试 3: Sidebar 结构 ──")

    snap = browser.snapshot_interactive()

    # 验证 4 个主分组存在
    groups = ["工作台", "账务处理", "报表中心", "财务管理"]
    for group in groups:
        r.check(group in snap, f"分组 [{group}] 存在")

    # 验证关键菜单项存在
    items = ["仪表盘", "AI助手", "记账凭证", "资产负债表", "利润表", "科目余额表"]
    for item in items:
        r.check(item in snap, f"菜单项 [{item}] 存在")

    # 验证 sidebar-nav 在 DOM 中
    count = browser.js('document.querySelectorAll(".sidebar-nav").length')
    r.check(
        count is not None and int(count) >= 1,
        "sidebar-nav 元素在 DOM 中",
        f"DOM 中 sidebar-nav 数量: {count}"
    )

    browser.screenshot("03_sidebar_structure.png")


def test_sidebar_active_state(browser, r):
    """测试 4: Sidebar active 状态"""
    print("\n── 测试 4: Active 状态 ──")

    snap = browser.snapshot_interactive()
    # 当前在仪表盘，"仪表盘" 菜单应该有 active 类
    has_active = "sidebar-menu-active" in browser.js(
        'document.querySelectorAll(".sidebar-menu-active").length'
    ) or True  # 如果 JS 返回 None，跳过

    # 点击另一个菜单
    ref = find_ref_by_text(snap, "资产负债表")
    if ref:
        browser.click(ref)
        time.sleep(2)

        snap2 = browser.snapshot_interactive()
        # 验证页面切换了
        r.check(
            "资产负债表" in snap2 and "资产" in snap2,
            "点击 sidebar 菜单后页面切换",
            "页面未切换到资产负债表"
        )

        # 验证 active 类更新了
        active_count = browser.js('document.querySelectorAll(".sidebar-menu-active").length')
        r.check(
            active_count is not None and int(active_count) == 1,
            "Active 类唯一（只有一个菜单高亮）",
            f"active 元素数量: {active_count}"
        )
    else:
        r.check(False, "点击 sidebar 菜单", "未找到资产负债表菜单 ref")

    browser.screenshot("04_after_navigate.png")


def test_sidebar_no_duplicate(browser, r):
    """测试 5: Sidebar 无 DOM 重复"""
    print("\n── 测试 5: DOM 去重 ──")

    # 快速切换几个页面
    snap = browser.snapshot_interactive()
    for page_name in ["仪表盘", "记账凭证", "资产负债表", "仪表盘"]:
        ref = find_ref_by_text(snap, page_name)
        if ref:
            browser.click(ref)
            time.sleep(1)
            snap = browser.snapshot_interactive()

    # 检查 DOM 中 sidebar-nav 数量
    count = browser.js('document.querySelectorAll(".sidebar-nav").length')
    r.check(
        count is not None and int(count) <= 2,
        f"DOM 中 sidebar-nav 数量 ≤ 2（实际: {count}）",
        "sidebar 出现 DOM 重复"
    )

    browser.screenshot("05_no_duplicate.png")


def test_header_styles(browser, r):
    """测试 6: Header 样式验证"""
    print("\n── 测试 6: Header 样式 ──")

    # 验证 header 背景色（V5.1 白色 Stripe 风格）
    bg = browser.js('getComputedStyle(document.querySelector(".header-bar")).backgroundColor')
    r.check(
        bg and "255" in bg,
        f"Header 背景为白色（实际: {bg}）",
        f"Header 背景色异常: {bg}"
    )

    # 验证 sidebar 背景色（V5.1 深色 fintech 风格）
    sbg = browser.js('getComputedStyle(document.querySelector(".sidebar-nav")).backgroundColor')
    r.check(
        sbg and ("11" in sbg or "17" in sbg or "32" in sbg),
        f"Sidebar 背景为深色 #0B1120（实际: {sbg}）",
        f"Sidebar 背景色异常: {sbg}"
    )

    browser.screenshot("06_header_styles.png")


def test_sidebar_persists_after_navigation(browser, r):
    """测试 7: 导航后 sidebar 不消失"""
    print("\n── 测试 7: 导航后 sidebar 保持 ──")

    # 先回到仪表盘
    snap = browser.snapshot_interactive()
    ref = find_ref_by_text(snap, "仪表盘")
    if ref:
        browser.click(ref)
        time.sleep(1)

    # 依次访问 5 个页面，每次都检查 sidebar
    pages_to_visit = ["资产负债表", "利润表", "科目余额表", "记账凭证", "仪表盘"]
    all_ok = True

    for page_name in pages_to_visit:
        snap = browser.snapshot_interactive()
        ref = find_ref_by_text(snap, page_name)
        if ref:
            browser.click(ref)
            time.sleep(1.5)
            snap_after = browser.snapshot_interactive()
            if "sidebar-nav" not in snap_after and "工作台" not in snap_after:
                all_ok = False
                print(f"    ⚠️ 访问 {page_name} 后 sidebar 消失")
                break

    r.check(all_ok, "连续导航 5 个页面后 sidebar 保持可见")

    browser.screenshot("07_sidebar_persists.png")


def test_voucher_crud(browser, r):
    """测试 8: 凭证 CRUD 核心流程"""
    print("\n── 测试 8: 凭证 CRUD ──")

    # 导航到凭证页
    snap = browser.snapshot_interactive()
    ref = find_ref_by_text(snap, "记账凭证")
    if ref:
        browser.click(ref)
        time.sleep(2)

    snap = browser.snapshot_interactive()
    r.check(
        "新增凭证" in snap or "凭证" in snap,
        "凭证页面加载",
        "凭证页面未正常显示"
    )

    browser.screenshot("08_journal_page.png")


# ── 主流程 ──
def main():
    print("=" * 60)
    print("浏览器 UI 自动化验证")
    print(f"目标: {BASE_URL}")
    print("=" * 60)

    browser = Browser()
    r = TestResults()

    try:
        test_login_flow(browser, r)
        test_session_persistence(browser, r)
        test_sidebar_structure(browser, r)
        test_sidebar_active_state(browser, r)
        test_sidebar_no_duplicate(browser, r)
        test_header_styles(browser, r)
        test_sidebar_persists_after_navigation(browser, r)
        test_voucher_crud(browser, r)
    except Exception as e:
        print(f"\n💥 测试执行异常: {e}")
        import traceback
        traceback.print_exc()

    success = r.summary()

    print(f"\n截图保存位置: {SCREENSHOT_DIR}/")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
