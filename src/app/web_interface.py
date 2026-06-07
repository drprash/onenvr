import os
import re
import yaml
import shutil
import logging
import hashlib
import secrets
import threading
from datetime import datetime
from flask import (Flask, send_from_directory, render_template_string,
                   abort, request, redirect, url_for, session, jsonify)
from functools import wraps

logger = logging.getLogger(__name__)

CONFIG_PATH = '/config/config.yaml'
STORAGE_PATH = '/storage'
CONFIG_DIR = '/config'

# ── CSS ──────────────────────────────────────────────────────────────────────
_CSS = """
:root {
  --bg:#0d1117; --bg-card:#161b22; --bg-hover:#1c2128;
  --border:#30363d; --border-subtle:#21262d;
  --text:#e6edf3; --text-body:#cdd9e5; --text-muted:#7d8590;
  --text-dim:#6e7681; --text-faint:#3d444d;
  --accent:#388bfd; --accent-hover:#58a6ff;
  --green:#3fb950; --red:#f85149; --yellow:#d29922;
  --green-bg:#12261e; --red-bg:#2d1217; --yellow-bg:#272115; --gray-bg:#161b22;
  --row-hover:rgba(28,33,40,.27);
  --btn-d-border:rgba(110,39,35,.3); --btn-d-hover:rgba(45,18,23,.27);
  --alert-e-bg:rgba(45,18,23,.2); --alert-e-border:rgba(110,39,35,.27);
  --alert-s-bg:rgba(18,38,30,.2); --alert-s-border:rgba(46,160,67,.27);
  --focus-ring:rgba(56,139,253,.1);
}
[data-theme="light"] {
  --bg:#f6f8fa; --bg-card:#ffffff; --bg-hover:#f3f4f6;
  --border:#d0d7de; --border-subtle:#d0d7de;
  --text:#1f2328; --text-body:#24292f; --text-muted:#57606a;
  --text-dim:#6e7781; --text-faint:#6e7781;
  --accent:#0969da; --accent-hover:#0969da;
  --green:#1a7f37; --red:#cf222e; --yellow:#9a6700;
  --green-bg:#dafbe1; --red-bg:#ffebe9; --yellow-bg:#fff8c5; --gray-bg:#f6f8fa;
  --row-hover:rgba(208,215,222,.2);
  --btn-d-border:rgba(207,34,46,.25); --btn-d-hover:rgba(255,235,233,.6);
  --alert-e-bg:rgba(255,235,233,.5); --alert-e-border:rgba(207,34,46,.25);
  --alert-s-bg:rgba(218,251,225,.5); --alert-s-border:rgba(26,127,55,.25);
  --focus-ring:rgba(9,105,218,.1);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg);
       color: var(--text); min-height: 100vh; display: flex; }
/* Mobile header */
.mobile-header { display: none; align-items: center; justify-content: space-between;
  position: fixed; top: 0; left: 0; right: 0; height: 50px;
  background: var(--bg-card); border-bottom: 1px solid var(--border);
  padding: 0 14px; z-index: 8; }
.mobile-header h1 { font-size: 1.05em; color: var(--accent); font-weight: 700; letter-spacing: -.02em; }
.hamburger { background: none; border: none; cursor: pointer; color: var(--text);
             padding: 6px; border-radius: 6px; display: flex; align-items: center; }
.hamburger:hover { background: var(--bg-hover); }
/* Drawer backdrop */
.drawer-backdrop { display: none; position: fixed; inset: 0; background: rgba(0,0,0,.55); z-index: 9; }
/* Sidebar */
.sb { width: 220px; background: var(--bg-card); border-right: 1px solid var(--border);
      display: flex; flex-direction: column; position: fixed; height: 100vh; z-index: 10; }
.sb-logo { padding: 18px 16px; border-bottom: 1px solid var(--border); }
.sb-logo h1 { font-size: 1.2em; color: var(--accent); font-weight: 700; letter-spacing: -.02em; }
.sb-logo p { font-size: .68em; color: var(--text-dim); margin-top: 2px; }
.sb-nav { flex: 1; padding: 10px 0; overflow-y: auto; }
.sb-sec { padding: 7px 14px 3px; font-size: .63em; color: var(--text-faint);
          text-transform: uppercase; letter-spacing: .06em; font-weight: 600; }
.sb-nav a { display: flex; align-items: center; gap: 9px; padding: 8px 12px;
            margin: 1px 6px; border-radius: 6px; color: var(--text-muted); text-decoration: none;
            font-size: .85em; transition: all .1s; }
.sb-nav a:hover { color: var(--text-body); background: var(--bg-hover); }
.sb-nav a.active { color: var(--text); background: var(--bg-hover); }
.sb-nav a svg { width: 16px; height: 16px; flex-shrink: 0; stroke-width: 1.75; }
.sb-foot { padding: 10px; border-top: 1px solid var(--border); display: flex; align-items: center; gap: 4px; }
.sb-foot a { display: flex; align-items: center; gap: 8px; color: var(--text-dim); text-decoration: none;
             font-size: .8em; padding: 7px 10px; border-radius: 6px; flex: 1; }
.sb-foot a:hover { color: var(--text-muted); background: var(--bg-hover); }
.theme-btn { background: none; border: none; cursor: pointer; color: var(--text-dim);
             font-size: .95em; padding: 7px 8px; border-radius: 6px; line-height: 1; flex-shrink: 0; }
.theme-btn:hover { color: var(--text-muted); background: var(--bg-hover); }
/* Main */
.main { margin-left: 220px; flex: 1; padding: 26px 30px; }
/* Page header */
.ph { margin-bottom: 22px; display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.ph-l h2 { font-size: 1.35em; font-weight: 600; color: var(--text); letter-spacing: -.02em; }
.ph-l p { color: var(--text-dim); font-size: .82em; margin-top: 3px; }
/* Stats row */
.stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
         gap: 12px; margin-bottom: 22px; }
.stat { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; padding: 15px; }
.stat-l { font-size: .72em; color: var(--text-muted); text-transform: uppercase;
          letter-spacing: .05em; font-weight: 600; margin-bottom: 7px; }
.stat-v { font-size: 1.6em; font-weight: 700; color: var(--text); }
.stat-s { font-size: .72em; color: var(--text-dim); margin-top: 2px; }
/* Cards */
.card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
        margin-bottom: 18px; overflow: hidden; }
.card-h { padding: 12px 16px; border-bottom: 1px solid var(--border);
          display: flex; align-items: center; justify-content: space-between; }
.card-h h3 { font-size: .78em; font-weight: 600; color: var(--text-muted);
             text-transform: uppercase; letter-spacing: .05em; }
.card-b { padding: 16px; }
/* Table */
.tbl-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 9px 14px; font-size: .72em; color: var(--text-dim);
     font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
     border-bottom: 1px solid var(--border); }
td { padding: 11px 14px; font-size: .85em; border-bottom: 1px solid var(--bg);
     color: var(--text-body); vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: var(--row-hover); }
/* Badges */
.badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px;
         border-radius: 20px; font-size: .72em; font-weight: 500; white-space: nowrap; }
.bg { background: var(--green-bg); color: var(--green); }
.br { background: var(--red-bg); color: var(--red); }
.by { background: var(--yellow-bg); color: var(--yellow); }
.bgr { background: var(--gray-bg); color: var(--text-dim); border: 1px solid var(--border); }
.dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; display: inline-block; }
/* Disk bar */
.bar-wrap { background: var(--bg); border-radius: 4px; height: 7px; overflow: hidden; margin-top: 8px; }
.bar { height: 100%; border-radius: 4px; transition: width .3s; }
.bar-g { background: linear-gradient(90deg, #3fb950, #2ea043); }
.bar-y { background: linear-gradient(90deg, #d29922, #b08800); }
.bar-r { background: linear-gradient(90deg, #f85149, #da3633); }
/* Forms */
.fg { margin-bottom: 16px; }
.fg label { display: block; font-size: .8em; color: var(--text-muted); margin-bottom: 5px; font-weight: 500; }
.fg input[type=text], .fg input[type=password], .fg input[type=number],
.fg select, .fg textarea { width: 100%; padding: 7px 11px; background: var(--bg);
  border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: .875em; outline: none; }
.fg input:focus, .fg select:focus, .fg textarea:focus
  { border-color: var(--accent); box-shadow: 0 0 0 3px var(--focus-ring); }
.fhint { font-size: .73em; color: var(--text-dim); margin-top: 4px; }
.fr { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.cb { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.cb input[type=checkbox] { width: 16px; height: 16px; cursor: pointer; accent-color: var(--accent); }
.cb label { margin: 0; font-size: .875em; color: var(--text-body); cursor: pointer; }
/* Buttons */
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 15px;
       border-radius: 6px; font-size: .85em; font-weight: 500; cursor: pointer;
       text-decoration: none; border: 1px solid transparent; transition: all .1s; white-space: nowrap; }
.btn-p { background: #238636; border-color: #2ea043; color: #fff; }
.btn-p:hover { background: #2ea043; }
.btn-b { background: #1f6feb; border-color: #388bfd; color: #fff; }
.btn-b:hover { background: #388bfd; }
.btn-s { background: transparent; border-color: var(--border); color: var(--text-body); }
.btn-s:hover { background: var(--bg-hover); border-color: var(--text-dim); }
.btn-d { background: transparent; border-color: var(--btn-d-border); color: var(--red); }
.btn-d:hover { background: var(--btn-d-hover); border-color: var(--red); }
.btn-sm { padding: 4px 10px; font-size: .78em; }
.btn-grp { display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }
/* Alerts */
.alert { padding: 10px 14px; border-radius: 6px; margin-bottom: 14px; font-size: .85em; }
.alert-e { background: var(--alert-e-bg); border: 1px solid var(--alert-e-border); color: var(--red); }
.alert-s { background: var(--alert-s-bg); border: 1px solid var(--alert-s-border); color: var(--green); }
/* Breadcrumb */
.bc { display: flex; align-items: center; gap: 5px; font-size: .78em; color: var(--text-dim);
      margin-bottom: 16px; flex-wrap: wrap; }
.bc a { color: var(--accent); text-decoration: none; }
.bc a:hover { text-decoration: underline; }
/* Recordings */
.date-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 9px; }
.date-card { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
             padding: 13px; text-align: center; text-decoration: none;
             color: var(--text-muted); font-size: .82em; transition: all .1s; }
.date-card:hover { border-color: var(--accent); color: var(--accent); }
.vgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 13px; }
.vc { background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
      padding: 14px; text-decoration: none; color: inherit; display: block; transition: all .1s; }
.vc:hover { border-color: var(--accent); transform: translateY(-1px); }
.vc-t { font-weight: 600; color: var(--text); margin-bottom: 4px; font-size: .9em; }
.vc-s { font-size: .78em; color: var(--accent); margin-bottom: 3px; }
.vc-f { font-size: .7em; color: var(--text-faint); font-family: monospace; }
.cl a { display: flex; align-items: center; gap: 10px; padding: 11px 14px;
        background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
        margin-bottom: 7px; text-decoration: none; color: var(--accent); font-size: .9em; transition: all .1s; }
.cl a:hover { border-color: var(--accent); color: var(--accent-hover); }
.cl a svg { width: 16px; height: 16px; color: var(--text-dim); flex-shrink: 0; }
/* Video */
video { width: 100%; border-radius: 6px; background: #000; max-height: 70vh; }
/* Login */
.lw { display: flex; justify-content: center; align-items: center;
      min-height: 100vh; width: 100%; background: var(--bg); }
.lb { width: 100%; max-width: 360px; background: var(--bg-card); border: 1px solid var(--border);
      border-radius: 12px; padding: 30px; margin: 16px; }
.lb h1 { color: var(--accent); font-size: 1.5em; text-align: center;
         margin-bottom: 4px; font-weight: 700; }
.lb .sub { color: var(--text-dim); text-align: center; font-size: .78em; margin-bottom: 22px; }
.lb .btn { width: 100%; justify-content: center; margin-top: 6px; }
.lb .fg input { width: 100%; }
.ll { display: block; text-align: center; margin-top: 12px; color: var(--accent);
      font-size: .78em; text-decoration: none; }
.ll:hover { text-decoration: underline; }
/* Empty */
.empty { text-align: center; color: var(--text-faint); padding: 36px 20px; font-size: .875em; }
.empty svg { width: 44px; height: 44px; margin: 0 auto 10px; display: block; color: var(--border-subtle); }
/* Divider */
.div { border: none; border-top: 1px solid var(--border); margin: 18px 0; }
/* Camera status row for dashboard */
.cam-row td:first-child { font-weight: 500; color: var(--text); }
/* Utility */
.text-green { color: var(--green); }
.text-red { color: var(--red); }
.text-yellow { color: var(--yellow); }
@media (max-width: 720px) {
  .mobile-header { display: flex; }
  .sb { transform: translateX(-220px); transition: transform .25s ease; z-index: 100; }
  .drawer-open .sb { transform: translateX(0); box-shadow: 4px 0 24px rgba(0,0,0,.4); }
  .drawer-open .drawer-backdrop { display: block; }
  .sb-nav a { min-height: 44px; }
  .main { margin-left: 0; padding: 14px; padding-top: 64px; }
  .fr { grid-template-columns: 1fr; }
  .stats { grid-template-columns: repeat(2, 1fr); }
}
"""

# ── Base layout template ──────────────────────────────────────────────────────
_FOUC_SCRIPT = "<script>(function(){var t=localStorage.getItem('onenvr-theme')||'auto';document.documentElement.dataset.theme=t==='auto'?(window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'):t;})()</script>"

_BASE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }} – OneNVR</title>""" + _FOUC_SCRIPT + """<style>""" + _CSS + """</style></head>
<body>
<div class="mobile-header">
  <button class="hamburger" onclick="toggleDrawer()" aria-label="Open menu">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="20" height="20" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
  </button>
  <h1>OneNVR</h1>
  <div style="width:32px"></div>
</div>
<div class="drawer-backdrop" onclick="closeDrawer()"></div>
<nav class="sb">
  <div class="sb-logo"><h1>OneNVR</h1><p>Network Video Recorder</p></div>
  <div class="sb-nav">
    <div class="sb-sec">Monitor</div>
    <a href="/" class="{{ 'active' if active=='dashboard' else '' }}" onclick="closeDrawer()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>
      <span>Dashboard</span></a>
    <a href="/recordings" class="{{ 'active' if active=='recordings' else '' }}" onclick="closeDrawer()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
      <span>Recordings</span></a>
    <div class="sb-sec">Configure</div>
    <a href="/cameras" class="{{ 'active' if active=='cameras' else '' }}" onclick="closeDrawer()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14.5 4h-5L7 7H4a2 2 0 00-2 2v9a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
      <span>Cameras</span></a>
    <a href="/settings" class="{{ 'active' if active=='settings' else '' }}" onclick="closeDrawer()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
      <span>Settings</span></a>
  </div>
  <div class="sb-foot">
    <button class="theme-btn" id="theme-btn" onclick="cycleTheme()" title="Toggle theme">◐</button>
    <a href="/logout" onclick="closeDrawer()">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="16" height="16"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
      <span>Logout</span></a>
  </div>
</nav>
<main class="main">{{ body | safe }}</main>
<script>
(function(){
  function openDrawer(){document.body.classList.add('drawer-open');}
  function closeDrawer(){document.body.classList.remove('drawer-open');}
  window.openDrawer=openDrawer;
  window.closeDrawer=closeDrawer;
  window.toggleDrawer=function(){document.body.classList.contains('drawer-open')?closeDrawer():openDrawer();};
  document.addEventListener('keydown',function(e){if(e.key==='Escape')closeDrawer();});
})();
(function(){
  var KEY='onenvr-theme',ORDER=['auto','light','dark'],ICONS={auto:'◐',light:'☀',dark:'☾'};
  function apply(t){
    document.documentElement.dataset.theme=t==='auto'?(window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'):t;
  }
  function updateBtn(t){var b=document.getElementById('theme-btn');if(b){b.textContent=ICONS[t];b.title='Theme: '+t;}}
  window.cycleTheme=function(){
    var t=localStorage.getItem(KEY)||'auto';
    var n=ORDER[(ORDER.indexOf(t)+1)%ORDER.length];
    localStorage.setItem(KEY,n);apply(n);updateBtn(n);
  };
  var saved=localStorage.getItem(KEY)||'auto';
  updateBtn(saved);
  window.matchMedia('(prefers-color-scheme: light)').addEventListener('change',function(){
    if((localStorage.getItem(KEY)||'auto')==='auto')apply('auto');
  });
})();
</script>
</body></html>"""

_LOGIN_BASE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }} – OneNVR</title>""" + _FOUC_SCRIPT + """<style>""" + _CSS + """</style></head>
<body>{{ body | safe }}</body></html>"""


def _rp(body_tpl, title, active, **ctx):
    """Render a page using the base layout with sidebar."""
    body = render_template_string(body_tpl, **ctx)
    return render_template_string(_BASE, title=title, active=active, body=body)


def _rl(body_tpl, title, **ctx):
    """Render a login-style page (no sidebar)."""
    body = render_template_string(body_tpl, **ctx)
    return render_template_string(_LOGIN_BASE, title=title, body=body)


# ── Page templates ────────────────────────────────────────────────────────────
_DASHBOARD = """
<div class="ph">
  <div class="ph-l"><h2>Dashboard</h2><p>System overview and camera health</p></div>
  <a href="/recordings" class="btn btn-s">Browse Recordings</a>
</div>
<div class="stats">
  <div class="stat">
    <div class="stat-l">Cameras</div>
    <div class="stat-v">{{ total }}</div>
    <div class="stat-s">configured</div>
  </div>
  <div class="stat">
    <div class="stat-l">Recording</div>
    <div class="stat-v {{ 'text-green' if healthy==total and total>0 else ('text-red' if healthy==0 and total>0 else '') }}" id="stat-healthy" data-total="{{ total }}">{{ healthy }}</div>
    <div class="stat-s">of {{ total }} healthy</div>
  </div>
  <div class="stat">
    <div class="stat-l">Disk Used</div>
    <div class="stat-v {{ 'text-red' if disk_pct>90 else ('text-yellow' if disk_pct>75 else '') }}">{{ disk_pct }}%</div>
    <div class="stat-s">{{ disk_free }}GB free</div>
  </div>
  <div class="stat">
    <div class="stat-l">Retention</div>
    <div class="stat-v">{{ retention }}</div>
    <div class="stat-s">days</div>
  </div>
</div>

<div class="card">
  <div class="card-h"><h3>Disk Usage</h3><span style="font-size:.78em;color:var(--text-dim)">{{ disk_used }}GB / {{ disk_total }}GB</span></div>
  <div class="card-b">
    <div class="bar-wrap">
      <div class="bar {{ 'bar-r' if disk_pct>90 else ('bar-y' if disk_pct>75 else 'bar-g') }}" style="width:{{ disk_pct }}%"></div>
    </div>
  </div>
</div>

<div class="card">
  <div class="card-h">
    <h3>Camera Status</h3>
    <a href="/cameras" class="btn btn-s btn-sm">Manage Cameras</a>
  </div>
  {% if cameras %}
  <div class="tbl-wrap"><table>
    <thead><tr>
      <th>Camera</th><th>Status</th><th>Process</th><th>Reachable</th><th>Recent File</th><th>Actions</th>
    </tr></thead>
    <tbody>
    {% for cam in cameras %}
    <tr class="cam-row" data-cam="{{ cam.name }}">
      <td>{{ cam.name }}</td>
      <td data-role="status">
        {% if cam.get('manually_stopped') %}
          <span class="badge bgr"><span class="dot"></span>Paused</span>
        {% elif cam.healthy %}
          <span class="badge bg"><span class="dot"></span>Recording</span>
        {% elif cam.process_running %}
          <span class="badge by"><span class="dot"></span>Starting</span>
        {% else %}
          <span class="badge br"><span class="dot"></span>Stopped</span>
        {% endif %}
      </td>
      <td data-role="process">{% if cam.process_running %}<span class="badge bg">Running</span>{% else %}<span class="badge br">Stopped</span>{% endif %}</td>
      <td data-role="reach">{% if cam.camera_reachable %}<span class="badge bg">Yes</span>{% else %}<span class="badge br">No</span>{% endif %}</td>
      <td data-role="files">{% if cam.recent_files %}<span class="badge bg">Yes</span>{% else %}<span class="badge bgr">None</span>{% endif %}</td>
      <td>
        <div class="btn-grp">
          <span data-role="action">
            {% if cam.process_running or cam.recording %}
              <button class="btn btn-d btn-sm" onclick="camAction('{{ cam.name }}','stop')">Stop</button>
            {% else %}
              <button class="btn btn-p btn-sm" onclick="camAction('{{ cam.name }}','start')">Start</button>
            {% endif %}
          </span>
          <a href="/recordings/{{ cam.name }}/" class="btn btn-s btn-sm">Recordings</a>
        </div>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table></div>
  {% else %}
  <div class="empty">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14.5 4h-5L7 7H4a2 2 0 00-2 2v9a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
    No cameras configured. <a href="/cameras/add" style="color:var(--accent)">Add a camera</a> to get started.
  </div>
  {% endif %}
</div>
<script>
(function(){
  function badge(cls,dot,text){return '<span class="badge '+cls+'">'+(dot?'<span class="dot"></span>':'')+text+'</span>';}
  function statusBadge(cam){
    if(cam.manually_stopped)return badge('bgr',true,'Paused');
    if(cam.healthy)return badge('bg',true,'Recording');
    if(cam.process_running)return badge('by',true,'Starting');
    return badge('br',true,'Stopped');
  }
  function camAction(name,action){
    var btn=document.querySelector('tr[data-cam="'+name+'"] [data-role=action] button');
    if(btn){btn.disabled=true;btn.textContent='...';}
    fetch('/api/cameras/'+name+'/'+action,{method:'POST'})
      .then(function(){setTimeout(updateDash,4000);})
      .catch(function(){if(btn){btn.disabled=false;btn.textContent=action==='stop'?'Stop':'Start';}});
  }
  function updateDash(){
    fetch('/api/status').then(function(r){return r.json();}).then(function(data){
      var healthy=0;
      (data.cameras||[]).forEach(function(cam){
        if(cam.healthy)healthy++;
        var row=document.querySelector('tr[data-cam="'+cam.name+'"]');
        if(!row)return;
        row.querySelector('[data-role=status]').innerHTML=statusBadge(cam);
        row.querySelector('[data-role=process]').innerHTML=cam.process_running?badge('bg',false,'Running'):badge('br',false,'Stopped');
        row.querySelector('[data-role=reach]').innerHTML=cam.camera_reachable?badge('bg',false,'Yes'):badge('br',false,'No');
        row.querySelector('[data-role=files]').innerHTML=cam.recent_files?badge('bg',false,'Yes'):badge('bgr',false,'None');
        var a=row.querySelector('[data-role=action]');
        var running=cam.process_running||cam.recording;
        var b=document.createElement('button');
        b.className='btn '+(running?'btn-d':'btn-p')+' btn-sm';
        b.textContent=running?'Stop':'Start';
        (function(n,ac){b.onclick=function(){camAction(n,ac);};})(cam.name,running?'stop':'start');
        a.innerHTML='';
        a.appendChild(b);
      });
      var h=document.getElementById('stat-healthy');
      if(h){
        h.textContent=healthy;
        var tot=(data.cameras||[]).length;
        h.className='stat-v '+(healthy===tot&&tot>0?'text-green':(healthy===0&&tot>0?'text-red':''));
      }
    }).catch(function(){});
  }
  window.camAction=camAction;
  setInterval(updateDash,8000);
})();
</script>"""

_CAM_LIST = """
<div class="ph">
  <div class="ph-l"><h2>Cameras</h2><p>Manage your camera configurations</p></div>
  <a href="/cameras/add" class="btn btn-p">+ Add Camera</a>
</div>
{% if msg %}<div class="alert alert-s">{{ msg }}</div>{% endif %}
{% if err %}<div class="alert alert-e">{{ err }}</div>{% endif %}
<div class="card">
  <div class="card-h"><h3>Configured Cameras</h3></div>
  {% if cameras %}
  <div class="tbl-wrap"><table>
    <thead><tr>
      <th>Name</th><th>RTSP URL</th><th>Codec</th><th>Interval</th><th>Status</th><th>Actions</th>
    </tr></thead>
    <tbody>
    {% for cam in cameras %}
    <tr>
      <td style="font-weight:500;color:var(--text)">{{ cam.name }}</td>
      <td style="font-family:monospace;font-size:.8em;color:var(--text-muted);max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
          title="{{ cam.rtsp_url }}">{{ cam.rtsp_url }}</td>
      <td>{{ cam.codec }}</td>
      <td>{{ cam.interval }}s</td>
      <td>
        {% if cam.name in live_status %}
          {% set s = live_status[cam.name] %}
          {% if s.healthy %}
            <span class="badge bg"><span class="dot"></span>Recording</span>
          {% elif s.process_running %}
            <span class="badge by"><span class="dot"></span>Starting</span>
          {% else %}
            <span class="badge br"><span class="dot"></span>Stopped</span>
          {% endif %}
        {% else %}
          <span class="badge bgr">Not started</span>
        {% endif %}
      </td>
      <td>
        <div class="btn-grp">
          <a href="/cameras/{{ cam.name }}/edit" class="btn btn-s btn-sm">Edit</a>
          <form method="post" action="/cameras/{{ cam.name }}/delete" style="display:inline"
                onsubmit="return confirm('Delete camera {{ cam.name }}? This only removes the configuration, recordings are kept.')">
            <button type="submit" class="btn btn-d btn-sm">Delete</button>
          </form>
        </div>
      </td>
    </tr>
    {% endfor %}
    </tbody>
  </table></div>
  {% else %}
  <div class="empty">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14.5 4h-5L7 7H4a2 2 0 00-2 2v9a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
    No cameras yet. <a href="/cameras/add" style="color:var(--accent)">Add your first camera</a>.
  </div>
  {% endif %}
</div>"""

_CAM_FORM = """
<div class="ph">
  <div class="ph-l">
    <h2>{{ 'Edit Camera' if edit_mode else 'Add Camera' }}</h2>
    <p>{{ 'Update the configuration for ' + cam_name if edit_mode else 'Configure a new RTSP camera stream' }}</p>
  </div>
</div>
<div class="bc">
  <a href="/cameras">Cameras</a> &rsaquo;
  <span>{{ 'Edit: ' + cam_name if edit_mode else 'Add Camera' }}</span>
</div>
{% if err %}<div class="alert alert-e">{{ err }}</div>{% endif %}
<div class="card">
  <div class="card-h"><h3>Camera Settings</h3></div>
  <div class="card-b">
    <form method="post">
      <div class="fg">
        <label>Camera Name *</label>
        <input type="text" name="name" value="{{ form.name }}" placeholder="e.g. frontdoor"
               {% if edit_mode %}readonly{% endif %} required>
        <div class="fhint">Alphanumeric, dashes and underscores only. Used as the folder name for recordings.</div>
      </div>
      <div class="fg">
        <label>RTSP URL *</label>
        <input type="text" name="rtsp_url" value="{{ form.rtsp_url }}"
               placeholder="rtsp://user:pass@192.168.1.10:554/stream1" required>
        <div class="fhint">Full RTSP stream URL including credentials if required.</div>
      </div>
      <div class="fr">
        <div class="fg">
          <label>Video Codec</label>
          <select name="codec">
            {% for c in ['copy','h264','h265','hevc','libx264','libx265'] %}
            <option value="{{ c }}" {{ 'selected' if form.codec == c else '' }}>{{ c }}</option>
            {% endfor %}
          </select>
          <div class="fhint"><strong>copy</strong> = no re-encoding (recommended)</div>
        </div>
        <div class="fg">
          <label>Segment Interval (seconds)</label>
          <input type="number" name="interval" value="{{ form.interval }}" min="60" max="3600">
          <div class="fhint">How long each video segment is. Minimum 60 seconds.</div>
        </div>
      </div>
      <hr class="div">
      <div class="btn-grp">
        <button type="submit" class="btn btn-p">{{ 'Save Changes' if edit_mode else 'Add Camera' }}</button>
        <a href="/cameras" class="btn btn-s">Cancel</a>
      </div>
    </form>
  </div>
</div>"""

_SETTINGS = """
<div class="ph">
  <div class="ph-l"><h2>Settings</h2><p>Configure global recording and retention options</p></div>
</div>
{% if msg %}<div class="alert alert-s">{{ msg }}</div>{% endif %}
{% if err %}<div class="alert alert-e">{{ err }}</div>{% endif %}
<div class="card">
  <div class="card-h"><h3>Recording Settings</h3></div>
  <div class="card-b">
    <form method="post">
      <div class="fg">
        <label>Retention Period (days)</label>
        <input type="number" name="retention_days" value="{{ cfg.retention_days }}" min="1" max="365">
        <div class="fhint">Recordings older than this many days will be automatically deleted.</div>
      </div>
      <hr class="div">
      <h4 style="font-size:.875em;color:var(--text-muted);font-weight:600;margin-bottom:14px;text-transform:uppercase;letter-spacing:.04em">Daily Concatenation</h4>
      <div class="cb">
        <input type="checkbox" id="concat" name="concatenation" {{ 'checked' if cfg.concatenation else '' }}>
        <label for="concat">Enable daily video concatenation</label>
      </div>
      <div class="fhint" style="margin-top:-10px;margin-bottom:14px">Merges all segments from the previous day into a single file.</div>
      <div class="fr">
        <div class="fg">
          <label>Concatenation Time</label>
          <input type="text" name="concatenation_time" value="{{ cfg.concatenation_time }}" placeholder="02:00">
          <div class="fhint">Time to run daily concatenation (HH:MM, 24-hour format).</div>
        </div>
        <div class="fg">
          <label>Cleanup Time</label>
          <input type="text" name="deletion_time" value="{{ cfg.deletion_time }}" placeholder="01:00">
          <div class="fhint">Time to run daily cleanup of old recordings (HH:MM).</div>
        </div>
      </div>
      <hr class="div">
      <button type="submit" class="btn btn-p">Save Settings</button>
    </form>
  </div>
</div>

<div class="card" style="margin-top:18px">
  <div class="card-h"><h3>Change Password</h3></div>
  <div class="card-b">
    {% if pw_msg %}<div class="alert alert-s">{{ pw_msg }}</div>{% endif %}
    {% if pw_err %}<div class="alert alert-e">{{ pw_err }}</div>{% endif %}
    <form method="post" action="/settings/change_password">
      <div class="fg">
        <label>Current Password</label>
        <input type="password" name="current_password" required autocomplete="current-password">
      </div>
      <div class="fr">
        <div class="fg">
          <label>New Password</label>
          <input type="password" name="new_password" required autocomplete="new-password" minlength="6">
          <div class="fhint">Minimum 6 characters.</div>
        </div>
        <div class="fg">
          <label>Confirm New Password</label>
          <input type="password" name="confirm_password" required autocomplete="new-password">
        </div>
      </div>
      <button type="submit" class="btn btn-b">Change Password</button>
    </form>
    <hr class="div">
    <p style="font-size:.75em;color:var(--text-muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px">Locked Out?</p>
    <p style="font-size:.82em;color:var(--text-dim);margin-bottom:10px">If you cannot log in, use the Forgot Password link on the login page. The reset key is written to the container filesystem — read it with:</p>
    <code style="display:block;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:9px 12px;font-size:.78em;color:var(--text-muted);font-family:monospace">docker exec &lt;container_name&gt; cat /config/password_reset.key</code>
  </div>
</div>"""

_RECORDINGS = """
<div class="ph">
  <div class="ph-l"><h2>Recordings</h2><p>Browse recorded footage by camera</p></div>
</div>
{% if cameras %}
<div class="cl">
  {% for cam in cameras %}
  <a href="/recordings/{{ cam }}/">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14.5 4h-5L7 7H4a2 2 0 00-2 2v9a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
    {{ cam }}
  </a>
  {% endfor %}
</div>
{% else %}
<div class="empty">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
  No recordings found. Cameras need to be recording to see footage here.
</div>
{% endif %}"""

_DATE_LIST = """
<div class="bc">
  <a href="/recordings">Recordings</a> &rsaquo; <span>{{ camera }}</span>
</div>
<div class="ph">
  <div class="ph-l"><h2>{{ camera }}</h2><p>Select a date to view recordings</p></div>
</div>
{% if dates %}
<div class="date-grid">
  {% for date in dates %}
  <a href="/recordings/{{ camera }}/{{ date }}/" class="date-card">{{ date }}</a>
  {% endfor %}
</div>
{% else %}
<div class="empty">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
  No recordings available for this camera yet.
</div>
{% endif %}"""

_VIDEO_LIST = """
<div class="bc">
  <a href="/recordings">Recordings</a> &rsaquo;
  <a href="/recordings/{{ camera }}/">{{ camera }}</a> &rsaquo;
  <span>{{ date }}</span>
</div>
<div class="ph">
  <div class="ph-l"><h2>{{ camera }} – {{ date }}</h2><p>{{ videos|length }} recording{{ 's' if videos|length != 1 else '' }}</p></div>
</div>
{% if videos %}
<div class="vgrid">
  {% for video in videos %}
  <a href="/recordings/{{ camera }}/{{ date }}/{{ video }}" class="vc">
    <div class="vc-t">Recording {{ loop.index }}</div>
    <div class="vc-s">
      {% set parts = video.split('_') %}
      {% if parts|length >= 2 %}{{ parts[1].split('.')[0].replace('-', ':') }}{% endif %}
    </div>
    <div class="vc-f">{{ video }}</div>
  </a>
  {% endfor %}
</div>
{% else %}
<div class="empty">
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
  No recordings for this date yet.
</div>
{% endif %}"""

_VIDEO_PLAYER = """
<div class="bc">
  <a href="/recordings">Recordings</a> &rsaquo;
  <a href="/recordings/{{ camera }}/">{{ camera }}</a> &rsaquo;
  <a href="/recordings/{{ camera }}/{{ date }}/">{{ date }}</a> &rsaquo;
  <span>{{ video }}</span>
</div>
<div class="ph">
  <div class="ph-l">
    <h2>{{ video }}</h2>
    <p>{{ camera }} &middot; {{ date }}</p>
  </div>
  <a href="/recordings/{{ camera }}/{{ date }}/" class="btn btn-s">&larr; Back</a>
</div>
<video controls autoplay preload="metadata">
  <source src="/video/{{ camera }}/{{ date }}/{{ video }}">
  Your browser does not support this video format.
</video>"""

_LOGIN_TPL = """
<div class="lw">
  <div class="lb">
    <h1>OneNVR</h1>
    <p class="sub">{{ 'Create your login credentials' if setup else ('Reset your password' if reset_key_form else 'Network Video Recorder') }}</p>
    {% if err %}<div class="alert alert-e">{{ err }}</div>{% endif %}
    {% if ok %}<div class="alert alert-s">{{ ok }}</div>{% endif %}
    {% if reset_mode %}
      <div class="alert alert-s" style="margin-bottom:10px">A reset key has been written to<br><strong>/config/password_reset.key</strong></div>
      <p style="font-size:.78em;color:var(--text-dim);margin-bottom:6px">Read it from your container (admin access required):</p>
      <code style="display:block;background:var(--bg);border:1px solid var(--border-subtle);border-radius:6px;padding:8px 11px;font-size:.72em;color:var(--text-muted);font-family:monospace;margin-bottom:14px;word-break:break-all">docker exec &lt;container&gt; cat /config/password_reset.key</code>
      <a href="/reset_password" class="btn btn-b" style="width:100%;justify-content:center;margin-bottom:10px">I have the reset key</a>
      <a href="/login" class="ll">Back to Login</a>
    {% elif reset_key_form %}
      <form method="post">
        <div class="fg"><label>Reset Key</label><input type="text" name="reset_key" required></div>
        <div class="fg"><label>New Password</label><input type="password" name="new_password" required></div>
        <div class="fg"><label>Confirm New Password</label><input type="password" name="confirm_new_password" required></div>
        <button type="submit" class="btn btn-b">Reset Password</button>
      </form>
      <a href="/login" class="ll">Back to Login</a>
    {% else %}
      <form method="post">
        <div class="fg"><label>Username</label><input type="text" name="username" autocomplete="username" required></div>
        <div class="fg"><label>Password</label><input type="password" name="password" autocomplete="{{ 'new-password' if setup else 'current-password' }}" required></div>
        {% if setup %}
        <div class="fg"><label>Confirm Password</label><input type="password" name="confirm_password" autocomplete="new-password" required></div>
        {% endif %}
        <button type="submit" class="btn btn-b">{{ 'Create Account' if setup else 'Sign In' }}</button>
      </form>
      {% if not setup %}<a href="/forgot_password" class="ll">Forgot password?</a>{% endif %}
    {% endif %}
  </div>
</div>"""


# ── Main factory ─────────────────────────────────────────────────────────────
def create_web_server(nvr_system=None):
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(16)
    app.logger.disabled = True

    auth_file = os.path.join(CONFIG_DIR, 'auth.dat')
    reset_key_file = os.path.join(CONFIG_DIR, 'password_reset.key')

    # ── Security helpers ──────────────────────────────────────────────────────
    def get_safe_path(*parts):
        safe = os.path.normpath(os.path.join(*parts)).lstrip('/')
        if '..' in safe or not safe.startswith('storage/'):
            abort(404)
        return os.path.join('/', safe)

    def _hash(password):
        salt = secrets.token_hex(8)
        h = hashlib.sha256((password + salt).encode()).hexdigest()
        return f"{salt}:{h}"

    def _verify(stored, password):
        salt, hval = stored.split(':', 1)
        return hashlib.sha256((password + salt).encode()).hexdigest() == hval

    def _create_user(username, password):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(auth_file, 'w') as f:
            f.write(f"{username}:{_hash(password)}")

    def _check_auth(username, password):
        try:
            with open(auth_file) as f:
                stored_user, stored_hash = f.read().strip().split(':', 1)
            return username == stored_user and _verify(stored_hash, password)
        except Exception:
            return False

    def login_required(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'authenticated' not in session:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return wrapper

    # ── Config helpers ────────────────────────────────────────────────────────
    def read_config():
        try:
            with open(CONFIG_PATH) as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {'cameras': [], 'retention_days': 7, 'concatenation': True,
                    'concatenation_time': '02:00', 'deletion_time': '01:00'}

    def write_config(config):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        tmp = CONFIG_PATH + '.tmp'
        with open(tmp, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp, CONFIG_PATH)
        logger.info("Configuration saved")

    def validate_time(t):
        return bool(re.match(r'^\d{2}:\d{2}$', t))

    def get_live_status():
        """Get live recorder status dict keyed by camera name."""
        if nvr_system is None:
            return {}
        try:
            with nvr_system._lock:
                result = {}
                for name, r in nvr_system.recorders.items():
                    h = r.get_individual_health()
                    h['manually_stopped'] = r.manually_stopped
                    result[name] = h
                return result
        except Exception:
            return {}

    def get_disk_info():
        try:
            st = shutil.disk_usage(STORAGE_PATH)
            total_gb = round(st.total / 1e9, 1)
            free_gb = round(st.free / 1e9, 1)
            used_gb = round(st.used / 1e9, 1)
            pct = int(st.used / st.total * 100)
            return total_gb, used_gb, free_gb, pct
        except Exception:
            return 0, 0, 0, 0

    # ── Auth routes ───────────────────────────────────────────────────────────
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        setup = not os.path.exists(auth_file)
        err = None
        if request.method == 'POST':
            u = request.form.get('username', '').strip()
            p = request.form.get('password', '')
            if setup:
                cp = request.form.get('confirm_password', '')
                if p != cp:
                    err = "Passwords do not match"
                elif len(p) < 6:
                    err = "Password must be at least 6 characters"
                else:
                    _create_user(u, p)
                    session['authenticated'] = True
                    return redirect(url_for('dashboard'))
            else:
                if _check_auth(u, p):
                    session['authenticated'] = True
                    return redirect(url_for('dashboard'))
                else:
                    err = "Invalid username or password"
        return _rl(_LOGIN_TPL, "Login", setup=setup, err=err, ok=None,
                   reset_mode=False, reset_key_form=False)

    @app.route('/logout')
    def logout():
        session.pop('authenticated', None)
        return redirect(url_for('login'))

    @app.route('/forgot_password')
    def forgot_password():
        reset_key = secrets.token_hex(16)
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(reset_key_file, 'w') as f:
            f.write(reset_key)
        return _rl(_LOGIN_TPL, "Forgot Password", setup=False, err=None, ok=None,
                   reset_mode=True, reset_key_form=False)

    @app.route('/reset_password', methods=['GET', 'POST'])
    def reset_password():
        if not os.path.exists(auth_file):
            return redirect(url_for('login'))
        err = ok = None
        if request.method == 'POST':
            key = request.form.get('reset_key', '')
            pw = request.form.get('new_password', '')
            cp = request.form.get('confirm_new_password', '')
            try:
                with open(reset_key_file) as f:
                    stored_key = f.read().strip()
                if key != stored_key:
                    err = "Invalid reset key"
                elif pw != cp:
                    err = "Passwords do not match"
                elif len(pw) < 6:
                    err = "Password must be at least 6 characters"
                else:
                    with open(auth_file) as f:
                        current_user = f.read().strip().split(':', 1)[0]
                    _create_user(current_user, pw)
                    if os.path.exists(reset_key_file):
                        os.remove(reset_key_file)
                    ok = "Password reset successfully. You can now log in."
            except FileNotFoundError:
                err = "Reset key not found. Please request a new password reset."
        return _rl(_LOGIN_TPL, "Reset Password", setup=False, err=err, ok=ok,
                   reset_mode=False, reset_key_form=True)

    # ── Dashboard ─────────────────────────────────────────────────────────────
    @app.route('/')
    @login_required
    def dashboard():
        live = get_live_status()
        cfg = read_config()
        total_gb, used_gb, free_gb, disk_pct = get_disk_info()
        cams = list(live.values())
        healthy = sum(1 for c in cams if c.get('healthy'))
        return _rp(_DASHBOARD, "Dashboard", "dashboard",
                   cameras=cams, total=len(cams), healthy=healthy,
                   disk_pct=disk_pct, disk_free=free_gb,
                   disk_used=used_gb, disk_total=total_gb,
                   retention=cfg.get('retention_days', 7))

    # ── Camera management ─────────────────────────────────────────────────────
    @app.route('/cameras/add', methods=['GET', 'POST'])
    @login_required
    def cameras_add():
        err = None
        form = {'name': '', 'rtsp_url': '', 'codec': 'copy', 'interval': 300}
        if request.method == 'POST':
            form = {
                'name': request.form.get('name', '').strip(),
                'rtsp_url': request.form.get('rtsp_url', '').strip(),
                'codec': request.form.get('codec', 'copy').strip(),
                'interval': request.form.get('interval', '300').strip(),
            }
            err = _validate_camera(form)
            if err is None:
                cfg = read_config()
                existing = [c['name'] for c in cfg.get('cameras', [])]
                if form['name'] in existing:
                    err = f"A camera named '{form['name']}' already exists."
                else:
                    cfg.setdefault('cameras', []).append({
                        'name': form['name'],
                        'rtsp_url': form['rtsp_url'],
                        'codec': form['codec'],
                        'interval': int(form['interval']),
                    })
                    write_config(cfg)
                    return redirect(url_for('cameras') + '?msg=Camera+added+successfully')
        return _rp(_CAM_FORM, "Add Camera", "cameras",
                   form=form, err=err, edit_mode=False, cam_name='')

    @app.route('/cameras/<name>/edit', methods=['GET', 'POST'])
    @login_required
    def cameras_edit(name):
        cfg = read_config()
        cam = next((c for c in cfg.get('cameras', []) if c['name'] == name), None)
        if cam is None:
            abort(404)
        err = None
        form = dict(cam)
        if request.method == 'POST':
            form = {
                'name': name,  # name is read-only when editing
                'rtsp_url': request.form.get('rtsp_url', '').strip(),
                'codec': request.form.get('codec', 'copy').strip(),
                'interval': request.form.get('interval', '300').strip(),
            }
            err = _validate_camera(form, editing=True)
            if err is None:
                for c in cfg['cameras']:
                    if c['name'] == name:
                        c['rtsp_url'] = form['rtsp_url']
                        c['codec'] = form['codec']
                        c['interval'] = int(form['interval'])
                        break
                write_config(cfg)
                return redirect(url_for('cameras') + '?msg=Camera+updated+successfully')
        return _rp(_CAM_FORM, f"Edit {name}", "cameras",
                   form=form, err=err, edit_mode=True, cam_name=name)

    @app.route('/cameras/<name>/delete', methods=['POST'])
    @login_required
    def cameras_delete(name):
        cfg = read_config()
        original_count = len(cfg.get('cameras', []))
        cfg['cameras'] = [c for c in cfg.get('cameras', []) if c['name'] != name]
        if len(cfg['cameras']) < original_count:
            write_config(cfg)
        return redirect(url_for('cameras') + '?msg=Camera+deleted+successfully')

    def _validate_camera(form, editing=False):
        name = form.get('name', '')
        rtsp = form.get('rtsp_url', '')
        interval = form.get('interval', '')
        if not editing and not re.match(r'^[a-zA-Z0-9_-]+$', name):
            return "Camera name must contain only letters, numbers, dashes and underscores."
        if not rtsp:
            return "RTSP URL is required."
        if not (rtsp.startswith('rtsp://') or rtsp.startswith('rtsps://')):
            return "RTSP URL must start with rtsp:// or rtsps://"
        try:
            if int(interval) < 60:
                return "Segment interval must be at least 60 seconds."
        except (ValueError, TypeError):
            return "Segment interval must be a valid number."
        return None

    # ── Settings ──────────────────────────────────────────────────────────────
    @app.route('/settings', methods=['GET', 'POST'])
    @login_required
    def settings():
        cfg = read_config()
        err = msg = None
        pw_err = request.args.get('pw_err')
        pw_msg = request.args.get('pw_msg')
        if request.method == 'POST':
            retention = request.form.get('retention_days', '').strip()
            concat = 'concatenation' in request.form
            concat_time = request.form.get('concatenation_time', '').strip()
            del_time = request.form.get('deletion_time', '').strip()
            try:
                r = int(retention)
                if r < 1:
                    raise ValueError
            except (ValueError, TypeError):
                err = "Retention period must be a positive integer."
            if not validate_time(concat_time):
                err = "Concatenation time must be in HH:MM format (e.g. 02:00)."
            if not validate_time(del_time):
                err = "Cleanup time must be in HH:MM format (e.g. 01:00)."
            if err is None:
                cfg['retention_days'] = int(retention)
                cfg['concatenation'] = concat
                cfg['concatenation_time'] = concat_time
                cfg['deletion_time'] = del_time
                write_config(cfg)
                msg = "Settings saved. Changes will take effect within a few seconds."
                cfg = read_config()
        return _rp(_SETTINGS, "Settings", "settings", cfg=cfg, err=err, msg=msg,
                   pw_err=pw_err, pw_msg=pw_msg)

    # ── Recordings browser ────────────────────────────────────────────────────
    @app.route('/recordings')
    @login_required
    def recordings():
        try:
            cams = sorted(
                d for d in os.listdir(STORAGE_PATH)
                if os.path.isdir(os.path.join(STORAGE_PATH, d))
            )
        except Exception:
            cams = []
        return _rp(_RECORDINGS, "Recordings", "recordings", cameras=cams)

    @app.route('/recordings/<camera>/')
    @login_required
    def rec_camera(camera):
        path = get_safe_path(STORAGE_PATH, camera)
        try:
            dates = sorted(
                [d for d in os.listdir(path)
                 if os.path.isdir(os.path.join(path, d))],
                key=lambda x: datetime.strptime(x, '%Y-%m-%d'),
                reverse=True
            )
        except Exception:
            dates = []
        return _rp(_DATE_LIST, camera, "recordings", camera=camera, dates=dates)

    @app.route('/recordings/<camera>/<date>/')
    @login_required
    def rec_date(camera, date):
        path = get_safe_path(STORAGE_PATH, camera, date)
        try:
            videos = sorted(
                [v for v in os.listdir(path) if v.endswith('.mkv')]
            )
        except Exception:
            videos = []
        return _rp(_VIDEO_LIST, f"{camera} – {date}", "recordings",
                   camera=camera, date=date, videos=videos)

    @app.route('/recordings/<camera>/<date>/<video>')
    @login_required
    def rec_video(camera, date, video):
        path = get_safe_path(STORAGE_PATH, camera, date, video)
        if not os.path.isfile(path):
            abort(404)
        return _rp(_VIDEO_PLAYER, video, "recordings",
                   camera=camera, date=date, video=video)

    @app.route('/video/<path:filename>')
    @login_required
    def serve_video(filename):
        safe_path = get_safe_path(STORAGE_PATH, filename)
        return send_from_directory(os.path.dirname(safe_path),
                                   os.path.basename(safe_path))

    # ── API ───────────────────────────────────────────────────────────────────
    @app.route('/api/status')
    @login_required
    def api_status():
        live = get_live_status()
        total_gb, used_gb, free_gb, disk_pct = get_disk_info()
        return jsonify({
            'cameras': list(live.values()),
            'disk': {'total_gb': total_gb, 'used_gb': used_gb,
                     'free_gb': free_gb, 'used_pct': disk_pct},
            'timestamp': datetime.now().isoformat(),
        })

    # ── Static & misc ─────────────────────────────────────────────────────────
    @app.route('/favicon.ico')
    def favicon():
        return send_from_directory(os.path.join(app.root_path, 'static'),
                                   'favicon.ico', mimetype='image/vnd.microsoft.icon')

    @app.route('/cameras')
    @login_required
    def cameras():
        cfg = read_config()
        live = get_live_status()
        msg = request.args.get('msg')
        return _rp(_CAM_LIST, "Cameras", "cameras",
                   cameras=cfg.get('cameras', []),
                   live_status=live, msg=msg, err=None)

    # ── Camera control API ────────────────────────────────────────────────────
    @app.route('/api/cameras/<name>/start', methods=['POST'])
    @login_required
    def api_camera_start(name):
        if nvr_system is None:
            return jsonify({'error': 'NVR system not available'}), 503
        with nvr_system._lock:
            recorder = nvr_system.recorders.get(name)
        if recorder is None:
            return jsonify({'error': 'Camera not found'}), 404
        # Run in background — start() does a connectivity check (up to 3s)
        threading.Thread(target=recorder.start, daemon=True).start()
        return jsonify({'ok': True, 'camera': name})

    @app.route('/api/cameras/<name>/stop', methods=['POST'])
    @login_required
    def api_camera_stop(name):
        if nvr_system is None:
            return jsonify({'error': 'NVR system not available'}), 503
        with nvr_system._lock:
            recorder = nvr_system.recorders.get(name)
        if recorder is None:
            return jsonify({'error': 'Camera not found'}), 404
        # Run in background — stop() blocks up to 15s waiting for FFmpeg to exit
        threading.Thread(target=recorder.manual_stop, daemon=True).start()
        return jsonify({'ok': True, 'camera': name})

    # ── Change password ───────────────────────────────────────────────────────
    @app.route('/settings/change_password', methods=['POST'])
    @login_required
    def change_password():
        current = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        try:
            with open(auth_file) as f:
                username, stored_hash = f.read().strip().split(':', 1)
        except Exception:
            return redirect(url_for('settings', pw_err='Could not read auth file'))
        if not _verify(stored_hash, current):
            return redirect(url_for('settings', pw_err='Current password is incorrect'))
        if new_pw != confirm:
            return redirect(url_for('settings', pw_err='New passwords do not match'))
        if len(new_pw) < 6:
            return redirect(url_for('settings', pw_err='Password must be at least 6 characters'))
        _create_user(username, new_pw)
        return redirect(url_for('settings', pw_msg='Password changed successfully'))

    @app.before_request
    def before_request():
        public = {'login', 'logout', 'forgot_password', 'reset_password', 'favicon', 'static'}
        if request.endpoint not in public and 'authenticated' not in session:
            return redirect(url_for('login'))

    logger.info(f"Web interface ready – auth stored in {auth_file}")
    return app
