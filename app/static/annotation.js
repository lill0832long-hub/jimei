/**
 * 页面标注工具 — 用户在页面上圈点写备注，保存为 JSON 供 AI 读取
 *
 * 功能：
 * 1. 点击"📝 标注"按钮进入标注模式
 * 2. 在页面上画矩形圈出问题区域（红色半透明）
 * 3. 点击任意位置添加文字备注气泡
 * 4. 右键点击元素标记"删除"/"修改"建议
 * 5. 保存 → POST 到 /api/v1/annotations/{page}
 * 6. 加载时自动读取已有标注并渲染
 */
(function () {
    "use strict";

    // ── 状态 ──
    var MODE_OFF     = 0;   // 标注模式关闭
    var MODE_DRAW    = 1;   // 画矩形圈选
    var MODE_NOTE    = 2;   // 点击添加备注
    var MODE_GONE    = 3;   // 右键标记删除

    var _mode     = MODE_OFF;
    var _drawing  = false;
    var _drawEl   = null;   // 当前正在画的矩形
    var _drawSX   = 0;      // 起始 X
    var _drawSY   = 0;      // 起始 Y
    var _annots   = [];     // 标注列表
    var _page     = "unknown";
    var _overlay  = null;   // Canvas overlay
    var _toolbar  = null;   // 工具栏
    var _ctx      = null;   // Canvas 2D context

    // ── 获取当前页面名 ──
    function _getPage() {
        var p = window.location.pathname.replace(/^\/+/, "") || "dashboard";
        return p.split("?")[0];
    }

    // ── 创建工具栏 ──
    function _createToolbar() {
        var bar = document.createElement("div");
        bar.id = "annotate-toolbar";
        bar.innerHTML =
            '<div class="atb-inner">' +
                '<span class="atb-title">📝 标注模式</span>' +
                <button class="atb-btn atb-btn-draw active" onclick="window._annot.setMode(1)">⬚ 圈选</button>' +
                '<button class="atb-btn atb-btn-note" onclick="window._annot.setMode(2)">💬 备注</button>' +
                '<button class="atb-btn atb-btn-gone" onclick="window._annot.setMode(3)">✕ 删除</button>' +
                '<span class="atb-sep">|</span>' +
                '<button class="atb-btn atb-btn-save" onclick="window._annot.save()">💾 保存</button>' +
                '<button class="atb-btn atb-btn-clear" onclick="window._annot.clearAll()">🗑 清空</button>' +
                '<button class="atb-btn atb-btn-close" onclick="window._annot.toggle(false)">✖ 退出</button>' +
            '</div>';
        document.body.appendChild(bar);
        return bar;
    }

    // ── 创建 Canvas 覆盖层 ──
    function _createOverlay() {
        var c = document.createElement("canvas");
        c.id = "annotate-canvas";
        c.style.cssText =
            "position:fixed;top:0;left:0;width:100%;height:100%;" +
            "z-index:99999;pointer-events:auto;display:block;";
        document.body.appendChild(c);
        _ctx = c.getContext("2d");
        _resizeCanvas(c);
        window.addEventListener("resize", function () { _resizeCanvas(c); });
        return c;
    }

    function _resizeCanvas(c) {
        c.width  = window.innerWidth;
        c.height = window.innerHeight;
        _redraw();
    }

    // ── 绘制所有标注 ──
    function _redraw() {
        if (!_ctx) return;
        _ctx.clearRect(0, 0, _overlay.width, _overlay.height);
        for (var i = 0; i < _annots.length; i++) {
            var a = _annots[i];
            if (a.type === "rect") {
                // 半透明填充
                _ctx.fillStyle = "rgba(239,68,68,0.12)";
                _ctx.fillRect(a.x, a.y, a.w, a.h);
                // 红色边框
                _ctx.strokeStyle = "rgba(239,68,68,0.7)";
                _ctx.lineWidth = 2;
                _ctx.setLineDash([4, 2]);
                _ctx.strokeRect(a.x, a.y, a.w, a.h);
                _ctx.setLineDash([]);
                // 标签
                if (a.label) {
                    _ctx.fillStyle = "rgba(239,68,68,0.9)";
                    _ctx.font = "12px Inter, sans-serif";
                    var tw = _ctx.measureText(a.label).width;
                    _ctx.fillStyle = "rgba(239,68,68,0.85)";
                    _ctx.fillRect(a.x, a.y - 18, tw + 10, 18);
                    _ctx.fillStyle = "#fff";
                    _ctx.fillText(a.label, a.x + 5, a.y - 4);
                }
            } else if (a.type === "note") {
                // 备注气泡
                _ctx.fillStyle = "#f59e0b";
                _ctx.beginPath();
                _ctx.arc(a.x, a.y, 14, 0, Math.PI * 2);
                _ctx.fill();
                _ctx.fillStyle = "#fff";
                _ctx.font = "bold 12px Inter, sans-serif";
                _ctx.textAlign = "center";
                _ctx.fillText("!", a.x, a.y + 4);
                _ctx.textAlign = "left";
                // 备注文字
                if (a.text) {
                    _ctx.fillStyle = "rgba(0,0,0,0.75)";
                    _ctx.font = "12px Inter, sans-serif";
                    var lines = a.text.split("\n");
                    var maxW = 0;
                    for (var li = 0; li < lines.length; li++) {
                        var lw = _ctx.measureText(lines[li]).width;
                        if (lw > maxW) maxW = lw;
                    }
                    var bh = lines.length * 16 + 8;
                    var bx = a.x + 18;
                    var by = a.y - 10;
                    _ctx.fillStyle = "rgba(255,255,255,0.95)";
                    _ctx.fillRect(bx, by, maxW + 12, bh);
                    _ctx.strokeStyle = "#d97706";
                    _ctx.lineWidth = 1;
                    _ctx.strokeRect(bx, by, maxW + 12, bh);
                    _ctx.fillStyle = "#1e293b";
                    for (var li2 = 0; li2 < lines.length; li2++) {
                        _ctx.fillText(lines[li2], bx + 6, by + 14 + li2 * 16);
                    }
                }
            } else if (a.type === "gone") {
                // 删除标记 — 红色 X
                _ctx.strokeStyle = "rgba(239,68,68,0.8)";
                _ctx.lineWidth = 3;
                var s = 12;
                _ctx.beginPath();
                _ctx.moveTo(a.x - s, a.y - s);
                _ctx.lineTo(a.x + s, a.y + s);
                _ctx.moveTo(a.x + s, a.y - s);
                _ctx.lineTo(a.x - s, a.y + s);
                _ctx.stroke();
                // 删除线
                if (a.targetText) {
                    _ctx.fillStyle = "rgba(239,68,68,0.7)";
                    _ctx.font = "11px Inter, sans-serif";
                    _ctx.fillText("删除: " + a.targetText.substring(0, 30), a.x + 16, a.y + 4);
                }
            }
        }
    }

    // ── 事件处理 ──
    function _onMouseDown(e) {
        if (_mode === MODE_OFF) return;
        if (_mode === MODE_DRAW) {
            _drawing = true;
            _drawSX = e.clientX;
            _drawSY = e.clientY;
        } else if (_mode === MODE_NOTE) {
            _promptNote(e.clientX, e.clientY);
        } else if (_mode === MODE_GONE) {
            _markGone(e);
        }
    }

    function _onMouseMove(e) {
        if (!_drawing || _mode !== MODE_DRAW) return;
        // 实时预览矩形
        _redraw();
        var x = Math.min(_drawSX, e.clientX);
        var y = Math.min(_drawSY, e.clientY);
        var w = Math.abs(e.clientX - _drawSX);
        var h = Math.abs(e.clientY - _drawSY);
        _ctx.fillStyle = "rgba(239,68,68,0.15)";
        _ctx.fillRect(x, y, w, h);
        _ctx.strokeStyle = "rgba(239,68,68,0.7)";
        _ctx.lineWidth = 2;
        _ctx.setLineDash([4, 2]);
        _ctx.strokeRect(x, y, w, h);
        _ctx.setLineDash([]);
    }

    function _onMouseUp(e) {
        if (!_drawing || _mode !== MODE_DRAW) return;
        _drawing = false;
        var x = Math.min(_drawSX, e.clientX);
        var y = Math.min(_drawSY, e.clientY);
        var w = Math.abs(e.clientX - _drawSX);
        var h = Math.abs(e.clientY - _drawSY);
        if (w < 5 || h < 5) return; // 太小忽略
        var label = prompt("圈选标签（可选，如\"按钮太大\"）：", "");
        _annots.push({ type: "rect", x: x, y: y, w: w, h: h, label: label || "" });
        _redraw();
    }

    function _promptNote(x, y) {
        var text = prompt("输入备注（如\"颜色不对，改成 #494fdf\"）：", "");
        if (text !== null && text.trim()) {
            _annots.push({ type: "note", x: x, y: y, text: text.trim() });
            _redraw();
        }
    }

    function _markGone(e) {
        var el = document.elementFromPoint(e.clientX, e.clientY);
        var txt = "";
        if (el) {
            txt = (el.textContent || "").trim().substring(0, 40);
            // 高亮目标元素
            el.style.outline = "2px dashed rgba(239,68,68,0.7)";
            setTimeout(function () { el.style.outline = ""; }, 2000);
        }
        _annots.push({ type: "gone", x: e.clientX, y: e.clientY, targetText: txt });
        _redraw();
    }

    // ── 公共 API ──
    window._annot = {
        toggle: function (on) {
            if (on === undefined) {
                _mode = (_mode === MODE_OFF) ? MODE_DRAW : MODE_OFF;
            } else {
                _mode = on ? MODE_DRAW : MODE_OFF;
            }
            if (_mode !== MODE_OFF) {
                if (!_overlay) _overlay = _createOverlay();
                if (!_toolbar) _toolbar = _createToolbar();
                _overlay.style.display = "block";
                _toolbar.style.display = "block";
                _page = _getPage();
                this.load();
            } else {
                if (_overlay) _overlay.style.display = "none";
                if (_toolbar) _toolbar.style.display = "none";
            }
            this._updateBtns();
        },

        setMode: function (m) {
            _mode = m;
            this._updateBtns();
        },

        _updateBtns: function () {
            if (!_toolbar) return;
            var btns = _toolbar.querySelectorAll(".atb-btn-draw, .atb-btn-note, .atb-btn-gone");
            btns.forEach(function (b) { b.classList.remove("active"); });
            if (_mode === MODE_DRAW) _toolbar.querySelector(".atb-btn-draw").classList.add("active");
            if (_mode === MODE_NOTE) _toolbar.querySelector(".atb-btn-note").classList.add("active");
            if (_mode === MODE_GONE) _toolbar.querySelector(".atb-btn-gone").classList.add("active");
        },

        save: function () {
            if (_annots.length === 0) {
                alert("还没有任何标注");
                return;
            }
            var data = {
                page: _page,
                url: window.location.href,
                savedAt: new Date().toISOString(),
                annotations: _annots
            };
            fetch("/api/v1/annotations/" + encodeURIComponent(_page), {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(data)
            }).then(function (r) { return r.json(); }).then(function (d) {
                alert("✅ 已保存 " + _annots.length + " 条标注\n\n我可以直接读取 .claude/annotations/" + _page + ".json");
            }).catch(function (e) {
                alert("保存失败: " + e);
            });
        },

        load: function () {
            fetch("/api/v1/annotations/" + encodeURIComponent(_page))
                .then(function (r) { return r.json(); })
                .then(function (d) {
                    if (d.success && d.data && d.data.annotations) {
                        _annots = d.data.annotations;
                        _redraw();
                    }
                }).catch(function () {});
        },

        clearAll: function () {
            if (!confirm("清空所有标注？")) return;
            _annots = [];
            _redraw();
        }
    };

    // ── 绑定事件 ──
    document.addEventListener("mousedown", function (e) {
        // 不拦截工具栏点击
        if (e.target.closest("#annotate-toolbar")) return;
        _onMouseDown(e);
    });
    document.addEventListener("mousemove", _onMouseMove);
    document.addEventListener("mouseup", _onMouseUp);
    // 右键在标注模式下用于标记删除
    document.addEventListener("contextmenu", function (e) {
        if (_mode === MODE_GONE) {
            e.preventDefault();
            _markGone(e);
        }
    });

    // ── 注入工具栏样式 ──
    var style = document.createElement("style");
    style.textContent =
        "#annotate-toolbar {" +
            "position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%); " +
            "z-index: 100000; background: #1e293b; border-radius: 12px; " +
            "box-shadow: 0 8px 32px rgba(0,0,0,0.3); padding: 8px 16px;" +
            "font-family: Inter, sans-serif; font-size: 13px;" +
            "display: none;" +
        "}" +
        "#annotate-toolbar .atb-inner {" +
            "display: flex; align-items: center; gap: 8px;" +
        "}" +
        "#annotate-toolbar .atb-title {" +
            "color: #f59e0b; font-weight: 700; margin-right: 4px;" +
        "}" +
        "#annotate-toolbar .atb-sep {" +
            "color: #475569;" +
        "}" +
        "#annotate-toolbar .atb-btn {" +
            "background: transparent; border: 1px solid transparent; " +
            "color: #cbd5e1; cursor: pointer; padding: 4px 10px; " +
            "border-radius: 6px; font-size: 13px; transition: all 0.15s;" +
        "}" +
        "#annotate-toolbar .atb-btn:hover {" +
            "background: rgba(255,255,255,0.1); color: #fff;" +
        "}" +
        "#annotate-toolbar .atb-btn.active {" +
            "background: rgba(99,102,241,0.3); color: #a5b4fc; border-color: rgba(99,102,241,0.4);" +
        "}" +
        "#annotate-toolbar .atb-btn-save {" +
            "background: rgba(34,197,94,0.2); color: #4ade80;" +
        "}" +
        "#annotate-toolbar .atb-btn-save:hover {" +
            "background: rgba(34,197,94,0.35);" +
        "}" +
        "#annotate-toolbar .atb-btn-clear {" +
            "background: rgba(239,68,68,0.15); color: #f87171;" +
        "}" +
        "#annotate-toolbar .atb-btn-close {" +
            "background: rgba(255,255,255,0.08); color: #94a3b8;" +
        "}" +
        "body.annotate-mode .main-content-area {" +
            "cursor: crosshair;" +
        "}";
    document.head.appendChild(style);

    console.log("[annotate] 标注工具已加载。调用 window._annot.toggle(true) 开启。");
})();
