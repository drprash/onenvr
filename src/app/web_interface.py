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
from onvif_discovery import ONVIFDiscovery

logger = logging.getLogger(__name__)

CONFIG_PATH = '/config/config.yaml'
STORAGE_PATH = '/storage'
CONFIG_DIR = '/config'

# ── CSS ──────────────────────────────────────────────────────────────────────
_CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117;
       color: #e6edf3; min-height: 100vh; display: flex; }
/* Sidebar */
.sb { width: 220px; background: #161b22; border-right: 1px solid #30363d;
      display: flex; flex-direction: column; position: fixed; height: 100vh; z-index: 10; }
.sb-logo { padding: 18px 16px; border-bottom: 1px solid #30363d; }
.sb-logo h1 { font-size: 1.2em; color: #388bfd; font-weight: 700; letter-spacing: -.02em; }
.sb-logo p { font-size: .68em; color: #6e7681; margin-top: 2px; }
.sb-nav { flex: 1; padding: 10px 0; overflow-y: auto; }
.sb-sec { padding: 7px 14px 3px; font-size: .63em; color: #3d444d;
          text-transform: uppercase; letter-spacing: .06em; font-weight: 600; }
.sb-nav a { display: flex; align-items: center; gap: 9px; padding: 8px 12px;
            margin: 1px 6px; border-radius: 6px; color: #7d8590; text-decoration: none;
            font-size: .85em; transition: all .1s; }
.sb-nav a:hover { color: #cdd9e5; background: #1c2128; }
.sb-nav a.active { color: #e6edf3; background: #1c2128; }
.sb-nav a svg { width: 16px; height: 16px; flex-shrink: 0; stroke-width: 1.75; }
.sb-foot { padding: 10px; border-top: 1px solid #30363d; }
.sb-foot a { display: flex; align-items: center; gap: 8px; color: #6e7681; text-decoration: none;
             font-size: .8em; padding: 7px 10px; border-radius: 6px; }
.sb-foot a:hover { color: #7d8590; background: #1c2128; }
/* Main */
.main { margin-left: 220px; flex: 1; padding: 26px 30px; }
/* Page header */
.ph { margin-bottom: 22px; display: flex; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.ph-l h2 { font-size: 1.35em; font-weight: 600; color: #e6edf3; letter-spacing: -.02em; }
.ph-l p { color: #6e7681; font-size: .82em; margin-top: 3px; }
/* Stats row */
.stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
         gap: 12px; margin-bottom: 22px; }
.stat { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 15px; }
.stat-l { font-size: .72em; color: #7d8590; text-transform: uppercase;
          letter-spacing: .05em; font-weight: 600; margin-bottom: 7px; }
.stat-v { font-size: 1.6em; font-weight: 700; color: #e6edf3; }
.stat-s { font-size: .72em; color: #6e7681; margin-top: 2px; }
/* Cards */
.card { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        margin-bottom: 18px; overflow: hidden; }
.card-h { padding: 12px 16px; border-bottom: 1px solid #30363d;
          display: flex; align-items: center; justify-content: space-between; }
.card-h h3 { font-size: .78em; font-weight: 600; color: #7d8590;
             text-transform: uppercase; letter-spacing: .05em; }
.card-b { padding: 16px; }
/* Table */
table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 9px 14px; font-size: .72em; color: #6e7681;
     font-weight: 600; text-transform: uppercase; letter-spacing: .04em;
     border-bottom: 1px solid #30363d; }
td { padding: 11px 14px; font-size: .85em; border-bottom: 1px solid #0d1117;
     color: #cdd9e5; vertical-align: middle; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #1c212844; }
/* Badges */
.badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px;
         border-radius: 20px; font-size: .72em; font-weight: 500; white-space: nowrap; }
.bg { background: #12261e; color: #3fb950; }
.br { background: #2d1217; color: #f85149; }
.by { background: #272115; color: #d29922; }
.bgr { background: #161b22; color: #6e7681; border: 1px solid #30363d; }
.dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; display: inline-block; }
/* Disk bar */
.bar-wrap { background: #0d1117; border-radius: 4px; height: 7px; overflow: hidden; margin-top: 8px; }
.bar { height: 100%; border-radius: 4px; transition: width .3s; }
.bar-g { background: linear-gradient(90deg, #3fb950, #2ea043); }
.bar-y { background: linear-gradient(90deg, #d29922, #b08800); }
.bar-r { background: linear-gradient(90deg, #f85149, #da3633); }
/* Forms */
.fg { margin-bottom: 16px; }
.fg label { display: block; font-size: .8em; color: #7d8590; margin-bottom: 5px; font-weight: 500; }
.fg input[type=text], .fg input[type=password], .fg input[type=number],
.fg select, .fg textarea { width: 100%; padding: 7px 11px; background: #0d1117;
  border: 1px solid #30363d; border-radius: 6px; color: #e6edf3; font-size: .875em; outline: none; }
.fg input:focus, .fg select:focus, .fg textarea:focus
  { border-color: #388bfd; box-shadow: 0 0 0 3px #388bfd1a; }
.fhint { font-size: .73em; color: #6e7681; margin-top: 4px; }
.fr { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.cb { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.cb input[type=checkbox] { width: 16px; height: 16px; cursor: pointer; accent-color: #388bfd; }
.cb label { margin: 0; font-size: .875em; color: #cdd9e5; cursor: pointer; }
/* Buttons */
.btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 15px;
       border-radius: 6px; font-size: .85em; font-weight: 500; cursor: pointer;
       text-decoration: none; border: 1px solid transparent; transition: all .1s; white-space: nowrap; }
.btn-p { background: #238636; border-color: #2ea043; color: #fff; }
.btn-p:hover { background: #2ea043; }
.btn-b { background: #1f6feb; border-color: #388bfd; color: #fff; }
.btn-b:hover { background: #388bfd; }
.btn-s { background: transparent; border-color: #30363d; color: #cdd9e5; }
.btn-s:hover { background: #1c2128; border-color: #6e7681; }
.btn-d { background: transparent; border-color: #6e27234d; color: #f85149; }
.btn-d:hover { background: #2d121744; border-color: #f85149; }
.btn-sm { padding: 4px 10px; font-size: .78em; }
.btn-grp { display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }
/* Alerts */
.alert { padding: 10px 14px; border-radius: 6px; margin-bottom: 14px; font-size: .85em; }
.alert-e { background: #2d121733; border: 1px solid #6e272344; color: #f85149; }
.alert-s { background: #12261e33; border: 1px solid #2ea04344; color: #3fb950; }
/* Breadcrumb */
.bc { display: flex; align-items: center; gap: 5px; font-size: .78em; color: #6e7681;
      margin-bottom: 16px; flex-wrap: wrap; }
.bc a { color: #388bfd; text-decoration: none; }
.bc a:hover { text-decoration: underline; }
/* Recordings */
.date-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 9px; }
.date-card { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
             padding: 13px; text-align: center; text-decoration: none;
             color: #7d8590; font-size: .82em; transition: all .1s; }
.date-card:hover { border-color: #388bfd; color: #388bfd; }
.vgrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 13px; }
.vc { background: #161b22; border: 1px solid #30363d; border-radius: 8px;
      padding: 14px; text-decoration: none; color: inherit; display: block; transition: all .1s; }
.vc:hover { border-color: #388bfd; transform: translateY(-1px); }
.vc-t { font-weight: 600; color: #e6edf3; margin-bottom: 4px; font-size: .9em; }
.vc-s { font-size: .78em; color: #388bfd; margin-bottom: 3px; }
.vc-f { font-size: .7em; color: #3d444d; font-family: monospace; }
.cl a { display: flex; align-items: center; gap: 10px; padding: 11px 14px;
        background: #161b22; border: 1px solid #30363d; border-radius: 8px;
        margin-bottom: 7px; text-decoration: none; color: #388bfd; font-size: .9em; transition: all .1s; }
.cl a:hover { border-color: #388bfd; color: #58a6ff; }
.cl a svg { width: 16px; height: 16px; color: #6e7681; flex-shrink: 0; }
/* Video */
video { width: 100%; border-radius: 6px; background: #000; max-height: 70vh; }
/* Login */
.lw { display: flex; justify-content: center; align-items: center;
      min-height: 100vh; width: 100%; background: #0d1117; }
.lb { width: 360px; background: #161b22; border: 1px solid #30363d;
      border-radius: 12px; padding: 30px; }
.lb h1 { color: #388bfd; font-size: 1.5em; text-align: center;
         margin-bottom: 4px; font-weight: 700; }
.lb .sub { color: #6e7681; text-align: center; font-size: .78em; margin-bottom: 22px; }
.lb .btn { width: 100%; justify-content: center; margin-top: 6px; }
.lb .fg input { width: 100%; }
.ll { display: block; text-align: center; margin-top: 12px; color: #388bfd;
      font-size: .78em; text-decoration: none; }
.ll:hover { text-decoration: underline; }
/* Discovery panel */
.disc-table { width:100%; border-collapse:collapse; font-size:.82em; }
.disc-table th { text-align:left; padding:7px 10px; font-size:.7em; color:#6e7681;
                 font-weight:600; text-transform:uppercase; letter-spacing:.04em;
                 border-bottom:1px solid #30363d; }
.disc-table td { padding:8px 10px; border-bottom:1px solid #0d1117; vertical-align:middle; }
.disc-table tr:last-child td { border-bottom:none; }
.disc-inp { width:100%; padding:4px 8px; background:#0d1117; border:1px solid #30363d;
            border-radius:4px; color:#e6edf3; font-size:.85em; }
.disc-inp:disabled { opacity:.4; cursor:not-allowed; }
/* Empty */
.empty { text-align: center; color: #3d444d; padding: 36px 20px; font-size: .875em; }
.empty svg { width: 44px; height: 44px; margin: 0 auto 10px; display: block; color: #21262d; }
/* Divider */
.div { border: none; border-top: 1px solid #30363d; margin: 18px 0; }
/* Camera status row for dashboard */
.cam-row td:first-child { font-weight: 500; color: #e6edf3; }
@media (max-width: 720px) {
  .sb { width: 54px; }
  .sb-logo h1, .sb-logo p, .sb-nav a span, .sb-sec, .sb-foot span { display: none; }
  .main { margin-left: 54px; padding: 14px; }
  .fr { grid-template-columns: 1fr; }
  .stats { grid-template-columns: repeat(2, 1fr); }
}
"""

# ── Base layout template ──────────────────────────────────────────────────────
_BASE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }} – OneNVR</title><style>""" + _CSS + """</style></head>
<body>
<nav class="sb">
  <div class="sb-logo"><h1>OneNVR</h1><p>Network Video Recorder</p></div>
  <div class="sb-nav">
    <div class="sb-sec">Monitor</div>
    <a href="/" class="{{ 'active' if active=='dashboard' else '' }}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>
      <span>Dashboard</span></a>
    <a href="/recordings" class="{{ 'active' if active=='recordings' else '' }}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
      <span>Recordings</span></a>
    <div class="sb-sec">Configure</div>
    <a href="/cameras" class="{{ 'active' if active=='cameras' else '' }}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14.5 4h-5L7 7H4a2 2 0 00-2 2v9a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
      <span>Cameras</span></a>
    <a href="/settings" class="{{ 'active' if active=='settings' else '' }}">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
      <span>Settings</span></a>
  </div>
  <div class="sb-foot">
    <a href="/logout">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" width="16" height="16"><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
      <span>Logout</span></a>
  </div>
</nav>
<main class="main">{{ body | safe }}</main>
</body></html>"""

_LOGIN_BASE = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ title }} – OneNVR</title><style>""" + _CSS + """</style></head>
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
    <div class="stat-v" id="stat-healthy" style="color:{{ '#3fb950' if healthy==total and total>0 else ('#f85149' if healthy==0 and total>0 else '#e6edf3') }}">{{ healthy }}</div>
    <div class="stat-s">of {{ total }} healthy</div>
  </div>
  <div class="stat">
    <div class="stat-l">Disk Used</div>
    <div class="stat-v" style="color:{{ '#f85149' if disk_pct>90 else ('#d29922' if disk_pct>75 else '#e6edf3') }}">{{ disk_pct }}%</div>
    <div class="stat-s">{{ disk_free }}GB free</div>
  </div>
  <div class="stat">
    <div class="stat-l">Retention</div>
    <div class="stat-v">{{ retention }}</div>
    <div class="stat-s">days</div>
  </div>
</div>

<div class="card">
  <div class="card-h"><h3>Disk Usage</h3><span style="font-size:.78em;color:#6e7681">{{ disk_used }}GB / {{ disk_total }}GB</span></div>
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
  <table>
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
  </table>
  {% else %}
  <div class="empty">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14.5 4h-5L7 7H4a2 2 0 00-2 2v9a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
    No cameras configured. <a href="/cameras/add" style="color:#388bfd">Add a camera</a> to get started.
  </div>
  {% endif %}
</div>
<div class="card" style="margin-top:18px" id="disc-card">
  <div class="card-h">
    <h3>Camera Discovery</h3>
    <button class="btn btn-b btn-sm" onclick="startScan()" id="scan-btn">Discover Cameras</button>
  </div>
  <div class="card-b" id="disc-body">
    <p style="font-size:.82em;color:#6e7681">Click "Discover Cameras" to scan your network for ONVIF cameras.</p>
  </div>
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
      if(h)h.textContent=healthy;
    }).catch(function(){});
  }
  window.camAction=camAction;

  var discCandidates = [];

  function startScan() {
    var btn = document.getElementById('scan-btn');
    var body = document.getElementById('disc-body');
    btn.disabled = true; btn.textContent = 'Scanning...';
    body.innerHTML = '<p style="font-size:.82em;color:#6e7681">Scanning network (this takes 10-15 seconds)...</p>';
    fetch('/api/discovery/scan', {method:'POST'})
      .then(function(r){return r.json();})
      .then(function(data){
        btn.disabled = false; btn.textContent = 'Discover Cameras';
        if(data.status !== 'ok') { body.innerHTML = '<div class="alert alert-e">Scan failed: '+data.error+'</div>'; return; }
        discCandidates = data.candidates;
        renderDiscTable(data.candidates);
      })
      .catch(function(e){ btn.disabled=false; btn.textContent='Discover Cameras';
        body.innerHTML = '<div class="alert alert-e">Scan error: '+e+'</div>'; });
  }

  function renderDiscTable(candidates) {
    var body = document.getElementById('disc-body');
    if(!candidates.length){ body.innerHTML='<div class="empty">No cameras found on network.</div>'; return; }
    var rows = candidates.map(function(c, i){
      var dis = c.already_configured ? 'style="opacity:.5"' : '';
      var credDis = (!c.requires_auth || c.already_configured) ? 'disabled' : '';
      var statusBadge = c.status === 'ok' ? '<span class="badge bg">No auth needed</span>'
        : c.status === 'auth_required' ? '<span class="badge by">Auth required</span>'
        : '<span class="badge br">'+c.status+'</span>';
      return '<tr '+dis+' data-idx="'+i+'">'
        +'<td>'+c.ip+'</td>'
        +'<td>'+c.model+'</td>'
        +'<td>'+statusBadge+'</td>'
        +'<td><input class="disc-inp" id="usr'+i+'" placeholder="username" value="'+(c.username||'')+'" '+credDis+'></td>'
        +'<td><input class="disc-inp" id="pwd'+i+'" type="password" placeholder="password" '+credDis+'></td>'
        +'<td style="font-size:.75em;color:#7d8590;font-family:monospace;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+c.rtsp_url+'</td>'
        +'<td id="val'+i+'">'+( c.status==='ok' ? '<span class="badge bg">Ready</span>' : '' )+'</td>'
        +'</tr>';
    }).join('');
    body.innerHTML = '<table class="disc-table"><thead><tr>'
      +'<th>IP</th><th>Model</th><th>Auth</th><th>Username</th><th>Password</th><th>RTSP URL</th><th>Status</th>'
      +'</tr></thead><tbody>'+rows+'</tbody></table>'
      +'<div class="btn-grp" style="margin-top:12px">'
      +'<button class="btn btn-s" onclick="validateSelected()">Validate Selected</button>'
      +'<button class="btn btn-p" id="add-btn" onclick="addValid()" disabled>Add Valid Cameras</button>'
      +'</div>';
  }

  function validateSelected() {
    var toValidate = discCandidates.map(function(c, i){
      return {ip:c.ip, mac:c.mac, onvif_port:c.onvif_port,
              username:document.getElementById('usr'+i) ? document.getElementById('usr'+i).value : '',
              password:document.getElementById('pwd'+i) ? document.getElementById('pwd'+i).value : '',
              rtsp_url:c.rtsp_url};
    });
    fetch('/api/discovery/validate', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(toValidate)})
      .then(function(r){return r.json();})
      .then(function(results){
        var anyValid = false;
        results.forEach(function(r, i){
          var cell = document.getElementById('val'+i);
          if(!cell) return;
          if(r.valid){ cell.innerHTML='<span class="badge bg">Valid</span>'; anyValid=true;
            discCandidates[i].validated_rtsp = r.rtsp_url;
            discCandidates[i].validated = true;
          } else { cell.innerHTML='<span class="badge br" title="'+r.error+'">Invalid</span>'; }
        });
        var addBtn = document.getElementById('add-btn');
        if(addBtn) addBtn.disabled = !anyValid;
      });
  }

  function addValid() {
    var toAdd = discCandidates.filter(function(c){ return c.validated && !c.already_configured; })
      .map(function(c){
        return {name: c.name || c.ip.replace(/[.]/g,'_'),
                rtsp_url: c.validated_rtsp || c.rtsp_url,
                mac: c.mac, onvif_port: c.onvif_port,
                username: c.username || '', password: c.password || '',
                codec: 'copy', interval: 300};
      });
    if(!toAdd.length) return;
    fetch('/api/discovery/add', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify(toAdd)})
      .then(function(r){return r.json();})
      .then(function(data){
        var msg = 'Added: '+data.added.join(', ')+(data.skipped.length ? ' | Skipped: '+data.skipped.join(', ') : '');
        document.getElementById('disc-body').innerHTML='<div class="alert alert-s">'+msg+'</div>';
      });
  }

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
  <table>
    <thead><tr>
      <th>Name</th><th>RTSP URL</th><th>Codec</th><th>Interval</th><th>Status</th><th>Actions</th>
    </tr></thead>
    <tbody>
    {% for cam in cameras %}
    <tr>
      <td style="font-weight:500;color:#e6edf3">{{ cam.name }}</td>
      <td style="font-family:monospace;font-size:.8em;color:#7d8590;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
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
  </table>
  {% else %}
  <div class="empty">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M14.5 4h-5L7 7H4a2 2 0 00-2 2v9a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2h-3l-2.5-3z"/><circle cx="12" cy="13" r="3"/></svg>
    No cameras yet. <a href="/cameras/add" style="color:#388bfd">Add your first camera</a>.
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
      <h4 style="font-size:.875em;color:#7d8590;font-weight:600;margin-bottom:14px;text-transform:uppercase;letter-spacing:.04em">Daily Concatenation</h4>
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
    <p style="font-size:.75em;color:#7d8590;font-weight:600;text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px">Locked Out?</p>
    <p style="font-size:.82em;color:#6e7681;margin-bottom:10px">If you cannot log in, use the Forgot Password link on the login page. The reset key is written to the container filesystem — read it with:</p>
    <code style="display:block;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:9px 12px;font-size:.78em;color:#7d8590;font-family:monospace">docker exec &lt;container_name&gt; cat /config/password_reset.key</code>
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
      <p style="font-size:.78em;color:#6e7681;margin-bottom:6px">Read it from your container (admin access required):</p>
      <code style="display:block;background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:8px 11px;font-size:.72em;color:#7d8590;font-family:monospace;margin-bottom:14px;word-break:break-all">docker exec &lt;container&gt; cat /config/password_reset.key</code>
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


def write_config_atomic(config: dict, config_path: str = CONFIG_PATH):
    tmp = config_path + '.tmp'
    with open(tmp, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    os.replace(tmp, config_path)
    logger.info("Config written by discovery endpoint")


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

    # ── Discovery API ─────────────────────────────────────────────────────────
    @app.route('/api/discovery/scan', methods=['POST'])
    @login_required
    def discovery_scan():
        cfg = read_config()
        disc_cfg = cfg.get('discovery') or {}
        try:
            disc = ONVIFDiscovery(
                onvif_timeout=disc_cfg.get('onvif_timeout', 5),
                rtsp_probe_timeout=disc_cfg.get('rtsp_probe_timeout', 3)
            )
            candidates = disc.scan()
            existing_macs = {c.get('mac_address', '') for c in cfg.get('cameras', []) if c.get('mac_address')}
            existing_urls = {c['rtsp_url'] for c in cfg.get('cameras', [])}
            for c in candidates:
                if c['mac'] in existing_macs or c['rtsp_url'] in existing_urls:
                    c['already_configured'] = True
                else:
                    c['already_configured'] = False
            return jsonify({'status': 'ok', 'candidates': candidates})
        except Exception as e:
            logger.error(f"Discovery scan failed: {e}")
            return jsonify({'status': 'error', 'error': str(e)}), 500

    @app.route('/api/discovery/validate', methods=['POST'])
    @login_required
    def discovery_validate():
        cfg = read_config()
        disc_cfg = cfg.get('discovery') or {}
        items = request.get_json(force=True) or []
        disc = ONVIFDiscovery(
            onvif_timeout=disc_cfg.get('onvif_timeout', 5),
            rtsp_probe_timeout=disc_cfg.get('rtsp_probe_timeout', 3)
        )
        results = []
        for item in items:
            try:
                result = disc.validate_credential(
                    ip=item['ip'],
                    mac=item.get('mac', ''),
                    onvif_port=item.get('onvif_port', 80),
                    username=item.get('username', ''),
                    password=item.get('password', ''),
                    rtsp_url=item['rtsp_url']
                )
                result['name'] = item.get('name', item['ip'])
                results.append(result)
            except Exception as e:
                results.append({'name': item.get('name', item['ip']),
                                'valid': False, 'error': str(e), 'rtsp_url': ''})
        return jsonify(results)

    @app.route('/api/discovery/add', methods=['POST'])
    @login_required
    def discovery_add():
        items = request.get_json(force=True) or []
        cfg = read_config()
        # Merge in any cameras already tracked by the live nvr_system
        if nvr_system is not None and hasattr(nvr_system, 'config'):
            live_cameras = nvr_system.config.get('cameras', [])
            cfg_macs = {c.get('mac_address', '') for c in cfg.get('cameras', []) if c.get('mac_address')}
            cfg_urls = {c.get('rtsp_url', '') for c in cfg.get('cameras', [])}
            for cam in live_cameras:
                mac = cam.get('mac_address', '')
                url = cam.get('rtsp_url', '')
                if (mac and mac not in cfg_macs) or (url and url not in cfg_urls):
                    cfg.setdefault('cameras', []).append(cam)
                    if mac:
                        cfg_macs.add(mac)
                    if url:
                        cfg_urls.add(url)

        existing_macs = {c.get('mac_address', '') for c in cfg['cameras'] if c.get('mac_address')}
        existing_urls = {c['rtsp_url'] for c in cfg['cameras']}

        added = []
        skipped = []
        for item in items:
            mac = item.get('mac', '')
            rtsp_url = item.get('rtsp_url', '')
            if mac and mac in existing_macs:
                skipped.append(item['name'])
                continue
            if rtsp_url in existing_urls:
                skipped.append(item['name'])
                continue
            import re as _re
            safe_name = _re.sub(r'[^a-zA-Z0-9_-]', '', str(item.get('name', '')))
            if not safe_name:
                safe_name = item.get('ip', 'camera').replace('.', '_')
            cfg['cameras'].append({
                'name': safe_name,
                'rtsp_url': rtsp_url,
                'mac_address': mac,
                'onvif_port': item.get('onvif_port', 80),
                'username': item.get('username', ''),
                'password': item.get('password', ''),
                'codec': item.get('codec', 'copy'),
                'interval': item.get('interval', 300),
            })
            added.append(item['name'])
            if mac:
                existing_macs.add(mac)
            existing_urls.add(rtsp_url)

        if added:
            write_config_atomic(cfg)
        return jsonify({'added': added, 'skipped': skipped})

    logger.info(f"Web interface ready – auth stored in {auth_file}")
    return app
