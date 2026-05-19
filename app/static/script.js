/**
 * AI 财务系统 V5.1 — 前端脚本
 *
 * 职责：
 * - sidebar active 状态切换（纯视觉，不拦截点击）
 * - 暗色主题切换
 * - 手机端底部导航栏
 * - 抽屉式侧边栏
 * - 导航统一：所有导航通过 window.location.href 触发页面重载
 *   Python navigate() 是唯一的导航逻辑源
 */

(function() {
    // ── Sidebar active 状态 ──
    window.sidebarCtrl = {
        setActiveItem: function(pageKey) {
            if (!pageKey) return;
            document.querySelectorAll('.sidebar-menu-item').forEach(function(el) {
                el.classList.remove('sidebar-menu-active');
            });
            var activeEl = document.querySelector('.sidebar-menu-item[data-page="' + pageKey + '"]');
            if (activeEl) activeEl.classList.add('sidebar-menu-active');
        },
        openDrawer: function() {
            var overlay = document.querySelector('.drawer-overlay');
            var drawer = document.querySelector('.drawer-sidebar');
            if (overlay) overlay.classList.add('active');
            if (drawer) drawer.classList.add('open');
            document.body.style.overflow = 'hidden';
        },
        closeDrawer: function() {
            var overlay = document.querySelector('.drawer-overlay');
            var drawer = document.querySelector('.drawer-sidebar');
            if (overlay) overlay.classList.remove('active');
            if (drawer) drawer.classList.remove('open');
            document.body.style.overflow = '';
        },
        toggleDrawer: function() {
            var drawer = document.querySelector('.drawer-sidebar');
            if (drawer && drawer.classList.contains('open')) {
                window.sidebarCtrl.closeDrawer();
            } else {
                window.sidebarCtrl.openDrawer();
            }
        }
    };

    // ── 暗色主题 ──
    window.toggleDarkTheme = function() {
        var isDark = document.body.getAttribute('data-theme') !== 'dark';
        document.body.setAttribute('data-theme', isDark ? 'dark' : 'light');
        try { localStorage.setItem('theme', isDark ? 'dark' : 'light'); } catch(e) {}
    };

    // ── 手机端导航函数 ──
    // 统一使用 window.location.href 触发页面重载
    // Python navigate() 是唯一导航逻辑源，JS 只负责触发页面跳转
    window.navigateTo = function(page) {
        document.querySelectorAll('.bottom-nav-item').forEach(function(el) {
            el.classList.toggle('active', el.dataset.page === page);
        });
        // 关闭抽屉（如果打开）
        window.sidebarCtrl.closeDrawer();
        // 触发页面跳转（全量重载，确保 Python index() 重新执行）
        window.location.href = '/' + page;
    };

    // ── DOMContentLoaded 初始化 ──
    document.addEventListener('DOMContentLoaded', function() {
        // 1. 初始化底部导航栏
        if (!document.getElementById('bottomNav')) {
            var nav = document.createElement('div');
            nav.id = 'bottomNav';
            nav.className = 'bottom-nav';
            nav.innerHTML =
                '<div class="bottom-nav-item active" data-page="dashboard" onclick="navigateTo(\'dashboard\')">' +
                    '<span class="q-icon">🏠</span><span>首页</span>' +
                '</div>' +
                '<div class="bottom-nav-item" data-page="journal" onclick="navigateTo(\'journal\')">' +
                    '<span class="q-icon">📝</span><span>凭证</span>' +
                '</div>' +
                '<div class="bottom-nav-item" data-page="reports" onclick="navigateTo(\'reports\')">' +
                    '<span class="q-icon">📊</span><span>报表</span>' +
                '</div>' +
                '<div class="bottom-nav-item" data-page="ai_assistant" onclick="navigateTo(\'ai_assistant\')">' +
                    '<span class="q-icon">🤖</span><span>AI</span>' +
                '</div>' +
                '<div class="bottom-nav-item" data-page="settings" onclick="navigateTo(\'settings\')">' +
                    '<span class="q-icon">⚙️</span><span>设置</span>' +
                '</div>';
            document.body.appendChild(nav);
        }

        // 2. 初始化抽屉
        if (!document.getElementById('drawerSidebar')) {
            var overlay = document.createElement('div');
            overlay.className = 'drawer-overlay';
            overlay.addEventListener('click', function() { window.sidebarCtrl.closeDrawer(); });
            document.body.appendChild(overlay);

            var drawer = document.createElement('div');
            drawer.id = 'drawerSidebar';
            drawer.className = 'drawer-sidebar';
            drawer.innerHTML =
                '<div style="padding:16px;display:flex;align-items:center;gap:8px;border-bottom:1px solid rgba(255,255,255,0.1)">' +
                    '<span style="font-size:24px;color:#fff">🏦</span>' +
                    '<span style="font-size:18px;font-weight:700;color:#fff">AI财务系统</span>' +
                '</div>' +
                '<div id="drawerMenuContent" style="padding:8px"></div>';
            document.body.appendChild(drawer);
        }

        // 3. 同步 sidebar 菜单到抽屉
        var sidebar = document.querySelector('.sidebar-nav');
        var drawerMenu = document.getElementById('drawerMenuContent');
        if (sidebar && drawerMenu && drawerMenu.children.length === 0) {
            var items = sidebar.querySelectorAll('.sidebar-menu-item, .sidebar-group-header, .sidebar-bottom-item, .sidebar-collapse-row');
            items.forEach(function(item) {
                var clone = item.cloneNode(true);
                clone.style.display = '';
                clone.style.width = '100%';
                drawerMenu.appendChild(clone);
            });
        }

        // 3b. 抽屉菜单点击 → 使用 window.location.href 导航（克隆元素无 Python handler）
        if (drawerMenu) {
            drawerMenu.addEventListener('click', function(e) {
                var btn = e.target.closest('.sidebar-menu-item');
                if (!btn) return;
                var page = btn.dataset.page;
                if (!page) return;
                window.location.href = '/' + page;
            });
        }

        // 4. 恢复主题
        try {
            if (localStorage.getItem('theme') === 'dark') {
                document.body.setAttribute('data-theme', 'dark');
            }
        } catch(e) {}

        // 5. 定期清理重复的 sidebar-nav（NiceGUI clear() 不删 DOM 的 workaround）
        setInterval(function() {
            var navs = document.querySelectorAll('.sidebar-nav');
            if (navs.length > 1) {
                var maxIdx = 0, maxCount = 0;
                for (var i = 0; i < navs.length; i++) {
                    if (navs[i].children.length > maxCount) {
                        maxCount = navs[i].children.length;
                        maxIdx = i;
                    }
                }
                for (var i = 0; i < navs.length; i++) {
                    if (i !== maxIdx && navs[i].parentNode) {
                        navs[i].parentNode.removeChild(navs[i]);
                    }
                }
            }
        }, 500);
    });
})();
