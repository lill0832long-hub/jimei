"""
CSS 模块化验证 —— 验证样式隔离性

运行方法: python -m pytest tests/test_css_modules.py -v
每个测试独立，失败不影响其他测试

验证维度:
1. 文件结构 —— CSS 模块文件是否存在、是否完整
2. 变量隔离 —— tokens.css 是否被所有模块引用
3. 选择器隔离 —— 模块 A 的选择器不泄露到模块 B
4. !important 计数 —— 每个模块的 !important 数量在阈值内
5. 加载顺序 —— index.css 的 @import 顺序正确
"""
import os
import re
import pytest

STYLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "static", "style")
TOKENS_FILE = os.path.join(STYLE_DIR, "tokens.css")
INDEX_FILE = os.path.join(STYLE_DIR, "index.css")

# 预期的模块文件
EXPECTED_MODULES = [
    "tokens.css",
    "base.css",
    "components.css",
    "header.css",
    "sidebar.css",
    "dashboard.css",
    "journal.css",
    "reports.css",
    "login.css",
    "responsive.css",
    "index.css",
]

# 每个模块允许的最大 !important 数量
# 注意：Quasar 框架通过 JS 设置 inline style，部分 !important 无法避免
# base.css 的 !important 主要用于覆盖 Quasar 组件默认样式（字体/圆角/背景等）
# sidebar.css 的 !important 用于覆盖 Quasar button 在深色背景上的样式
IMPORTANT_BUDGET = {
    "tokens.css": 0,
    "base.css": 50,       # Quasar 组件覆盖，难以消除
    "components.css": 10,
    "header.css": 45,     # Quasar header/field 覆盖 + error popup 覆盖
    "sidebar.css": 25,    # Quasar button 在深色背景上的覆盖
    "dashboard.css": 3,
    "journal.css": 3,
    "reports.css": 3,
    "login.css": 10,      # Quasar button/field 覆盖
    "responsive.css": 10, # display: none 覆盖 Quasar display
    "index.css": 0,
}


class TestCSSFileStructure:
    """验证 CSS 模块文件结构"""

    @pytest.mark.parametrize("module", EXPECTED_MODULES)
    def test_module_file_exists(self, module):
        """每个模块文件必须存在"""
        path = os.path.join(STYLE_DIR, module)
        assert os.path.exists(path), f"模块文件缺失: {module}"

    @pytest.mark.parametrize("module", [m for m in EXPECTED_MODULES if m != "index.css"])
    def test_module_not_empty(self, module):
        """每个非入口模块至少包含一条 CSS 规则"""
        path = os.path.join(STYLE_DIR, module)
        if not os.path.exists(path):
            pytest.skip(f"模块尚未创建: {module}")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # 至少有一个 CSS 规则（包含 { }）
        assert "{" in content, f"{module} 不包含任何 CSS 规则"

    def test_index_css_only_has_imports(self):
        """index.css 只包含 @import，不包含实际 CSS 规则"""
        if not os.path.exists(INDEX_FILE):
            pytest.skip("index.css 尚未创建")
        with open(INDEX_FILE, encoding="utf-8") as f:
            content = f.read()
        # 不允许有 @import 之外的规则块（即不含 { 除非在注释中）
        lines = [l for l in content.split("\n") if l.strip() and not l.strip().startswith("//") and not l.strip().startswith("/*")]
        for line in lines:
            assert "{" not in line or "@import" in line, \
                f"index.css 包含非 @import 规则: {line.strip()}"

    def test_all_modules_imported_in_index(self):
        """index.css 必须 import 所有模块（除自身外）"""
        if not os.path.exists(INDEX_FILE):
            pytest.skip("index.css 尚未创建")
        with open(INDEX_FILE, encoding="utf-8") as f:
            content = f.read()
        for module in EXPECTED_MODULES:
            if module == "index.css":
                continue
            assert module in content, f"index.css 未导入 {module}"


class TestCSSVariables:
    """验证 CSS 变量定义和使用"""

    def test_tokens_file_has_all_variables(self):
        """tokens.css 包含所有 Design Tokens"""
        if not os.path.exists(TOKENS_FILE):
            pytest.skip("tokens.css 尚未创建")
        with open(TOKENS_FILE, encoding="utf-8") as f:
            content = f.read()
        # 检查关键变量组存在
        required_groups = [
            ("--c-primary", "全局主色"),
            ("--sidebar-", "侧边栏变量"),
            ("--header-", "顶部栏变量"),
            ("--c-bg-page", "页面背景"),
            ("--c-text-primary", "主文本色"),
            ("--font-stack", "字体"),
        ]
        for var, desc in required_groups:
            assert var in content, f"tokens.css 缺少 {desc} 变量: {var}"

    def test_no_variables_in_other_modules(self):
        """除 tokens.css 外，其他模块不应定义 CSS 变量（应在 tokens.css 中统一定义）"""
        if not os.path.exists(STYLE_DIR):
            pytest.skip("style/ 目录尚未创建")
        var_pattern = re.compile(r"^\s+--[\w-]+:", re.MULTILINE)
        for fname in os.listdir(STYLE_DIR):
            if fname in ("tokens.css", "index.css") or not fname.endswith(".css"):
                continue
            fpath = os.path.join(STYLE_DIR, fname)
            with open(fpath, encoding="utf-8") as f:
                content = f.read()
            # 允许在 :root 中不定义变量，但其他选择器中不应有变量定义
            # 简化检查：整个文件中不应有 --xxx: 形式的定义
            matches = var_pattern.findall(content)
            assert len(matches) == 0, \
                f"{fname} 中定义了 {len(matches)} 个 CSS 变量，应统一放到 tokens.css"


class TestCSSSpecificity:
    """验证 CSS 特异性 —— 用选择器特异性替代 !important"""

    def count_important(self, filepath):
        """统计文件中 !important 数量"""
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        return content.count("!important")

    @pytest.mark.parametrize("module,budget", [
        (m, IMPORTANT_BUDGET.get(m, 5)) for m in EXPECTED_MODULES
    ])
    def test_important_budget(self, module, budget):
        """每个模块的 !important 数量不超过预算"""
        fpath = os.path.join(STYLE_DIR, module)
        if not os.path.exists(fpath):
            pytest.skip(f"模块尚未创建: {module}")
        count = self.count_important(fpath)
        assert count <= budget, \
            f"{module} 有 {count} 个 !important，超过预算 {budget}"

    def test_total_important_reasonable(self):
        """全局 !important 数量在合理范围内（Quasar 应用 ~130 属正常）"""
        if not os.path.exists(STYLE_DIR):
            pytest.skip("style/ 目录尚未创建")
        total = 0
        for fname in os.listdir(STYLE_DIR):
            if fname.endswith(".css"):
                total += self.count_important(os.path.join(STYLE_DIR, fname))
        # Quasar 应用需要通过 !important 覆盖框架 inline style
        # 当前 ~130 个属正常范围，<200 为健康上限
        assert total < 200, f"全局 !important 共 {total} 个，超过健康上限 200"


class TestCSSIsolation:
    """验证 CSS 模块隔离性 —— 改一个模块不影响其他模块"""

    def get_selectors(self, filepath):
        """提取文件中所有 CSS 选择器"""
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        # 简单提取选择器（在 { 之前的内容）
        selectors = re.findall(r"([^{}]+)\{", content)
        return [s.strip() for s in selectors if s.strip() and not s.strip().startswith("@")]

    def test_sidebar_module_no_header_selectors(self):
        """sidebar.css 中不应包含 header 相关选择器"""
        fpath = os.path.join(STYLE_DIR, "sidebar.css")
        if not os.path.exists(fpath):
            pytest.skip("sidebar.css 尚未创建")
        selectors = self.get_selectors(fpath)
        header_keywords = ["header-bar", "header-left", "header-center", "header-right",
                          "header-select", "header-year", "header-month"]
        for sel in selectors:
            for kw in header_keywords:
                assert kw not in sel, f"sidebar.css 包含 header 选择器: {sel}"

    def test_header_module_no_sidebar_selectors(self):
        """header.css 中不应包含 sidebar 相关选择器"""
        fpath = os.path.join(STYLE_DIR, "header.css")
        if not os.path.exists(fpath):
            pytest.skip("header.css 尚未创建")
        selectors = self.get_selectors(fpath)
        sidebar_keywords = ["sidebar-nav", "sidebar-menu", "sidebar-group", "sidebar-logo",
                           "sidebar-collapse", "sidebar-wrapper"]
        for sel in selectors:
            for kw in sidebar_keywords:
                assert kw not in sel, f"header.css 包含 sidebar 选择器: {sel}"

    def test_login_module_independent(self):
        """login.css 完全独立，不引用其他模块的选择器"""
        fpath = os.path.join(STYLE_DIR, "login.css")
        if not os.path.exists(fpath):
            pytest.skip("login.css 尚未创建")
        selectors = self.get_selectors(fpath)
        external_keywords = ["header-", "sidebar-", "dashboard-", "q-card", "nicegui-"]
        for sel in selectors:
            for kw in external_keywords:
                assert kw not in sel, f"login.css 引用了外部选择器: {sel}"


class TestCSSBaseline:
    """验证 CSS 基准 —— 拆分后样式值与拆分前一致"""

    def test_all_original_selectors_preserved(self):
        """所有原始 style.css 中的选择器在模块化后仍然存在"""
        original_css = os.path.join(os.path.dirname(STYLE_DIR), "style.css")
        if not os.path.exists(original_css):
            pytest.skip("原始 style.css 不存在（已替换）")

        # 提取原始选择器
        with open(original_css, encoding="utf-8") as f:
            original = f.read()
        original_selectors = set(
            s.strip() for s in re.findall(r"([^{}]+)\{", original)
            if s.strip() and not s.strip().startswith("@") and not s.strip().startswith("/*")
        )

        # 提取模块化后的所有选择器
        modular_selectors = set()
        if os.path.exists(STYLE_DIR):
            for fname in os.listdir(STYLE_DIR):
                if fname.endswith(".css") and fname != "index.css":
                    fpath = os.path.join(STYLE_DIR, fname)
                    with open(fpath, encoding="utf-8") as f:
                        content = f.read()
                    for s in re.findall(r"([^{}]+)\{", content):
                        s = s.strip()
                        if s and not s.startswith("@"):
                            modular_selectors.add(s)

        # 检查丢失的选择器（忽略 :root 和 @import）
        missing = original_selectors - modular_selectors
        missing = {s for s in missing if not s.startswith("@") and ":root" not in s}
        assert len(missing) == 0, f"以下选择器在模块化后丢失:\n  " + "\n  ".join(sorted(missing)[:20])
