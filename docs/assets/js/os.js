/* ============================================================
   AgriVision OS — shell + chart engine + renderers
   Data lives at window.AGV (assets/js/data.js). API is window.OS.
   Dependency-free. Works over file://.
   ============================================================ */
(function () {
  "use strict";
  var OS = (window.OS = {});
  var D = window.AGV || {};

  /* ---------- tiny DOM helpers ---------- */
  function h(tag, attrs, children) {
    var e = document.createElement(tag);
    if (attrs) for (var k in attrs) {
      if (k === "class") e.className = attrs[k];
      else if (k === "html") e.innerHTML = attrs[k];
      else if (k === "text") e.textContent = attrs[k];
      else if (k.slice(0, 2) === "on" && typeof attrs[k] === "function") e.addEventListener(k.slice(2), attrs[k]);
      else if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    }
    (children || []).forEach(function (c) { if (c != null) e.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return e;
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  OS.h = h; OS.esc = esc;

  /* ---------- brand + icons ---------- */
  var brandSVG =
    '<svg viewBox="0 0 48 48" fill="none" aria-hidden="true"><defs>' +
    '<linearGradient id="agvg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#22c55e"/><stop offset="1" stop-color="#0e7a38"/></linearGradient></defs>' +
    '<path d="M24 4C13 8 7 17 7 27c0 8 5 15 13 17 0-14 4-24 15-31C29 6 26 5 24 4Z" fill="url(#agvg)"/>' +
    '<path d="M20 44c-1-13 3-23 15-31" stroke="#f5c518" stroke-width="2.4" stroke-linecap="round"/>' +
    '<circle cx="24" cy="24" r="4.4" fill="#04100a" stroke="#22c55e" stroke-width="2"/></svg>';
  OS.brandSVG = brandSVG;

  var ICON = {
    overview: '<path d="M4 13h7V4H4v9Zm9 7h7v-9h-7v9ZM4 20h7v-5H4v5ZM13 9h7V4h-7v5Z"/>',
    docs: '<path d="M5 4h11l4 4v12H5V4Z" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M9 10h7M9 14h7M9 18h4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    results: '<path d="M4 20V4M4 20h16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><rect x="7" y="12" width="3" height="5" fill="currentColor"/><rect x="12" y="8" width="3" height="9" fill="currentColor"/><rect x="17" y="5" width="3" height="12" fill="currentColor"/>',
    architecture: '<circle cx="6" cy="6" r="2.4" fill="currentColor"/><circle cx="18" cy="6" r="2.4" fill="currentColor"/><circle cx="12" cy="18" r="2.4" fill="currentColor"/><path d="M6 8v3a3 3 0 0 0 3 3h1M18 8v3a3 3 0 0 1-3 3h-1M12 15.6V14" fill="none" stroke="currentColor" stroke-width="1.7"/>',
    dashboard: '<rect x="3" y="4" width="18" height="13" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M8 20h8M12 17v3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M6 12l3-3 2 2 4-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
    pitch: '<rect x="3" y="4" width="18" height="11" rx="1.6" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 15v4m-3 1h6" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><path d="M7 11l3-2 2 1 4-3" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    sun: '<circle cx="12" cy="12" r="4.2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M12 2v2.5M12 19.5V22M2 12h2.5M19.5 12H22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M19.1 4.9l-1.8 1.8M6.7 17.3l-1.8 1.8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
    moon: '<path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/>',
    menu: '<path d="M4 7h16M4 12h16M4 17h16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    download: '<path d="M12 4v10m0 0 4-4m-4 4-4-4M5 19h14" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>',
    arrow: '<path d="M5 12h14m0 0-6-6m6 6-6 6" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"/>'
  };
  OS.icon = function (name, size) { return '<svg viewBox="0 0 24 24" width="' + (size || 24) + '" height="' + (size || 24) + '" fill="currentColor">' + (ICON[name] || "") + "</svg>"; };

  var APPS = [
    { id: "overview", label: "Overview", href: "index.html" },
    { id: "docs", label: "Docs", href: "documentation.html" },
    { id: "results", label: "Results", href: "results.html" },
    { id: "architecture", label: "System", href: "architecture.html" },
    { id: "dashboard", label: "Console", href: "dashboard.html" },
    { id: "pitch", label: "Pitch", href: "pitch.html" }
  ];

  /* ---------- theme ---------- */
  function getTheme() {
    try { var q = new URLSearchParams(location.search).get("theme"); if (q === "light" || q === "dark") { localStorage.setItem("agv-theme", q); return q; } } catch (e) {}
    return localStorage.getItem("agv-theme") || "dark";
  }
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    localStorage.setItem("agv-theme", t);
    var b = document.querySelector(".theme-btn");
    if (b) b.innerHTML = OS.icon(t === "dark" ? "sun" : "moon", 18);
    document.querySelectorAll("[data-rechart]").forEach(function (el) { if (el.__redraw) el.__redraw(); });
  }
  OS.toggleTheme = function () { applyTheme(getTheme() === "dark" ? "light" : "dark"); };

  /* ---------- chrome ---------- */
  function buildChrome() {
    var app = document.body.getAttribute("data-app") || "overview";
    var crumb = document.body.getAttribute("data-crumb") || "";

    var topbar = h("header", { class: "topbar" });
    topbar.innerHTML =
      '<button class="menu-btn" aria-label="Menu">' + OS.icon("menu", 20) + "</button>" +
      '<a class="brand" href="index.html" style="text-decoration:none;color:inherit">' + brandSVG +
      '<span><b>Agri<span>Vision</span></b><small>OS · Field Intelligence</small></span></a>' +
      '<div class="crumb">' + (crumb ? '<span class="dot">●</span> ' + esc(crumb) : "") + "</div>" +
      '<div class="spacer"></div>' +
      '<div class="status-cluster">' +
        '<span class="led"><i></i><span>Drone Link</span></span>' +
        '<span class="led amber"><i></i><span>YOLOv8 · best.pt</span></span>' +
        '<span class="led off"><i></i><span>Offline Ready</span></span>' +
        '<span class="clock" id="os-clock">--:--:--</span>' +
        '<button class="theme-btn" aria-label="Toggle theme">' + OS.icon("sun", 18) + "</button>" +
      "</div>";

    var dock = h("nav", { class: "dock", "aria-label": "Apps" });
    var dh = APPS.map(function (a) {
      return '<a href="' + a.href + '" class="' + (a.id === app ? "active" : "") + '"><span class="ic">' + OS.icon(a.id, 22) + "</span>" + esc(a.label) + "</a>";
    });
    dh.splice(2, 0, '<span class="sep"></span>');
    dh.splice(6, 0, '<span class="sep"></span>');
    dock.innerHTML = dh.join("");

    document.body.insertBefore(topbar, document.body.firstChild);
    document.body.insertBefore(dock, topbar.nextSibling);

    topbar.querySelector(".theme-btn").addEventListener("click", OS.toggleTheme);
    topbar.querySelector(".menu-btn").addEventListener("click", function () { dock.classList.toggle("open"); });
    document.addEventListener("click", function (e) {
      if (window.innerWidth <= 860 && dock.classList.contains("open") && !dock.contains(e.target) && !e.target.closest(".menu-btn")) dock.classList.remove("open");
    });
    applyTheme(getTheme());
  }

  /* ---------- boot splash ---------- */
  function boot() {
    var force = document.body.getAttribute("data-boot") === "always";
    if (!force && sessionStorage.getItem("agv-booted")) return;
    var el = h("div", { id: "boot" });
    el.innerHTML =
      '<div class="boot-wrap"><div class="boot-logo">' + brandSVG + "</div>" +
      '<div class="boot-title">Agri<span>Vision</span> OS</div>' +
      '<div class="boot-sub">Field Intelligence Platform</div>' +
      '<div class="boot-bar"><i></i></div>' +
      '<div class="boot-status" id="boot-status"></div></div>';
    document.body.appendChild(el);
    var steps = ["mounting core/…", "loading models/best.pt", "linking scrcpy mirror", "calibrating geo-tags", "ready ✓"], i = 0;
    var st = el.querySelector("#boot-status");
    var iv = setInterval(function () { st.textContent = steps[i] || ""; if (++i >= steps.length) clearInterval(iv); }, 340);
    setTimeout(function () { el.classList.add("done"); sessionStorage.setItem("agv-booted", "1"); setTimeout(function () { el.remove(); }, 650); }, 1850);
  }

  /* ---------- clock ---------- */
  function clock() {
    var el = document.getElementById("os-clock"); if (!el) return;
    function t() { var d = new Date(); el.textContent = d.toLocaleTimeString([], { hour12: false }); }
    t(); setInterval(t, 1000);
  }

  /* ---------- reveal (re-scannable for dynamically added nodes) ---------- */
  var _io;
  function scanReveal() {
    if (!("IntersectionObserver" in window)) { document.querySelectorAll("[data-reveal]").forEach(function (el) { el.classList.add("in"); }); return; }
    if (!_io) _io = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); _io.unobserve(e.target); } }); }, { threshold: 0.08 });
    document.querySelectorAll("[data-reveal]:not([data-obs])").forEach(function (el) { el.setAttribute("data-obs", ""); _io.observe(el); });
  }
  OS.scanReveal = scanReveal;

  /* ---------- footer ---------- */
  function footer() {
    if (document.querySelector(".os-foot")) return;
    var f = h("footer", { class: "os-foot" });
    f.innerHTML =
      '<div>AgriVision · Legacy College of Compostela — Institute of Information Technology · March 2026</div>' +
      '<div>Drone-based banana disease detection · YOLOv8 · Heatmaps · Geotagging</div>';
    var main = document.querySelector(".os-main"); if (main) main.appendChild(f);
  }

  /* ============================================================
     CHART ENGINE (SVG, offline)
     ============================================================ */
  var tip;
  function tipEl() { if (!tip) { tip = h("div", { class: "chart-tip" }); document.body.appendChild(tip); } return tip; }
  function showTip(html, x, y) { var t = tipEl(); t.innerHTML = html; t.style.opacity = 1; var w = t.offsetWidth, hh = t.offsetHeight; t.style.left = Math.min(window.innerWidth - w - 8, Math.max(8, x - w / 2)) + "px"; t.style.top = Math.max(8, y - hh - 14) + "px"; }
  function hideTip() { if (tip) tip.style.opacity = 0; }
  function css(v) { return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
  var SERIES = function () { return [css("--s1"), css("--s2"), css("--s3"), css("--s4"), css("--s5")]; };

  function svgWrap(w, hgt, inner) { return '<svg viewBox="0 0 ' + w + ' ' + hgt + '" width="100%" preserveAspectRatio="xMidYMid meet" style="display:block;overflow:visible">' + inner + "</svg>"; }
  function fmtNum(v, dp) { return (dp != null ? Number(v).toFixed(dp) : v); }

  /* Multi-series line chart, single y-axis (0..yMax) */
  OS.lineChart = function (container, o) {
    var el = typeof container === "string" ? document.querySelector(container) : container;
    if (!el) return;
    el.setAttribute("data-rechart", "1");
    function draw() {
      var W = 720, H = o.height || 300, m = { t: 16, r: 60, b: 34, l: 44 };
      var pw = W - m.l - m.r, ph = H - m.t - m.b;
      var pts = o.points, xs = pts.map(function (p) { return p[o.xKey]; });
      var xmin = Math.min.apply(null, xs), xmax = Math.max.apply(null, xs);
      var ymin = o.yMin != null ? o.yMin : 0, ymax = o.yMax != null ? o.yMax : Math.max.apply(null, pts.map(function (p) { return Math.max.apply(null, o.series.map(function (s) { return p[s.key] || 0; })); }));
      var X = function (v) { return m.l + (xmax === xmin ? 0 : (v - xmin) / (xmax - xmin)) * pw; };
      var Y = function (v) { return m.t + ph - (v - ymin) / (ymax - ymin) * ph; };
      var pal = SERIES(), inner = "";
      // gridlines + y ticks
      var ticks = o.yTicks || 4;
      for (var i = 0; i <= ticks; i++) { var yv = ymin + (ymax - ymin) * i / ticks, yy = Y(yv); inner += '<line class="grid-line" x1="' + m.l + '" y1="' + yy + '" x2="' + (m.l + pw) + '" y2="' + yy + '"/>'; inner += '<text class="tick" x="' + (m.l - 8) + '" y="' + (yy + 3) + '" text-anchor="end">' + (o.yFmt ? o.yFmt(yv) : fmtNum(yv, o.yDp)) + "</text>"; }
      // x ticks
      pts.forEach(function (p, idx) { if (idx % (o.xEvery || 1) === 0 || idx === pts.length - 1) { var xx = X(p[o.xKey]); inner += '<text class="tick" x="' + xx + '" y="' + (m.t + ph + 18) + '" text-anchor="middle">' + p[o.xKey] + "</text>"; } });
      inner += '<line class="axis" x1="' + m.l + '" y1="' + (m.t + ph) + '" x2="' + (m.l + pw) + '" y2="' + (m.t + ph) + '"/>';
      // lines
      o.series.forEach(function (s, si) {
        var col = s.color || pal[si % pal.length];
        var d = pts.map(function (p, i2) { return (i2 ? "L" : "M") + X(p[o.xKey]) + " " + Y(p[s.key] || 0); }).join(" ");
        inner += '<path d="' + d + '" fill="none" stroke="' + col + '" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>';
        var last = pts[pts.length - 1];
        inner += '<circle cx="' + X(last[o.xKey]) + '" cy="' + Y(last[s.key] || 0) + '" r="3.5" fill="' + col + '"/>';
        inner += '<text class="vlabel" x="' + (X(last[o.xKey]) + 7) + '" y="' + (Y(last[s.key] || 0) + 3) + '" fill="' + col + '">' + (o.yFmt ? o.yFmt(last[s.key]) : fmtNum(last[s.key], o.yDp)) + "</text>";
      });
      // hover markers
      pts.forEach(function (p) {
        var xx = X(p[o.xKey]);
        var body = o.series.map(function (s, si) { var col = s.color || pal[si % pal.length]; return '<span style="display:inline-flex;align-items:center;gap:6px"><span style="width:9px;height:9px;border-radius:3px;background:' + col + '"></span>' + esc(s.label) + ": <b>" + (o.yFmt ? o.yFmt(p[s.key]) : fmtNum(p[s.key], o.yDp)) + "</b></span>"; }).join("<br>");
        inner += '<rect x="' + (xx - pw / pts.length / 2) + '" y="' + m.t + '" width="' + (pw / pts.length) + '" height="' + ph + '" fill="transparent" style="cursor:crosshair" data-tip="' + esc('<b>' + (o.xLabel || o.xKey) + " " + p[o.xKey] + "</b><br>" + body) + '"><title></title></rect>';
        inner += '<line x1="' + xx + '" y1="' + m.t + '" x2="' + xx + '" y2="' + (m.t + ph) + '" stroke="' + css("--brand-bright") + '" stroke-width="1" opacity="0" class="cross" data-x="' + xx + '"/>';
      });
      el.innerHTML = svgWrap(W, H, inner);
      bindBars(el);
    }
    el.__redraw = draw; draw();
  };

  /* Bar chart — grouped vertical or single. o.groups=[{label, bars:[{label,value,color}]}] */
  OS.barChart = function (container, o) {
    var el = typeof container === "string" ? document.querySelector(container) : container; if (!el) return;
    el.setAttribute("data-rechart", "1");
    function draw() {
      var W = 720, H = o.height || 300, m = { t: 16, r: 16, b: 40, l: 44 };
      var pw = W - m.l - m.r, ph = H - m.t - m.b;
      var ymax = o.yMax != null ? o.yMax : Math.max.apply(null, o.groups.reduce(function (a, g) { return a.concat(g.bars.map(function (b) { return b.value; })); }, [1]));
      var Y = function (v) { return m.t + ph - (v / ymax) * ph; };
      var gW = pw / o.groups.length, inner = "";
      for (var i = 0; i <= 4; i++) { var yv = ymax * i / 4, yy = Y(yv); inner += '<line class="grid-line" x1="' + m.l + '" y1="' + yy + '" x2="' + (m.l + pw) + '" y2="' + yy + '"/>'; inner += '<text class="tick" x="' + (m.l - 8) + '" y="' + (yy + 3) + '" text-anchor="end">' + (o.yFmt ? o.yFmt(yv) : Math.round(yv)) + "</text>"; }
      o.groups.forEach(function (g, gi) {
        var n = g.bars.length, bw = Math.min(46, (gW - 16) / n), x0 = m.l + gi * gW + (gW - bw * n) / 2;
        g.bars.forEach(function (b, bi) {
          var x = x0 + bi * bw, bh = (b.value / ymax) * ph, y = m.t + ph - bh;
          inner += '<rect class="bar-seg" x="' + (x + 2) + '" y="' + y + '" width="' + (bw - 4) + '" height="' + Math.max(0, bh) + '" rx="4" fill="' + b.color + '" data-tip="' + esc("<b>" + esc(g.label) + "</b><br>" + esc(b.label) + ": <b>" + (o.valFmt ? o.valFmt(b.value) : b.value) + "</b>") + '"/>';
        });
        inner += '<text class="tick" x="' + (m.l + gi * gW + gW / 2) + '" y="' + (m.t + ph + 18) + '" text-anchor="middle">' + esc(g.label) + "</text>";
      });
      inner += '<line class="axis" x1="' + m.l + '" y1="' + (m.t + ph) + '" x2="' + (m.l + pw) + '" y2="' + (m.t + ph) + '"/>';
      el.innerHTML = svgWrap(W, H, inner);
      bindBars(el);
    }
    el.__redraw = draw; draw();
  };

  /* Horizontal bars — o.items=[{label,value,color,sub}] */
  OS.hbarChart = function (container, o) {
    var el = typeof container === "string" ? document.querySelector(container) : container; if (!el) return;
    el.setAttribute("data-rechart", "1");
    function draw() {
      var rowH = o.rowH || 40, W = 720, m = { t: 8, r: 60, b: 8, l: o.labelW || 130 };
      var H = m.t + m.b + o.items.length * rowH, pw = W - m.l - m.r;
      var ymax = o.max != null ? o.max : Math.max.apply(null, o.items.map(function (x) { return x.value; })) || 1;
      var inner = "";
      o.items.forEach(function (it, i) {
        var y = m.t + i * rowH + rowH / 2, bw = (it.value / ymax) * pw;
        inner += '<text x="' + (m.l - 10) + '" y="' + (y + 4) + '" text-anchor="end" class="vlabel" style="font-weight:600">' + esc(it.label) + "</text>";
        inner += '<rect x="' + m.l + '" y="' + (y - 9) + '" width="' + pw + '" height="18" rx="9" fill="' + css("--bg-3") + '"/>';
        inner += '<rect class="bar-seg" x="' + m.l + '" y="' + (y - 9) + '" width="' + Math.max(3, bw) + '" height="18" rx="9" fill="' + it.color + '" data-tip="' + esc("<b>" + esc(it.label) + "</b><br>" + (it.sub || "") + (o.valFmt ? o.valFmt(it.value) : it.value)) + '"/>';
        inner += '<text x="' + (m.l + Math.max(3, bw) + 8) + '" y="' + (y + 4) + '" class="vlabel">' + (o.valFmt ? o.valFmt(it.value) : it.value) + "</text>";
      });
      el.innerHTML = svgWrap(W, H, inner);
      bindBars(el);
    }
    el.__redraw = draw; draw();
  };

  /* Donut — o.segments=[{label,value,color}] */
  OS.donut = function (container, o) {
    var el = typeof container === "string" ? document.querySelector(container) : container; if (!el) return;
    el.setAttribute("data-rechart", "1");
    function draw() {
      var S = 220, cx = S / 2, cy = S / 2, r = 84, rin = 54;
      var total = o.segments.reduce(function (a, s) { return a + s.value; }, 0) || 1;
      var a0 = -Math.PI / 2, inner = "";
      o.segments.forEach(function (s) {
        var frac = s.value / total, a1 = a0 + frac * Math.PI * 2, big = frac > 0.5 ? 1 : 0;
        if (frac <= 0) return;
        var x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0), x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
        var xi1 = cx + rin * Math.cos(a1), yi1 = cy + rin * Math.sin(a1), xi0 = cx + rin * Math.cos(a0), yi0 = cy + rin * Math.sin(a0);
        inner += '<path class="bar-seg" d="M' + x0 + ' ' + y0 + ' A' + r + ' ' + r + ' 0 ' + big + ' 1 ' + x1 + ' ' + y1 + ' L' + xi1 + ' ' + yi1 + ' A' + rin + ' ' + rin + ' 0 ' + big + ' 0 ' + xi0 + ' ' + yi0 + ' Z" fill="' + s.color + '" stroke="' + css("--chart-surface") + '" stroke-width="2" data-tip="' + esc("<b>" + esc(s.label) + "</b>: " + s.value + " (" + Math.round(frac * 100) + "%)") + '"/>';
        a0 = a1;
      });
      inner += '<text x="' + cx + '" y="' + (cy - 4) + '" text-anchor="middle" class="vlabel" style="font-size:26px">' + (o.center != null ? o.center : total) + "</text>";
      inner += '<text x="' + cx + '" y="' + (cy + 16) + '" text-anchor="middle" class="tick">' + esc(o.centerLabel || "total") + "</text>";
      el.innerHTML = '<svg viewBox="0 0 ' + S + " " + S + '" width="100%" style="max-width:240px;display:block;margin:0 auto;overflow:visible">' + inner + "</svg>";
      bindBars(el);
    }
    el.__redraw = draw; draw();
  };

  function bindBars(el) {
    el.querySelectorAll("[data-tip]").forEach(function (r) {
      r.addEventListener("mousemove", function (e) { showTip(r.getAttribute("data-tip"), e.clientX, e.clientY); });
      r.addEventListener("mouseleave", hideTip);
    });
  }

  OS.legend = function (items) {
    return '<div class="legend">' + items.map(function (i) { return '<span class="li"><span class="sw" style="background:' + i.color + '"></span>' + esc(i.label) + "</span>"; }).join("") + "</div>";
  };

  /* ============================================================
     RENDERERS (documentation blocks, tables, figures)
     ============================================================ */
  OS.tableHTML = function (t) {
    if (!t) return "";
    var hl = t.highlightCol;
    var head = "<tr>" + t.headers.map(function (hd, i) { return "<th" + (hl === i ? ' class="hl"' : "") + ">" + esc(hd) + "</th>"; }).join("") + "</tr>";
    var body = t.rows.map(function (r) {
      var isSum = /^(Average|Total Average|Total)$/i.test(r[0]);
      return "<tr" + (isSum ? ' class="sum"' : "") + ">" + r.map(function (c, i) { return "<td" + (hl === i ? ' class="hl"' : "") + ">" + esc(c) + "</td>"; }).join("") + "</tr>";
    }).join("");
    return '<div class="tbl-wrap"><table class="data"><thead>' + head + "</thead><tbody>" + body + "</tbody></table></div>" +
      '<p class="tbl-cap"><b>' + esc(t.number) + ".</b> " + esc(t.caption) + (t.note ? ' — <span class="muted">' + esc(t.note) + "</span>" : "") + "</p>";
  };

  OS.figureHTML = function (f) {
    if (!f) return "";
    if (f.group) {
      var imgs = f.items.map(function (it) { return '<div><div class="frame" style="padding:8px;background:#fff"><img loading="lazy" src="' + esc(it.file) + '" alt="' + esc(it.label) + '"></div><p class="slide-label">' + esc(it.label) + "</p></div>"; }).join("");
      return '<figure class="fig"><div class="fig-group">' + imgs + "</div>" +
        '<p class="fig-cap"><b>' + esc(f.number) + ".</b> " + esc(f.title) + "</p>" +
        (f.desc ? '<p class="desc">' + esc(f.desc) + "</p>" : "") + "</figure>";
    }
    return '<figure class="fig"><div class="frame"><img loading="lazy" src="' + esc(f.file) + '" alt="' + esc(f.title) + '"></div>' +
      '<p class="fig-cap"><b>' + esc(f.number) + ".</b> " + esc(f.title) + "</p>" +
      (f.desc ? '<p class="desc">' + esc(f.desc) + "</p>" : "") + "</figure>";
  };

  OS.renderBlocks = function (host, blocks) {
    blocks.forEach(function (b) {
      var node;
      switch (b.type) {
        case "paragraph": node = h("p", { html: linkRefs(esc(b.text)) }); break;
        case "heading": node = h("h" + (b.level === 2 ? "3" : "4"), { class: "sub", text: b.text }); break;
        case "list":
          node = h(b.ordered ? "ol" : "ul", b.ordered ? { class: "clean" } : {});
          b.items.forEach(function (it) { node.appendChild(h("li", { html: esc(it) })); });
          break;
        case "definitionList":
          node = h("div", { class: "deflist" });
          b.items.forEach(function (it) { node.appendChild(h("div", { class: "di", html: "<b>" + esc(it.term) + ".</b> <span>" + esc(it.def) + "</span>" })); });
          break;
        case "callout":
          node = h("div", { class: "callout " + (b.variant || "info"), html: "<b>" + esc(b.title) + "</b><span>" + esc(b.text) + "</span>" }); break;
        case "reqList":
          node = h("div", {});
          b.items.forEach(function (it) { node.appendChild(h("div", { class: "req " + (b.kind === "nonfunctional" ? "nf" : ""), html: '<span class="rid">' + esc(it.id) + "</span><div><p>" + esc(it.text) + "</p></div>" })); });
          break;
        case "table": node = h("div", { html: OS.tableHTML(D.tables[b.ref]) }); break;
        case "figure": node = h("div", { html: OS.figureHTML(D.figures[b.ref]) }); break;
        case "figureGroup": node = h("div", { html: OS.figureHTML(D.figures[b.ref]) }); break;
        case "chart":
          node = h("div", { class: "chart-card", style: "margin:22px 0" });
          if (b.ref === "epochMetrics") { OS.__pendingCharts = OS.__pendingCharts || []; var cid = "chart-" + b.ref; node.innerHTML = '<div class="chart-head"><h3>Checkpoint metrics by epoch</h3><span class="sub">Table 13 · AdamW optimizer</span></div><div id="' + cid + '"></div>'; OS.__pendingCharts.push(cid); }
          break;
        default: node = h("div");
      }
      if (node) { node.setAttribute("data-reveal", ""); host.appendChild(node); }
    });
  };

  function linkRefs(txt) {
    return txt.replace(/\[(\d{1,2})\](?:&#8211;|–|-)\[(\d{1,2})\]/g, function (mm, a, b) { return refspan(a) + "–" + refspan(b); })
      .replace(/\[(\d{1,2})\]/g, function (mm, n) { return refspan(n); });
  }
  function refspan(n) { return '<a class="tag" href="documentation.html#references" title="Reference ' + n + '" style="text-decoration:none">[' + n + "]</a>"; }
  OS.linkRefs = linkRefs;

  OS.mountEpochChart = function () {
    (OS.__pendingCharts || []).forEach(function (cid) {
      var m = D.metrics.checkpoints;
      OS.barChart("#" + cid, {
        height: 280,
        yMax: 100,
        groups: m.map(function (c) {
          return { label: c.epoch + " ep", bars: [
            { label: "Accuracy (mAP@.5)", value: c.accuracy, color: css("--s1") },
            { label: "Recall", value: c.recall, color: css("--s5") },
            { label: "Precision", value: c.precision, color: css("--s2") },
            { label: "F1-Score", value: c.f1, color: css("--s4") }
          ] };
        }),
        valFmt: function (v) { return v + "%"; }
      });
      var host = document.getElementById(cid);
      if (host) host.insertAdjacentHTML("afterend", OS.legend([
        { label: "Accuracy", color: css("--s1") }, { label: "Recall", color: css("--s5") },
        { label: "Precision", color: css("--s2") }, { label: "F1-Score", color: css("--s4") }
      ]));
    });
  };

  /* ---------- init ---------- */
  function init() { buildChrome(); boot(); clock(); footer(); scanReveal(); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();
  OS.ready = function (fn) { if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn); else fn(); };
})();
