/**
 * AI 财务系统 v3 — 前端脚本
 *
 * 职责：
 * - sidebar active 状态切换
 * - 暗色主题切换
 * - 手机端底部导航栏
 * - 抽屉式侧边栏
 */

(function() {
    // ── Sidebar + Drawer 控制 ──
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
        document.body.classList.toggle('dark');
        var isDark = document.body.classList.contains('dark');
        document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
        try { localStorage.setItem('theme', isDark ? 'dark' : 'light'); } catch(e) {}
    };

    // ── 手机端导航函数 ──
    window.navigateTo = function(page) {
        document.querySelectorAll('.bottom-nav-item').forEach(function(el) {
            el.classList.toggle('active', el.dataset.page === page);
        });
        // 使用 NiceGUI 内置导航
        Quasar.navigateTo({ path: '/' + page });
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

        // 4. 恢复主题
        try {
            if (localStorage.getItem('theme') === 'dark') {
                document.body.classList.add('dark');
                document.documentElement.setAttribute('data-theme', 'dark');
            }
        } catch(e) {}
    });
})();
