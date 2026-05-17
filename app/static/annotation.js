/**
 * 页面标注工具 v3 — 用户在页面上圈点写备注，保存为 JSON 供 AI 读取
 * 不用 prompt/alert/confirm，全部用自定义 HTML 弹窗
 */
(function () {
    "use strict";

    var MODE_OFF = 0, MODE_DRAW = 1, MODE_NOTE = 2, MODE_GONE = 3;
    var _mode = MODE_OFF, _drawing = false, _drawSX = 0, _drawSY = 0;
    var _annots = [], _page = "unknown";
    var _canvas = null, _toolbar = null, _ctx = null;
    var _modal = null; // 自定义弹窗

    function _getPage() {
        return (window.location.pathname.replace(/^\/+/, "") || "dashboard").split("?")[0];
    }

    // ── 自定义弹窗（替代 prompt/alert/confirm）──
    function _showModal(opts) {
        // opts: { title, placeholder, defaultValue, onOk, onCancel, isConfirm }
        if (_modal) _modal.remove();
        var wrap = document.createElement("div");
        wrap.id = "atb-modal";
        wrap.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;z-index:200000;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.5);";

        var box = document.createElement("div");
        box.style.cssText = "background:#1e293b;border-radius:12px;padding:24px;min-width:320px;max-width:90%;box-shadow:0 16px 48px rgba(0,0,0,0.4);font-family:Inter,sans-serif;";

        var title = document.createElement("div");
        title.textContent = opts.title || "";
        title.style.cssText = "color:#e2e8f0;font-size:14px;font-weight:600;margin-bottom:12px;";
        box.appendChild(title);

        var input = null;
        if (!opts.isConfirm) {
            input = document.createElement("input");
            input.type = "text";
            input.value = opts.defaultValue || "";
            input.placeholder = opts.placeholder || "";
            input.style.cssText = "width:100%;padding:8px 12px;border:1px solid #334155;border-radius:6px;background:#0f172a;color:#e2e8f0;font-size:13px;outline:none;box-sizing:border-box;";
            input.addEventListener("keydown", function (e) { if (e.key === "Enter") okBtn.click(); });
            box.appendChild(input);
        }

        var btnRow = document.createElement("div");
        btnRow.style.cssText = "display:flex;justify-content:flex-end;gap:8px;margin-top:16px;";

        var cancelBtn = document.createElement("button");
        cancelBtn.textContent = opts.isConfirm ? "取消" : "取消";
        cancelBtn.style.cssText = "padding:6px 16px;border:1px solid #334155;border-radius:6px;background:transparent;color:#94a3b8;cursor:pointer;font-size:13px;";
        cancelBtn.addEventListener("click", function () { wrap.remove(); _modal = null; if (opts.onCancel) opts.onCancel(); });

        var okBtn = document.createElement("button");
        okBtn.textContent = "确定";
        okBtn.style.cssText = "padding:6px 16px;border:none;border-radius:6px;background:#494fdf;color:#fff;cursor:pointer;font-size:13px;font-weight:600;";
        okBtn.addEventListener("click", function () {
            wrap.remove();
            _modal = null;
            var val = input ? input.value : true;
            if (opts.onOk) opts.onOk(val);
        });

        btnRow.appendChild(cancelBtn);
        btnRow.appendChild(okBtn);
        box.appendChild(btnRow);
        wrap.appendChild(box);
        document.body.appendChild(wrap);
        _modal = wrap;
        if (input) input.focus();
    }

    // ── 工具栏 ──
    function _createToolbar() {
        var bar = document.createElement("div");
        bar.id = "annotate-toolbar";
        bar.innerHTML = '<div class="atb-inner">' +
            '<span class="atb-title">&#x1F4DD; &#27010;&#27880;&#27169;&#24335;</span>' +
            '<button class="atb-btn atb-btn-draw active" id="atb-draw">&#x2B1C; &#22280;&#36873;</button>' +
            '<button class="atb-btn atb-btn-note" id="atb-note">&#x1F4AC; &#22791;&#27880;</button>' +
            '<button class="atb-btn atb-btn-gone" id="atb-gone">&#x2715; &#21024;&#38500;</button>' +
            '<span class="atb-sep">|</span>' +
            '<button class="atb-btn atb-btn-save" id="atb-save">&#x1F4BE; &#20445;&#23384;</button>' +
            '<button class="atb-btn atb-btn-clear" id="atb-clear">&#x1F5D1; &#28165;&#31354;</button>' +
            '<button class="atb-btn atb-btn-close" id="atb-close">&#x2716; &#36864;&#20986;</button>' +
            '</div>';
        document.body.appendChild(bar);

        bar.querySelector("#atb-draw").addEventListener("click", function (e) { e.stopPropagation(); _mode = MODE_DRAW; _updateBtns(); });
        bar.querySelector("#atb-note").addEventListener("click", function (e) { e.stopPropagation(); _mode = MODE_NOTE; _updateBtns(); });
        bar.querySelector("#atb-gone").addEventListener("click", function (e) { e.stopPropagation(); _mode = MODE_GONE; _updateBtns(); });
        bar.querySelector("#atb-save").addEventListener("click", function (e) { e.stopPropagation(); _doSave(); });
        bar.querySelector("#atb-clear").addEventListener("click", function (e) { e.stopPropagation(); _doClear(); });
        bar.querySelector("#atb-close").addEventListener("click", function (e) { e.stopPropagation(); _doToggle(false); });
        return bar;
    }

    function _updateBtns() {
        if (!_toolbar) return;
        var all = _toolbar.querySelectorAll(".atb-btn-draw,.atb-btn-note,.atb-btn-gone");
        for (var i = 0; i < all.length; i++) all[i].classList.remove("active");
        if (_mode === MODE_DRAW) _toolbar.querySelector(".atb-btn-draw").classList.add("active");
        if (_mode === MODE_NOTE) _toolbar.querySelector(".atb-btn-note").classList.add("active");
        if (_mode === MODE_GONE) _toolbar.querySelector(".atb-btn-gone").classList.add("active");
    }

    // ── Canvas ──
    function _createOverlay() {
        var c = document.createElement("canvas");
        c.id = "annotate-canvas";
        c.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;z-index:99999;pointer-events:auto;display:block;";
        document.body.appendChild(c);
        _ctx = c.getContext("2d");
        _canvas = c;
        _sizeCanvas();
        window.addEventListener("resize", _sizeCanvas);
        return c;
    }

    function _sizeCanvas() {
        if (!_canvas) return;
        _canvas.width = window.innerWidth;
        _canvas.height = window.innerHeight;
        _redraw();
    }

    // ── 绘制 ──
    function _redraw() {
        if (!_ctx || !_canvas) return;
        _ctx.clearRect(0, 0, _canvas.width, _canvas.height);
        for (var i = 0; i < _annots.length; i++) {
            var a = _annots[i];
            if (a.type === "rect") {
                _ctx.fillStyle = "rgba(239,68,68,0.12)";
                _ctx.fillRect(a.x, a.y, a.w, a.h);
                _ctx.strokeStyle = "rgba(239,68,68,0.7)";
                _ctx.lineWidth = 2;
                _ctx.setLineDash([4, 2]);
                _ctx.strokeRect(a.x, a.y, a.w, a.h);
                _ctx.setLineDash([]);
                if (a.label) {
                    _ctx.font = "12px Inter,sans-serif";
                    var tw = _ctx.measureText(a.label).width;
                    _ctx.fillStyle = "rgba(239,68,68,0.85)";
                    _ctx.fillRect(a.x, a.y - 18, tw + 10, 18);
                    _ctx.fillStyle = "#fff";
                    _ctx.fillText(a.label, a.x + 5, a.y - 4);
                }
            } else if (a.type === "note") {
                _ctx.fillStyle = "#f59e0b";
                _ctx.beginPath();
                _ctx.arc(a.x, a.y, 14, 0, Math.PI * 2);
                _ctx.fill();
                _ctx.fillStyle = "#fff";
                _ctx.font = "bold 12px Inter,sans-serif";
                _ctx.textAlign = "center";
                _ctx.fillText("!", a.x, a.y + 4);
                _ctx.textAlign = "left";
                if (a.text) {
                    _ctx.font = "12px Inter,sans-serif";
                    var lines = a.text.split("\n");
                    var maxW = 0;
                    for (var li = 0; li < lines.length; li++) {
                        var lw = _ctx.measureText(lines[li]).width;
                        if (lw > maxW) maxW = lw;
                    }
                    var bh = lines.length * 16 + 8;
                    var bx = a.x + 18, by = a.y - 10;
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
                _ctx.strokeStyle = "rgba(239,68,68,0.8)";
                _ctx.lineWidth = 3;
                var s = 12;
                _ctx.beginPath();
                _ctx.moveTo(a.x - s, a.y - s);
                _ctx.lineTo(a.x + s, a.y + s);
                _ctx.moveTo(a.x + s, a.y - s);
                _ctx.lineTo(a.x - s, a.y + s);
                _ctx.stroke();
                if (a.targetText) {
                    _ctx.fillStyle = "rgba(239,68,68,0.7)";
                    _ctx.font = "11px Inter,sans-serif";
                    _ctx.fillText("删除: " + a.targetText.substring(0, 30), a.x + 16, a.y + 4);
                }
            }
        }
    }

    // ── 鼠标事件 ──
    function _onMouseDown(e) {
        if (_mode === MODE_OFF) return;
        if (e.target.closest("#annotate-toolbar") || e.target.closest("#atb-modal")) return;
        if (_mode === MODE_DRAW) {
            _drawing = true;
            _drawSX = e.clientX;
            _drawSY = e.clientY;
        } else if (_mode === MODE_NOTE) {
            _doNote(e.clientX, e.clientY);
        } else if (_mode === MODE_GONE) {
            _doGone(e);
        }
    }

    function _onMouseMove(e) {
        if (!_drawing || _mode !== MODE_DRAW) return;
        _redraw();
        var x = Math.min(_drawSX, e.clientX), y = Math.min(_drawSY, e.clientY);
        var w = Math.abs(e.clientX - _drawSX), h = Math.abs(e.clientY - _drawSY);
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
        var x = Math.min(_drawSX, e.clientX), y = Math.min(_drawSY, e.clientY);
        var w = Math.abs(e.clientX - _drawSX), h = Math.abs(e.clientY - _drawSY);
        if (w < 5 || h < 5) return;
        _showModal({
            title: "圈选标签（可选，如“按钮太大”）",
            placeholder: "输入标签文字...",
            onOk: function (val) {
                _annots.push({ type: "rect", x: x, y: y, w: w, h: h, label: val || "" });
                _redraw();
            }
        });
    }

    function _onContextMenu(e) {
        if (_mode === MODE_GONE) { e.preventDefault(); _doGone(e); }
    }

    function _doNote(x, y) {
        _showModal({
            title: "输入备注（如“颜色不对，改成 #494fdf”）",
            placeholder: "输入备注内容...",
            onOk: function (val) {
                if (val && val.trim()) {
                    _annots.push({ type: "note", x: x, y: y, text: val.trim() });
                    _redraw();
                }
            }
        });
    }

    function _doGone(e) {
        var el = document.elementFromPoint(e.clientX, e.clientY);
        var txt = "";
        if (el) {
            txt = (el.textContent || "").trim().substring(0, 40);
            el.style.outline = "2px dashed rgba(239,68,68,0.7)";
            setTimeout(function () { el.style.outline = ""; }, 2000);
        }
        _annots.push({ type: "gone", x: e.clientX, y: e.clientY, targetText: txt });
        _redraw();
    }

    function _doSave() {
        if (_annots.length === 0) {
            _showModal({ title: "还没有任何标注", isConfirm: true, onOk: function () {} });
            return;
        }
        var data = { page: _page, url: window.location.href, savedAt: new Date().toISOString(), annotations: _annots };
        fetch("/api/v1/annotations/" + encodeURIComponent(_page), {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(data)
        }).then(function (r) { return r.json(); }).then(function () {
            _showModal({ title: "✅ 已保存 " + _annots.length + " 条标注", isConfirm: true, onOk: function () {} });
        }).catch(function (e) {
            _showModal({ title: "❌ 保存失败: " + e, isConfirm: true, onOk: function () {} });
        });
    }

    function _doClear() {
        _showModal({
            title: "确定清空所有标注？",
            isConfirm: true,
            onOk: function () { _annots = []; _redraw(); }
        });
    }

    function _doLoad() {
        fetch("/api/v1/annotations/" + encodeURIComponent(_page))
            .then(function (r) { return r.json(); })
            .then(function (d) {
                if (d.success && d.data && d.data.annotations) {
                    _annots = d.data.annotations;
                    _redraw();
                }
            }).catch(function () {});
    }

    function _doToggle(on) {
        if (on === undefined) { _mode = (_mode === MODE_OFF) ? MODE_DRAW : MODE_OFF; }
        else { _mode = on ? MODE_DRAW : MODE_OFF; }
        if (_mode !== MODE_OFF) {
            if (!_canvas) _createOverlay();
            if (!_toolbar) _toolbar = _createToolbar();
            _canvas.style.display = "block";
            _toolbar.style.display = "block";
            _page = _getPage();
            _doLoad();
        } else {
            if (_canvas) _canvas.style.display = "none";
            if (_toolbar) _toolbar.style.display = "none";
        }
        _updateBtns();
    }

    // ── 全局事件 ──
    document.addEventListener("mousedown", _onMouseDown);
    document.addEventListener("mousemove", _onMouseMove);
    document.addEventListener("mouseup", _onMouseUp);
    document.addEventListener("contextmenu", _onContextMenu);

    // ── 样式 ──
    var style = document.createElement("style");
    style.textContent = [
        "#annotate-toolbar{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);z-index:100000;background:#1e293b;border-radius:12px;box-shadow:0 8px 32px rgba(0,0,0,0.3);padding:8px 16px;font-family:Inter,sans-serif;font-size:13px;display:none;}",
        "#annotate-toolbar .atb-inner{display:flex;align-items:center;gap:8px;}",
        "#annotate-toolbar .atb-title{color:#f59e0b;font-weight:700;margin-right:4px;}",
        "#annotate-toolbar .atb-sep{color:#475569;}",
        "#annotate-toolbar .atb-btn{background:transparent;border:1px solid transparent;color:#cbd5e1;cursor:pointer;padding:4px 10px;border-radius:6px;font-size:13px;transition:all 0.15s;}",
        "#annotate-toolbar .atb-btn:hover{background:rgba(255,255,255,0.1);color:#fff;}",
        "#annotate-toolbar .atb-btn.active{background:rgba(99,102,241,0.3);color:#a5b4fc;border-color:rgba(99,102,241,0.4);}",
        "#annotate-toolbar .atb-btn-save{background:rgba(34,197,94,0.2);color:#4ade80;}",
        "#annotate-toolbar .atb-btn-save:hover{background:rgba(34,197,94,0.35);}",
        "#annotate-toolbar .atb-btn-clear{background:rgba(239,68,68,0.15);color:#f87171;}",
        "#annotate-toolbar .atb-btn-close{background:rgba(255,255,255,0.08);color:#94a3b8;}",
        "#atb-modal input:focus{border-color:#494fdf;}"
    ].join("");
    document.head.appendChild(style);

    window._annot = { toggle: _doToggle, setMode: function (m) { _mode = m; _updateBtns(); }, save: _doSave, clearAll: _doClear };
    console.log("[annotate] v3 loaded.");
})();
