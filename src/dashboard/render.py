"""生成纯静态 HTML 看板（内嵌 SVG 折线 + 原生 JS 交互）。

看板数据直接内嵌进 ``<script>``，无 CDN、无外链，断网可打开。
交互：站点筛选（复选框）、时间范围切换（近 7/14/30 天、全部）、指标切换（温度/湿度/气压/PM2.5）。
"""

from __future__ import annotations

import json
from pathlib import Path

_HTML_HEAD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IoT 传感器数据看板</title>
<style>
:root { --bg:#0f172a; --panel:#1e293b; --line:#334155; --text:#e2e8f0; --muted:#94a3b8; --accent:#38bdf8; }
* { box-sizing: border-box; }
body { margin:0; background:var(--bg); color:var(--text); font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; }
header { padding:24px 28px 16px; border-bottom:1px solid var(--line); }
header h1 { margin:0; font-size:22px; }
header p { margin:6px 0 0; color:var(--muted); font-size:13px; }
.wrap { padding:20px 28px 40px; }
.controls { display:flex; flex-wrap:wrap; gap:18px; align-items:flex-start; margin-bottom:16px; }
.group { display:flex; flex-direction:column; gap:8px; }
.group > .label { font-size:12px; color:var(--muted); }
.tabs, .ranges { display:flex; gap:6px; flex-wrap:wrap; }
.tab, .range-btn { background:var(--panel); color:var(--text); border:1px solid var(--line); padding:6px 12px; border-radius:6px; cursor:pointer; font-size:13px; }
.tab.active, .range-btn.active { background:var(--accent); color:#082f49; border-color:var(--accent); font-weight:600; }
.sites { display:flex; gap:10px; flex-wrap:wrap; }
.site-chip { display:flex; align-items:center; gap:5px; font-size:13px; cursor:pointer; }
.site-chip input { accent-color:var(--accent); }
.dot { width:10px; height:10px; border-radius:50%; display:inline-block; }
.chart-card { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:16px; margin-bottom:20px; }
.chart-card svg { width:100%; height:auto; display:block; }
.legend { display:flex; gap:14px; flex-wrap:wrap; margin-top:10px; font-size:12px; color:var(--muted); }
.legend span { display:inline-flex; align-items:center; gap:5px; }
table { width:100%; border-collapse:collapse; background:var(--panel); border-radius:10px; overflow:hidden; font-size:13px; }
th, td { padding:10px 12px; text-align:right; border-bottom:1px solid var(--line); }
th:first-child, td:first-child { text-align:left; }
thead th { background:#0b1220; color:var(--muted); font-weight:600; }
tr.dimmed { opacity:.35; }
.summary-title { font-size:14px; font-weight:600; margin:0 0 10px; }
.axis { fill:var(--muted); font-size:11px; }
.grid { stroke:var(--line); stroke-width:1; }
.line { fill:none; stroke-width:2; stroke-linejoin:round; stroke-linecap:round; }
</style>
</head>
<body>
<header>
  <h1>IoT 传感器数据看板</h1>
  <p>ODS → DWD → DWS → ADS 四层 ETL · 确定性随机模拟数据 · 纯 SVG 离线渲染</p>
</header>
<div class="wrap">
  <div class="controls">
    <div class="group">
      <span class="label">指标</span>
      <div class="tabs" id="metricTabs"></div>
    </div>
    <div class="group">
      <span class="label">站点</span>
      <div class="sites" id="siteFilters"></div>
    </div>
    <div class="group">
      <span class="label">时间范围</span>
      <div class="ranges" id="rangeBtns"></div>
    </div>
  </div>
  <div class="chart-card">
    <svg id="chart" viewBox="0 0 960 420" role="img"></svg>
    <div class="legend" id="legend"></div>
  </div>
  <p class="summary-title">站点对比（30 天均值）</p>
  <table id="summary"></table>
</div>
"""

_HTML_TAIL = """</body>
</html>
"""

_JS_TEMPLATE = """<script>
const DATA = __DATA__;

const SVG_NS = 'http://www.w3.org/2000/svg';
const COLORS = ['#38bdf8','#f87171','#4ade80','#fbbf24','#a78bfa','#2dd4bf','#f472b6','#a3e635','#fb923c','#818cf8'];

const METRICS = DATA.metrics;
const TRENDS = DATA.trends;
const W = 960, H = 420;
const PAD = { top: 20, right: 20, bottom: 50, left: 62 };
const PLOT_W = W - PAD.left - PAD.right;
const PLOT_H = H - PAD.top - PAD.bottom;

let currentMetric = METRICS[0].key;
let currentRange = 'all';
let selectedSites = new Set(TRENDS.map(t => t.site_id));

const siteData = TRENDS.map(t => ({
  site_id: t.site_id,
  site_name: t.site_name,
  map: new Map(t.points.map(p => [p.hour, p])),
}));
const siteName = Object.fromEntries(TRENDS.map(t => [t.site_id, t.site_name]));

function colorOf(siteId) { return COLORS[(siteId - 1) % COLORS.length]; }

function el(name, attrs) {
  const e = document.createElementNS(SVG_NS, name);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  return e;
}
function textEl(x, y, txt, anchor) {
  const t = el('text', { x, y, 'text-anchor': anchor || 'middle', class: 'axis' });
  t.textContent = txt;
  return t;
}

function rangeDays() {
  return { '7d': 7, '14d': 14, '30d': 30, all: null }[currentRange];
}
function fmt(v) {
  if (v == null) return '';
  if (Math.abs(v) >= 100) return v.toFixed(0);
  return v.toFixed(1);
}

function collectHours(sites) {
  const set = new Set();
  sites.forEach(s => s.map.forEach((_, h) => set.add(h)));
  return Array.from(set).sort();
}

function render() {
  const metric = currentMetric;
  const chart = document.getElementById('chart');
  chart.innerHTML = '';

  const visible = siteData.filter(s => selectedSites.has(s.site_id));
  let hours = collectHours(visible);
  const days = rangeDays();
  if (days != null) hours = hours.slice(-days * 24);

  // y 轴范围
  let yMin = Infinity, yMax = -Infinity;
  hours.forEach(h => {
    visible.forEach(s => {
      const v = s.map.get(h) && s.map.get(h)[metric];
      if (v != null) { if (v < yMin) yMin = v; if (v > yMax) yMax = v; }
    });
  });
  if (!isFinite(yMin)) { yMin = 0; yMax = 1; }
  if (yMin === yMax) { yMin -= 1; yMax += 1; }
  const padY = (yMax - yMin) * 0.05;
  yMin -= padY; yMax += padY;

  const xFor = i => PAD.left + (hours.length <= 1 ? PLOT_W / 2 : i / (hours.length - 1) * PLOT_W);
  const yFor = v => PAD.top + (1 - (v - yMin) / (yMax - yMin)) * PLOT_H;

  // 网格与 y 轴刻度
  const yTickCount = 5;
  for (let k = 0; k < yTickCount; k++) {
    const val = yMin + (yMax - yMin) * k / (yTickCount - 1);
    const y = yFor(val);
    chart.appendChild(el('line', { x1: PAD.left, y1: y, x2: PAD.left + PLOT_W, y2: y, class: 'grid' }));
    chart.appendChild(textEl(PAD.left - 8, y + 4, fmt(val), 'end'));
  }
  // x 轴刻度（约 6 个）
  const xTickCount = 6;
  const xIdx = [];
  if (hours.length <= 1) xIdx.push(0);
  else for (let k = 0; k < xTickCount; k++) xIdx.push(Math.round(k * (hours.length - 1) / (xTickCount - 1)));
  xIdx.forEach(i => {
    const x = xFor(i);
    chart.appendChild(el('line', { x1: x, y1: PAD.top, x2: x, y2: PAD.top + PLOT_H, class: 'grid' }));
    const label = hours[i].slice(5, 13);
    chart.appendChild(textEl(x, PAD.top + PLOT_H + 18, label, 'middle'));
  });

  // 轴线
  chart.appendChild(el('line', { x1: PAD.left, y1: PAD.top, x2: PAD.left, y2: PAD.top + PLOT_H, class: 'grid' }));
  chart.appendChild(el('line', { x1: PAD.left, y1: PAD.top + PLOT_H, x2: PAD.left + PLOT_W, y2: PAD.top + PLOT_H, class: 'grid' }));

  // 折线
  visible.forEach(s => {
    const pts = [];
    hours.forEach((h, i) => {
      const p = s.map.get(h);
      const v = p ? p[metric] : null;
      if (v != null) pts.push([xFor(i), yFor(v)]);
    });
    if (pts.length) {
      const d = pts.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
      chart.appendChild(el('path', { d, stroke: colorOf(s.site_id), class: 'line' }));
    }
  });

  // 图例
  const legend = document.getElementById('legend');
  legend.innerHTML = '';
  visible.forEach(s => {
    const sp = document.createElement('span');
    sp.innerHTML = '<span class="dot" style="background:' + colorOf(s.site_id) + '"></span>' + s.site_name;
    legend.appendChild(sp);
  });
  if (!visible.length) legend.innerHTML = '<span>未选择站点</span>';

  renderSummary();
}

function renderSummary() {
  const table = document.getElementById('summary');
  const labels = Object.fromEntries(METRICS.map(m => [m.key, m.label]));
  let html = '<thead><tr><th>站点</th>';
  METRICS.forEach(m => { html += '<th>' + m.label + ' (' + m.unit + ')</th>'; });
  html += '</tr></thead><tbody>';
  DATA.summary.forEach(row => {
    const dim = selectedSites.has(row.site_id) ? '' : ' class="dimmed"';
    html += '<tr' + dim + '><td>' + row.site_name + '</td>';
    METRICS.forEach(m => { html += '<td>' + (row[m.key] == null ? '—' : row[m.key].toFixed(2)) + '</td>'; });
    html += '</tr>';
  });
  html += '</tbody>';
  table.innerHTML = html;
}

function buildControls() {
  const tabs = document.getElementById('metricTabs');
  METRICS.forEach(m => {
    const b = document.createElement('button');
    b.className = 'tab' + (m.key === currentMetric ? ' active' : '');
    b.textContent = m.label;
    b.onclick = () => { currentMetric = m.key; refreshTabs(); render(); };
    tabs.appendChild(b);
  });

  const sites = document.getElementById('siteFilters');
  TRENDS.forEach(t => {
    const lab = document.createElement('label');
    lab.className = 'site-chip';
    lab.innerHTML = '<input type="checkbox" checked> <span class="dot" style="background:' + colorOf(t.site_id) + '"></span>' + t.site_name;
    const cb = lab.querySelector('input');
    cb.onchange = () => { cb.checked ? selectedSites.add(t.site_id) : selectedSites.delete(t.site_id); render(); };
    sites.appendChild(lab);
  });

  const ranges = document.getElementById('rangeBtns');
  [['7d','近 7 天'],['14d','近 14 天'],['30d','近 30 天'],['all','全部']].forEach(([key, label]) => {
    const b = document.createElement('button');
    b.className = 'range-btn' + (key === currentRange ? ' active' : '');
    b.textContent = label;
    b.onclick = () => { currentRange = key; refreshRanges(); render(); };
    ranges.appendChild(b);
  });
}

function refreshTabs() {
  document.querySelectorAll('.tab').forEach(b => {
    b.classList.toggle('active', b.textContent === Object.fromEntries(METRICS.map(m => [m.key, m.label]))[currentMetric]);
  });
}
function refreshRanges() {
  document.querySelectorAll('.range-btn').forEach(b => {
    b.classList.toggle('active', b.textContent === ({ '7d':'近 7 天','14d':'近 14 天','30d':'近 30 天',all:'全部' })[currentRange]);
  });
}

buildControls();
render();
</script>
"""


def render_html(data_path: Path, out_path: Path) -> None:
    """读取 dashboard_data.json，生成纯静态 HTML（内嵌 SVG + 原生 JS 交互）。"""
    data = json.loads(data_path.read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    js = _JS_TEMPLATE.replace("__DATA__", payload)
    html = _HTML_HEAD + js + _HTML_TAIL
    out_path.write_text(html, encoding="utf-8")
