from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, redirect, render_template_string, request, url_for

from vectrion.config_store import (
    get_stage_name,
    get_stage_order,
    is_setup_complete,
    load_config,
    save_config,
)
from vectrion.constants import DEFAULT_STAGES, LEGAL_DISCLAIMER
from vectrion.runbook import next_layer, run_layer
from vectrion.storage import Storage

# ─────────────────────────────────────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """<style>
:root {
  --navy:        #08121F;
  --navy-2:      #0F1E33;
  --navy-3:      #1A3050;
  --navy-4:      #22406A;
  --blue:        #1D4ED8;
  --blue-2:      #2563EB;
  --blue-light:  #3B82F6;
  --blue-glow:   rgba(59,130,246,0.22);
  --silver:      #8899B0;
  --silver-2:    #A8BAD0;
  --silver-3:    #CBD5E1;
  --silver-pale: #E2EAF4;
  --bg:          #EEF3FA;
  --white:       #FFFFFF;
  --text:        #0D1826;
  --muted:       #5A6F88;
  --border:      #CDD8E8;
  --success:     #059669;
  --danger:      #DC2626;
  --warn:        #D97706;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', system-ui, Arial, sans-serif; background: var(--bg); color: var(--text); font-size: 14px; line-height: 1.55; }

/* ── TOPBAR ── */
.topbar {
  display: flex; align-items: center;
  background: var(--navy); border-bottom: 1px solid var(--navy-3);
  height: 56px; padding: 0 28px;
  position: sticky; top: 0; z-index: 200;
  box-shadow: 0 2px 16px rgba(0,0,0,0.4);
}
.topbar-brand { display:flex; align-items:center; gap:12px; text-decoration:none; }
.tb-icon {
  width:36px; height:36px; border-radius:9px;
  background: linear-gradient(135deg,var(--blue-light),var(--blue));
  display:flex; align-items:center; justify-content:center;
  font-size:19px; box-shadow: 0 0 14px var(--blue-glow);
}
.tb-name  { font-size:17px; font-weight:800; letter-spacing:2.5px; color:var(--white); }
.tb-sub   { font-size:9px; letter-spacing:2.5px; color:var(--silver); text-transform:uppercase; margin-top:1px; }
.tb-div   { width:1px; height:30px; background:var(--navy-3); margin:0 20px; }
nav { margin-left:auto; display:flex; align-items:center; gap:4px; }
nav a {
  color:var(--silver-2); text-decoration:none; font-size:12px; font-weight:600;
  padding:6px 16px; border-radius:6px; letter-spacing:0.8px;
  text-transform:uppercase; transition:all 0.15s; border:1px solid transparent;
}
nav a:hover { background:rgba(255,255,255,0.07); color:var(--white); border-color:var(--navy-3); }
nav a.active { background:var(--navy-3); color:var(--white); border-color:var(--blue); }

/* ── SPLIT LAYOUT (pages with robot panel) ── */
.split-wrap { display:flex; min-height:calc(100vh - 56px); }
.split-main { flex:1; min-width:0; padding:28px 32px 60px; }
.split-panel {
  width:320px; flex-shrink:0;
  background:var(--navy); border-left:1px solid var(--navy-3);
  display:flex; flex-direction:column;
  height:calc(100vh - 56px); position:sticky; top:56px;
  overflow:hidden;
}

/* ── FULL PAGE WRAPPER (no panel) ── */
.page { max-width:1100px; margin:32px auto; padding:0 28px 60px; }

/* ── CARDS ── */
.card {
  background:var(--white); border:1px solid var(--border); border-radius:12px;
  padding:22px 26px; margin-bottom:20px;
  box-shadow:0 2px 10px rgba(10,22,40,0.07);
}
.card-title {
  font-size:11px; font-weight:700; text-transform:uppercase;
  letter-spacing:1.5px; color:var(--navy-4);
  padding-bottom:14px; margin-bottom:18px;
  border-bottom:1px solid var(--silver-pale);
  display:flex; align-items:center; gap:8px;
}

/* ── BUTTONS ── */
.btn {
  display:inline-flex; align-items:center; gap:6px;
  padding:9px 20px; font-size:13px; font-weight:600;
  border-radius:7px; border:none; cursor:pointer;
  text-decoration:none; transition:all 0.15s; letter-spacing:0.3px;
}
.btn-primary { background:var(--blue); color:#fff; box-shadow:0 2px 8px rgba(29,78,216,0.3); }
.btn-primary:hover { background:#1a44c4; box-shadow:0 4px 14px rgba(29,78,216,0.45); transform:translateY(-1px); }
.btn-secondary { background:var(--white); color:var(--text); border:1px solid var(--border); }
.btn-secondary:hover { background:var(--bg); border-color:var(--silver); }
.btn-danger { background:var(--danger); color:#fff; }
.btn-danger:hover { background:#b91c1c; }
.btn-ghost { background:transparent; color:var(--silver); border:none; cursor:pointer; padding:4px 8px; border-radius:5px; font-size:16px; }
.btn-ghost:hover { color:var(--white); background:rgba(255,255,255,0.08); }
.btn-sm { padding:5px 12px; font-size:12px; }
.btn-action {
  display:inline-flex; align-items:center; gap:5px;
  padding:7px 14px; font-size:12px; font-weight:600;
  background:var(--navy-3); color:var(--silver-3);
  border:1px solid var(--navy-4); border-radius:6px;
  cursor:pointer; text-decoration:none; transition:all 0.15s;
  margin-top:6px; margin-right:4px;
}
.btn-action:hover { background:var(--blue); color:#fff; border-color:var(--blue); }

/* ── FORM ELEMENTS ── */
label { font-size:11px; font-weight:700; color:var(--muted); text-transform:uppercase; letter-spacing:0.8px; display:block; margin-bottom:5px; }
input[type=text], input[type=number], select, textarea {
  width:100%; padding:9px 12px; border:1px solid var(--border); border-radius:7px;
  font-size:13px; background:var(--white); color:var(--text); transition:all 0.15s;
}
input[type=text]:focus, input[type=number]:focus, select:focus, textarea:focus {
  outline:none; border-color:var(--blue-light); box-shadow:0 0 0 3px rgba(59,130,246,0.14);
}

/* ── TABLES ── */
table { border-collapse:collapse; width:100%; }
thead th {
  background:var(--navy); color:var(--silver-2);
  font-size:10px; font-weight:700; letter-spacing:1.5px; text-transform:uppercase;
  padding:10px 14px; text-align:left;
}
thead th:first-child { border-radius:8px 0 0 0; }
thead th:last-child  { border-radius:0 8px 0 0; }
tbody td { padding:11px 14px; border-bottom:1px solid var(--silver-pale); vertical-align:middle; }
tbody tr:hover td { background:#F2F7FF; }
tbody tr:last-child td { border-bottom:none; }

/* ── BADGES / PILLS ── */
.badge { display:inline-flex; align-items:center; padding:3px 10px; border-radius:999px; font-size:11px; font-weight:600; letter-spacing:0.5px; }
.badge-blue   { background:#DBEAFE; color:#1D4ED8; }
.badge-green  { background:#D1FAE5; color:#065F46; }
.badge-silver { background:var(--silver-pale); color:var(--muted); }
.badge-warn   { background:#FEF3C7; color:#92400E; }
.stage-pill {
  display:inline-flex; align-items:center; gap:5px;
  padding:4px 12px; border-radius:999px; font-size:11px; font-weight:600;
  background:var(--silver-pale); color:var(--muted); margin:3px; border:1px solid var(--border);
}
.stage-pill.done    { background:#D1FAE5; color:#065F46; border-color:#A7F3D0; }
.stage-pill.current { background:#DBEAFE; color:#1E40AF; border-color:#93C5FD; font-weight:700; }

/* ── PRE ── */
pre {
  background:var(--navy); color:#A8C8E8; padding:16px 18px; border-radius:9px;
  white-space:pre-wrap; max-height:440px; overflow:auto;
  font-size:12px; line-height:1.75; border:1px solid var(--navy-3);
}

/* ── MISC ── */
.muted { color:var(--muted); font-size:13px; }
.disclaimer { font-size:11px; color:var(--muted); border-top:1px solid var(--border); padding-top:14px; margin-top:8px; }
.wizard-steps { display:flex; margin-bottom:28px; }
.wizard-step { flex:1; text-align:center; padding:12px; font-size:13px; font-weight:600; background:var(--white); border:1px solid var(--border); color:var(--muted); }
.wizard-step:first-child { border-radius:8px 0 0 8px; }
.wizard-step:last-child  { border-radius:0 8px 8px 0; }
.wizard-step.active { background:var(--blue); color:#fff; border-color:var(--blue); }
.wizard-step.done   { background:#D1FAE5; color:#065F46; border-color:#A7F3D0; }
a.plain { color:var(--blue); text-decoration:none; font-weight:500; }
a.plain:hover { text-decoration:underline; }

/* ─────────────────────────────────────
   ROBOT PANEL
───────────────────────────────────── */
.robot-header {
  padding:20px 16px 14px;
  background:var(--navy-2);
  border-bottom:1px solid var(--navy-3);
  display:flex; flex-direction:column; align-items:center; gap:10px;
}
/* Robot head */
.robot-wrap { position:relative; width:76px; height:88px; display:flex; flex-direction:column; align-items:center; }
.robot-antenna-stem {
  width:3px; height:14px; background:var(--silver);
  border-radius:2px; margin-bottom:0; flex-shrink:0;
}
.robot-antenna-tip {
  width:10px; height:10px; border-radius:50%;
  background:var(--blue-light);
  box-shadow:0 0 10px var(--blue-light), 0 0 20px var(--blue-glow);
  position:absolute; top:0; left:50%; transform:translateX(-50%);
  animation:antennaPulse 2.4s ease-in-out infinite;
}
.robot-neck { width:18px; height:6px; background:var(--navy-3); border-radius:2px; }
.robot-face {
  width:72px; height:60px; background:var(--navy-2);
  border:2px solid var(--navy-4); border-radius:12px;
  display:flex; flex-direction:column; align-items:center; justify-content:center; gap:9px;
  box-shadow:0 0 20px rgba(59,130,246,0.12), inset 0 1px 0 rgba(255,255,255,0.05);
  position:relative; overflow:hidden;
}
.robot-face::before {
  content:''; position:absolute; top:0; left:0; right:0; height:1px;
  background:linear-gradient(90deg,transparent,var(--blue-light),transparent);
  opacity:0.6;
}
.robot-eyes { display:flex; gap:16px; }
.robot-eye {
  width:13px; height:13px; border-radius:50%;
  background:var(--blue-light);
  box-shadow:0 0 8px var(--blue-light), 0 0 18px var(--blue-glow);
  animation:eyeBlink 5s ease-in-out infinite;
}
.robot-eye:nth-child(2) { animation-delay:0.08s; }
.robot-mouth {
  width:38px; height:7px; border-radius:3px;
  background:repeating-linear-gradient(90deg, var(--silver) 0, var(--silver) 4px, transparent 4px, transparent 8px);
  opacity:0.7;
}
.robot-ear {
  position:absolute; top:50%; transform:translateY(-50%);
  width:5px; height:20px; border-radius:2px;
  background:var(--navy-4); border:1px solid var(--navy-3);
}
.robot-ear.left  { left:-6px; }
.robot-ear.right { right:-6px; }
@keyframes antennaPulse {
  0%,100% { opacity:1; box-shadow:0 0 10px var(--blue-light),0 0 20px var(--blue-glow); }
  50%      { opacity:0.4; box-shadow:0 0 4px var(--blue-light); }
}
@keyframes eyeBlink {
  0%,90%,100% { transform:scaleY(1); }
  94%,97%     { transform:scaleY(0.08); }
}

.robot-name { font-size:13px; font-weight:800; letter-spacing:2px; color:var(--white); text-transform:uppercase; }
.robot-status { display:flex; align-items:center; gap:6px; font-size:10px; color:#22C55E; letter-spacing:1px; text-transform:uppercase; }
.robot-status-dot { width:7px; height:7px; border-radius:50%; background:#22C55E; box-shadow:0 0 6px #22C55E; animation:statusPulse 2s infinite; }
@keyframes statusPulse {
  0%,100% { opacity:1; } 50% { opacity:0.4; }
}

/* Panel messages */
.panel-messages {
  flex:1; overflow-y:auto; padding:14px;
  display:flex; flex-direction:column; gap:10px;
  scroll-behavior:smooth;
}
.panel-messages::-webkit-scrollbar { width:4px; }
.panel-messages::-webkit-scrollbar-track { background:transparent; }
.panel-messages::-webkit-scrollbar-thumb { background:var(--navy-3); border-radius:4px; }

.pmsg { display:flex; gap:8px; align-items:flex-start; }
.pmsg.user { flex-direction:row-reverse; }
.pmsg-av {
  width:26px; height:26px; flex-shrink:0; border-radius:7px;
  background:linear-gradient(135deg,var(--blue-light),var(--blue));
  display:flex; align-items:center; justify-content:center;
  font-size:12px; color:#fff; font-weight:700;
}
.pmsg-av.user { background:var(--navy-3); color:var(--silver-2); font-size:10px; }
.pmsg-content { max-width:82%; display:flex; flex-direction:column; gap:4px; }
.pmsg-bubble {
  padding:9px 13px; border-radius:10px;
  font-size:12px; line-height:1.6;
}
.pmsg-bubble.bot {
  background:rgba(255,255,255,0.06); color:var(--silver-2);
  border:1px solid rgba(255,255,255,0.08); border-top-left-radius:3px;
}
.pmsg-bubble.user {
  background:var(--blue); color:#fff; border-top-right-radius:3px;
}
.pmsg-actions { display:flex; flex-wrap:wrap; gap:4px; padding-left:2px; }

.panel-input-row {
  border-top:1px solid var(--navy-3); padding:12px;
  display:flex; gap:8px; background:var(--navy-2); flex-shrink:0;
}
.panel-input {
  flex:1; background:rgba(255,255,255,0.07) !important;
  border:1px solid rgba(255,255,255,0.12) !important;
  color:var(--white) !important; padding:8px 11px !important;
  border-radius:7px !important; font-size:12px !important;
}
.panel-input::placeholder { color:var(--silver) !important; }
.panel-input:focus { border-color:var(--blue-light) !important; box-shadow:0 0 0 2px rgba(59,130,246,0.2) !important; }
.panel-send {
  background:var(--blue); color:#fff; border:none;
  border-radius:7px; padding:8px 14px; font-size:12px; font-weight:600; cursor:pointer;
}
.panel-send:hover { background:#1a44c4; }

/* Typing indicator */
.typing-dots { display:flex; gap:4px; padding:9px 13px; }
.typing-dots span {
  width:6px; height:6px; border-radius:50%; background:var(--silver);
  animation:typingDot 1.2s infinite;
}
.typing-dots span:nth-child(2) { animation-delay:0.2s; }
.typing-dots span:nth-child(3) { animation-delay:0.4s; }
@keyframes typingDot { 0%,60%,100%{opacity:0.2;transform:translateY(0)} 30%{opacity:1;transform:translateY(-4px)} }

/* ─────────────────────────────────────
   WELCOME PAGE
───────────────────────────────────── */
.welcome-wrap {
  min-height:calc(100vh - 56px);
  background:linear-gradient(155deg, var(--navy) 0%, #0D2040 50%, #0A1A30 100%);
  display:flex; align-items:center; justify-content:center; padding:40px 20px;
}
.welcome-inner { width:100%; max-width:800px; display:flex; flex-direction:column; align-items:center; gap:36px; }
.welcome-logo-wrap { text-align:center; }
.welcome-logo {
  width:80px; height:80px; border-radius:20px; margin:0 auto 18px;
  background:linear-gradient(135deg,var(--blue-light),var(--blue));
  display:flex; align-items:center; justify-content:center; font-size:42px;
  box-shadow:0 0 50px rgba(59,130,246,0.4);
}
.welcome-title { font-size:46px; font-weight:900; letter-spacing:6px; color:var(--white); }
.welcome-tag { font-size:11px; letter-spacing:4px; color:var(--silver); text-transform:uppercase; margin-top:8px; }
.welcome-divider { width:60px; height:2px; background:linear-gradient(90deg,transparent,var(--blue-light),transparent); margin:4px auto; }

.welcome-chat-card {
  width:100%;
  background:rgba(255,255,255,0.04);
  border:1px solid rgba(255,255,255,0.1);
  border-radius:18px; overflow:hidden; backdrop-filter:blur(10px);
  box-shadow:0 12px 60px rgba(0,0,0,0.5);
}
.welcome-chat-header {
  background:rgba(255,255,255,0.04); border-bottom:1px solid rgba(255,255,255,0.08);
  padding:14px 20px; display:flex; align-items:center; gap:12px;
  color:var(--silver-2); font-size:13px; font-weight:700; letter-spacing:0.5px;
}
.wch-dot { width:8px; height:8px; border-radius:50%; background:#22C55E; box-shadow:0 0 8px #22C55E; }
.wch-right { margin-left:auto; font-size:10px; color:var(--silver); letter-spacing:2px; }
.welcome-messages {
  padding:20px; display:flex; flex-direction:column; gap:14px;
  min-height:240px; max-height:360px; overflow-y:auto; scroll-behavior:smooth;
}
.wmsg { display:flex; gap:12px; align-items:flex-start; }
.wmsg.user { flex-direction:row-reverse; }
.wmsg-av {
  width:36px; height:36px; flex-shrink:0; border-radius:10px;
  background:linear-gradient(135deg,var(--blue-light),var(--blue));
  display:flex; align-items:center; justify-content:center; font-size:18px;
}
.wmsg-av.user { background:var(--navy-3); color:var(--silver-2); font-size:12px; font-weight:700; }
.wmsg-bubble {
  max-width:84%; padding:13px 16px; border-radius:12px;
  font-size:14px; line-height:1.65;
}
.wmsg-bubble.bot { background:rgba(255,255,255,0.07); color:var(--silver-2); border:1px solid rgba(255,255,255,0.08); border-top-left-radius:3px; }
.wmsg-bubble.user { background:var(--blue); color:#fff; border-top-right-radius:3px; }
.welcome-input-row {
  border-top:1px solid rgba(255,255,255,0.08); padding:14px 16px;
  display:flex; gap:10px; background:rgba(255,255,255,0.03);
}
.welcome-input {
  flex:1; background:rgba(255,255,255,0.07) !important;
  border:1px solid rgba(255,255,255,0.12) !important; color:var(--white) !important;
  border-radius:9px !important;
}
.welcome-input::placeholder { color:var(--silver) !important; }
.welcome-input:focus { border-color:var(--blue-light) !important; box-shadow:0 0 0 3px rgba(59,130,246,0.2) !important; }
.btn-enter {
  background:var(--blue); color:#fff; padding:14px 40px;
  font-size:14px; font-weight:700; letter-spacing:1.5px; border-radius:10px;
  text-decoration:none; border:none; cursor:pointer;
  box-shadow:0 4px 24px rgba(29,78,216,0.5); transition:all 0.15s;
}
.btn-enter:hover { background:#1a44c4; box-shadow:0 6px 32px rgba(29,78,216,0.65); transform:translateY(-2px); }
</style>"""

# ─────────────────────────────────────────────────────────────────────────────
# TOPBAR SNIPPET
# ─────────────────────────────────────────────────────────────────────────────

_TOPBAR = """
<div class="topbar">
  <a href="/" class="topbar-brand">
    <div class="tb-icon">&#9670;</div>
    <div><div class="tb-name">VECTORIAN</div><div class="tb-sub">Breach Response Platform</div></div>
  </a>
  <div class="tb-div"></div>
  <nav>
    <a href="/" class="{{ 'active' if active_nav=='dashboard' else '' }}">Dashboard</a>
    <a href="/config" class="{{ 'active' if active_nav=='config' else '' }}">Configuration</a>
  </nav>
</div>"""

# ─────────────────────────────────────────────────────────────────────────────
# ROBOT PANEL (always-open, embedded in split layout)
# ─────────────────────────────────────────────────────────────────────────────

_ROBOT_PANEL = """
<div class="split-panel" id="vectorian-panel">
  <!-- Robot head -->
  <div class="robot-header">
    <div class="robot-wrap">
      <div class="robot-antenna-tip"></div>
      <div style="width:3px;height:14px;background:var(--silver);border-radius:2px;margin-top:10px"></div>
      <div class="robot-neck"></div>
      <div class="robot-face">
        <div class="robot-ear left"></div>
        <div class="robot-ear right"></div>
        <div class="robot-eyes">
          <div class="robot-eye"></div>
          <div class="robot-eye"></div>
        </div>
        <div class="robot-mouth"></div>
      </div>
    </div>
    <div class="robot-name">Vectorian</div>
    <div class="robot-status"><div class="robot-status-dot"></div>AI Agent Online</div>
  </div>

  <!-- Messages -->
  <div class="panel-messages" id="panel-msgs"></div>

  <!-- Input -->
  <div class="panel-input-row">
    <input class="panel-input" id="panel-input" type="text" placeholder="Ask Vectorian anything..." />
    <button class="panel-send" onclick="panelSend()">&#9658;</button>
  </div>
</div>

<script>
(function(){
  const PAGE_KEY = 'vect_panel_' + (document.body.dataset.page || 'default');
  function getH(){ try{return JSON.parse(sessionStorage.getItem(PAGE_KEY)||'[]');}catch{return [];} }
  function saveH(h){ sessionStorage.setItem(PAGE_KEY,JSON.stringify(h)); }

  function renderPanel(){
    const box = document.getElementById('panel-msgs');
    const h = getH();
    box.innerHTML='';
    h.forEach(m=>{
      const wrap=document.createElement('div');
      wrap.className='pmsg '+(m.role==='user'?'user':'');
      const av=document.createElement('div');
      av.className='pmsg-av '+(m.role==='user'?'user':'');
      av.textContent=m.role==='user'?'OP':'V';
      const content=document.createElement('div');
      content.className='pmsg-content';
      const bub=document.createElement('div');
      bub.className='pmsg-bubble '+(m.role==='user'?'user':'bot');
      bub.textContent=m.text;
      content.appendChild(bub);
      if(m.actions && m.actions.length){
        const actRow=document.createElement('div');
        actRow.className='pmsg-actions';
        m.actions.forEach(a=>{
          const btn=document.createElement('a');
          btn.className='btn-action';
          btn.href=a.href;
          btn.textContent='▶ '+a.label;
          actRow.appendChild(btn);
        });
        content.appendChild(actRow);
      }
      wrap.appendChild(av);
      wrap.appendChild(content);
      box.appendChild(wrap);
    });
    box.scrollTop=box.scrollHeight;
  }

  function addMsg(role,text,actions){
    const h=getH();
    h.push({role,text,actions:actions||[]});
    saveH(h);
    renderPanel();
  }

  function showTyping(){
    const box=document.getElementById('panel-msgs');
    const t=document.createElement('div');
    t.id='typing-ind';
    t.className='pmsg';
    t.innerHTML='<div class="pmsg-av">V</div><div class="typing-dots"><span></span><span></span><span></span></div>';
    box.appendChild(t);
    box.scrollTop=box.scrollHeight;
  }
  function hideTyping(){ const t=document.getElementById('typing-ind'); if(t)t.remove(); }

  window.panelSend=function(){
    const inp=document.getElementById('panel-input');
    const msg=inp.value.trim();
    if(!msg)return;
    inp.value='';
    addMsg('user',msg,[]);
    showTyping();
    const iid=document.body.dataset.incidentId||'';
    const payload={message:msg};
    if(iid)payload.incident_id=iid;
    fetch('/api/chat',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    }).then(r=>r.json()).then(d=>{
      hideTyping();
      addMsg('bot',d.reply||'No response.',d.actions||[]);
    }).catch(()=>{hideTyping();addMsg('bot','Unable to reach Vectorian AI. Check your connection.');});
  };

  document.addEventListener('keydown',e=>{
    if(e.key==='Enter'&&document.activeElement===document.getElementById('panel-input'))panelSend();
  });

  // Boot greeting if empty
  if(!getH().length){
    addMsg('bot','Hello, Operator. I\'m Vectorian — your AI breach response agent. I can guide you through the 9-stage workflow, answer compliance questions, and help you configure this platform. What do you need?',[]);
  } else {
    renderPanel();
  }
})();
</script>
"""

# ─────────────────────────────────────────────────────────────────────────────
# WELCOME PAGE
# ─────────────────────────────────────────────────────────────────────────────

WELCOME_TMPL = """<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — Breach Response Platform</title>""" + _CSS + """</head>
<body>""" + _TOPBAR + """
<div class="welcome-wrap">
  <div class="welcome-inner">
    <div class="welcome-logo-wrap">
      <div class="welcome-logo">&#9670;</div>
      <div class="welcome-title">VECTORIAN</div>
      <div class="welcome-divider"></div>
      <div class="welcome-tag">AI-Powered Breach Response Platform</div>
    </div>

    <div class="welcome-chat-card">
      <div class="welcome-chat-header">
        <div class="wch-dot"></div>
        Vectorian AI &mdash; Breach Response Agent
        <span class="wch-right">SECURE CHANNEL</span>
      </div>
      <div class="welcome-messages" id="w-msgs">
        <div class="wmsg">
          <div class="wmsg-av">&#9670;</div>
          <div class="wmsg-bubble bot" id="w-greeting"></div>
        </div>
      </div>
      <div class="welcome-input-row">
        <input class="welcome-input" id="w-input" type="text" placeholder="Ask Vectorian about breach response, stages, compliance..." />
        <button class="btn-enter" style="padding:10px 24px;font-size:13px" onclick="wSend()">Send</button>
      </div>
    </div>

    <a href="{{ enter_url }}" class="btn-enter">&#9654;&nbsp;&nbsp;Enter Platform</a>

    <div style="text-align:center;color:var(--silver);font-size:11px;max-width:620px">{{ disclaimer }}</div>
  </div>
</div>

<script>
const GREETING = `Welcome, Operator.

I am Vectorian — your AI-powered breach response agent.

My purpose is to guide your organization through the complete 9-stage data breach response workflow: from initial scope confirmation and data normalization, through sensitive data classification, impact quantification, regulatory trigger analysis, and all the way to regulatory filings and public disclosure support.

I combine deep breach response knowledge with agentic platform capabilities — I don't just answer questions, I can take action within the platform.

All outputs are draft-only and require human review. How can I assist you today?`;

const WKEY='vect_welcome_v2';
function getWH(){try{return JSON.parse(sessionStorage.getItem(WKEY)||'[]');}catch{return[];}}
function saveWH(h){sessionStorage.setItem(WKEY,JSON.stringify(h));}

function renderW(){
  const box=document.getElementById('w-msgs');
  const h=getWH();
  while(box.children.length>1)box.removeChild(box.lastChild);
  h.forEach(m=>{
    const wrap=document.createElement('div');
    wrap.className='wmsg '+(m.role==='user'?'user':'');
    const av=document.createElement('div');
    av.className='wmsg-av '+(m.role==='user'?'user':'');
    av.textContent=m.role==='user'?'OP':'◆';
    const bub=document.createElement('div');
    bub.className='wmsg-bubble '+(m.role==='user'?'user':'bot');
    bub.textContent=m.text;
    wrap.appendChild(av);wrap.appendChild(bub);
    box.appendChild(wrap);
  });
  box.scrollTop=box.scrollHeight;
}

function wSend(){
  const inp=document.getElementById('w-input');
  const msg=inp.value.trim();
  if(!msg)return;
  inp.value='';
  const h=getWH();h.push({role:'user',text:msg});saveWH(h);renderW();
  fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg})})
    .then(r=>r.json()).then(d=>{
      const h2=getWH();h2.push({role:'bot',text:d.reply||'No response.'});saveWH(h2);renderW();
    }).catch(()=>{const h2=getWH();h2.push({role:'bot',text:'Unable to reach Vectorian AI.'});saveWH(h2);renderW();});
}
document.getElementById('w-input').addEventListener('keydown',e=>{if(e.key==='Enter')wSend();});

// Typewriter
(function(){
  const el=document.getElementById('w-greeting');
  let i=0;
  function tick(){
    if(i<GREETING.length){
      el.textContent+=GREETING[i++];
      document.getElementById('w-msgs').scrollTop=99999;
      setTimeout(tick,i<120?16:5);
    }
  }
  tick();
})();
</script></body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────

INDEX_TMPL = """<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — Dashboard</title>""" + _CSS + """</head>
<body>""" + _TOPBAR + """
<div class="page">
  <div style="margin-bottom:24px">
    <div style="font-size:22px;font-weight:700;color:var(--navy)">Incident Dashboard</div>
    <div class="muted" style="margin-top:3px">Manage and monitor active breach response engagements</div>
  </div>

  <div class="card">
    <div class="card-title">&#43; New Incident</div>
    <form method="post" action="/incidents/create" style="display:flex;gap:14px;align-items:flex-end;flex-wrap:wrap">
      <div style="flex:1;min-width:220px">
        <label>Incident ID</label>
        <input type="text" name="incident_id" id="inc-input" placeholder="{{ id_placeholder }}" oninput="updatePreview()" required/>
      </div>
      <div style="min-width:180px">
        <label>Preview</label>
        <div style="padding:9px 13px;background:var(--navy);border-radius:7px;font-family:monospace;font-size:13px;color:var(--silver-2);letter-spacing:1px">
          <span id="inc-preview">—</span>
        </div>
      </div>
      <button class="btn btn-primary" type="submit" style="margin-bottom:1px">Create Incident</button>
    </form>
  </div>

  <div class="card">
    <div class="card-title">&#128203; Active Incidents</div>
    {% if incidents %}
    <table>
      <thead><tr><th>Incident ID</th><th>Current Stage</th><th>Progress</th><th>Created</th><th></th></tr></thead>
      <tbody>
        {% for i in incidents %}
        <tr>
          <td><a href="/incidents/{{ i.id }}" class="plain" style="font-weight:700">{{ i.id }}</a></td>
          <td>
            {% if i.current_layer %}
              <span class="badge badge-blue">Stage {{ i.current_layer }}</span>
              <span class="muted" style="margin-left:6px;font-size:12px">{{ i.stage_name }}</span>
            {% else %}<span class="badge badge-green">&#10003; Complete</span>{% endif %}
          </td>
          <td class="muted" style="font-size:12px">{{ i.completed }}</td>
          <td class="muted" style="font-size:12px">{{ i.created_at }}</td>
          <td><a href="/incidents/{{ i.id }}" class="btn btn-secondary btn-sm">Open &rarr;</a></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}
    <div style="text-align:center;padding:44px 0;color:var(--muted)">
      <div style="font-size:40px;margin-bottom:12px">&#128203;</div>
      <div style="font-weight:600;font-size:15px">No incidents yet</div>
      <div class="muted" style="margin-top:4px">Create your first incident using the form above</div>
    </div>
    {% endif %}
  </div>
  <div class="disclaimer">{{ disclaimer }}</div>
</div>
<script>
(function(){
  window.updatePreview=function(){
    var v=document.getElementById('inc-input').value;
    document.getElementById('inc-preview').textContent=v||'—';
  };
})();
</script>
</body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# SETUP WIZARD  (split layout with robot panel)
# ─────────────────────────────────────────────────────────────────────────────

SETUP_TMPL = """<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — Setup</title>""" + _CSS + """</head>
<body data-page="setup">""" + _TOPBAR + """
<div class="split-wrap">
  <div class="split-main">
    <div style="margin-bottom:24px">
      <div style="font-size:22px;font-weight:700;color:var(--navy)">Platform Setup</div>
      <div class="muted" style="margin-top:3px">Configure Vectorian for your organization</div>
    </div>
    <div class="wizard-steps">
      <div class="wizard-step {{ 'active' if step==1 else 'done' if step>1 else '' }}">&#9312; Incident Code Format</div>
      <div class="wizard-step {{ 'active' if step==2 else '' }}">&#9313; Stage Configuration</div>
    </div>

    {% if step == 1 %}
    <div class="card">
      <div class="card-title">&#9881; Incident Code Format</div>
      <form method="post" action="/setup/step1">
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;max-width:560px;margin-bottom:24px">
          <div><label>Prefix</label><input type="text" name="prefix" value="{{ cfg.incident_code_format.prefix }}" oninput="updatePreview()"/></div>
          <div><label>Separator</label>
            <select name="separator" onchange="updatePreview()">
              <option value="-" {{ 'selected' if cfg.incident_code_format.separator=='-' }}>Hyphen  —  -</option>
              <option value="_" {{ 'selected' if cfg.incident_code_format.separator=='_' }}>Underscore  —  _</option>
              <option value="/" {{ 'selected' if cfg.incident_code_format.separator=='/' }}>Slash  —  /</option>
            </select>
          </div>
          <div><label>Include Year</label>
            <div style="padding:9px 12px;border:1px solid var(--border);border-radius:7px;background:var(--white)">
              <input type="checkbox" name="year" id="year-chk" onchange="updatePreview()" {{ 'checked' if cfg.incident_code_format.year }} style="width:auto;margin-right:8px"/>Append year
            </div>
          </div>
          <div><label>Sequence Digits</label><input type="number" name="digits" min="2" max="8" value="{{ cfg.incident_code_format.digits }}" oninput="updatePreview()"/></div>
        </div>
        <div style="background:var(--navy);border-radius:10px;padding:18px 24px;margin-bottom:24px;max-width:560px">
          <div style="font-size:10px;letter-spacing:2px;color:var(--silver);text-transform:uppercase;margin-bottom:8px">Live Preview</div>
          <div id="fmt-preview" style="font-size:28px;font-family:monospace;color:var(--white);font-weight:800;letter-spacing:4px"></div>
        </div>
        <button class="btn btn-primary" type="submit">Next &rarr;</button>
      </form>
    </div>
    <script>
    function updatePreview(){
      var p=document.querySelector('[name=prefix]').value||'INC';
      var s=document.querySelector('[name=separator]').value||'-';
      var y=document.getElementById('year-chk').checked;
      var d=parseInt(document.querySelector('[name=digits]').value)||4;
      var parts=[p];if(y)parts.push('2026');parts.push('1'.padStart(d,'0'));
      document.getElementById('fmt-preview').textContent=parts.join(s);
    }
    updatePreview();
    </script>

    {% elif step == 2 %}
    <div class="card">
      <div class="card-title">&#9776; Stage Configuration</div>
      <form method="post" action="/setup/save">
        <table id="stages-table" style="margin-bottom:18px">
          <thead><tr><th>#</th><th>Default Name</th><th>Custom Name <span style="font-weight:400;text-transform:none;letter-spacing:0">(optional)</span></th></tr></thead>
          <tbody>
          {% for s in cfg.stages %}
          <tr>
            <td><span class="badge badge-blue">{{ s.id }}</span></td>
            <td class="muted">{{ s.name }}</td>
            <td>
              <input type="hidden" name="id[]" value="{{ s.id }}"/>
              <input type="hidden" name="name[]" value="{{ s.name }}"/>
              <input type="text" name="custom_name[]" value="{{ s.custom_name }}" placeholder="Leave blank to use default"/>
            </td>
          </tr>
          {% endfor %}
          </tbody>
        </table>
        <div style="display:flex;gap:12px">
          <button type="button" class="btn btn-secondary" onclick="addStage()">&#43; Add Custom Stage</button>
          <button type="submit" class="btn btn-primary">Complete Setup &rarr;</button>
        </div>
      </form>
    </div>
    <script>
    var cc=0;
    function addStage(){
      cc++;var cid='custom_'+cc;
      var tbody=document.querySelector('#stages-table tbody');
      var tr=document.createElement('tr');
      tr.innerHTML='<td><span class="badge badge-silver">'+cid+'</span></td><td class="muted"><em>Custom Stage</em></td><td>'+
        '<input type="hidden" name="id[]" value="'+cid+'"/>'+
        '<input type="hidden" name="name[]" value="Custom Stage"/>'+
        '<input type="text" name="custom_name[]" placeholder="Enter stage name"/></td>';
      tbody.appendChild(tr);
    }
    </script>
    {% endif %}
  </div>
  """ + _ROBOT_PANEL + """
</div></body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG PANEL  (split layout with robot panel)
# ─────────────────────────────────────────────────────────────────────────────

CONFIG_TMPL = """<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — Configuration</title>""" + _CSS + """</head>
<body data-page="config">""" + _TOPBAR + """
<div class="split-wrap">
  <div class="split-main">
    <div style="margin-bottom:24px">
      <div style="font-size:22px;font-weight:700;color:var(--navy)">Configuration</div>
      <div class="muted" style="margin-top:3px">Manage incident codes, stages, owners, and workflow settings</div>
    </div>
    <form method="post" action="/config/save">
      <div class="card">
        <div class="card-title">&#9881; Incident Code Format</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;max-width:700px;margin-bottom:18px">
          <div><label>Prefix</label><input type="text" name="prefix" value="{{ cfg.incident_code_format.prefix }}" oninput="updatePreview()"/></div>
          <div><label>Separator</label>
            <select name="separator" onchange="updatePreview()">
              <option value="-" {{ 'selected' if cfg.incident_code_format.separator=='-' }}>-</option>
              <option value="_" {{ 'selected' if cfg.incident_code_format.separator=='_' }}>_</option>
              <option value="/" {{ 'selected' if cfg.incident_code_format.separator=='/' }}>/</option>
            </select>
          </div>
          <div><label>Year</label>
            <div style="padding:9px 12px;border:1px solid var(--border);border-radius:7px;background:var(--white)">
              <input type="checkbox" name="year" id="year-chk" onchange="updatePreview()" {{ 'checked' if cfg.incident_code_format.year }} style="width:auto;margin-right:8px"/>Yes
            </div>
          </div>
          <div><label>Digits</label><input type="number" name="digits" min="2" max="8" value="{{ cfg.incident_code_format.digits }}" oninput="updatePreview()"/></div>
        </div>
        <div style="background:var(--navy);border-radius:9px;padding:12px 20px;max-width:420px;display:inline-flex;align-items:center;gap:16px">
          <span style="font-size:10px;letter-spacing:2px;color:var(--silver);text-transform:uppercase">Preview</span>
          <span id="fmt-preview" style="font-size:20px;font-family:monospace;color:var(--white);font-weight:800;letter-spacing:3px"></span>
        </div>
      </div>

      <div class="card">
        <div class="card-title">&#9776; Stages
          <button type="button" class="btn btn-secondary btn-sm" style="margin-left:auto" onclick="addStage()">&#43; Add Stage</button>
        </div>
        <table id="stages-table">
          <thead><tr><th style="width:80px">Order</th><th>Stage</th><th>Custom Name</th><th>Owner</th><th>Notes</th><th style="width:76px">Enabled</th><th style="width:54px"></th></tr></thead>
          <tbody id="stages-body">
          {% for i, s in stages_enum %}
          <tr id="row-{{ s.id }}">
            <td style="text-align:center">
              <button type="button" class="btn btn-secondary btn-sm" onclick="moveRow('{{ s.id }}',-1)" style="padding:3px 8px">&#8593;</button>
              <button type="button" class="btn btn-secondary btn-sm" onclick="moveRow('{{ s.id }}',1)"  style="padding:3px 8px">&#8595;</button>
            </td>
            <td>
              <input type="hidden" name="id[]" value="{{ s.id }}"/>
              <span class="badge badge-blue" style="margin-right:6px">{{ s.id }}</span>
              <span class="muted" style="font-size:12px">{{ s.name }}</span>
            </td>
            <td><input type="text" name="custom_name[]" value="{{ s.custom_name }}" placeholder="Override..."/></td>
            <td><input type="text" name="owner[]" value="{{ s.owner }}" placeholder="Assignee..."/></td>
            <td><textarea name="notes[]" rows="1" style="resize:vertical;font-size:12px">{{ s.notes }}</textarea></td>
            <td style="text-align:center"><input type="checkbox" name="enabled_{{ s.id }}" {{ 'checked' if s.enabled }} style="width:auto;transform:scale(1.3)"/></td>
            <td style="text-align:center"><button type="button" class="btn btn-danger btn-sm" onclick="deleteRow('{{ s.id }}')">&#x2715;</button></td>
          </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>

      <div style="display:flex;gap:12px;margin-bottom:40px">
        <button type="submit" class="btn btn-primary">Save Configuration</button>
        <a href="/" class="btn btn-secondary">Cancel</a>
      </div>
    </form>
  </div>
  """ + _ROBOT_PANEL + """
</div>
<script>
var cc={{ custom_count }};
function updatePreview(){
  var p=document.querySelector('[name=prefix]').value||'INC';
  var s=document.querySelector('[name=separator]').value||'-';
  var y=document.getElementById('year-chk').checked;
  var d=parseInt(document.querySelector('[name=digits]').value)||4;
  var parts=[p];if(y)parts.push('2026');parts.push('1'.padStart(d,'0'));
  document.getElementById('fmt-preview').textContent=parts.join(s);
}
updatePreview();
function moveRow(id,dir){
  var el=document.getElementById('row-'+id);if(!el)return;
  if(dir===-1&&el.previousElementSibling)el.parentNode.insertBefore(el,el.previousElementSibling);
  else if(dir===1&&el.nextElementSibling)el.parentNode.insertBefore(el.nextElementSibling,el);
}
function deleteRow(id){var el=document.getElementById('row-'+id);if(el)el.remove();}
function addStage(){
  cc++;var cid='custom_'+cc;
  var tbody=document.getElementById('stages-body');
  var tr=document.createElement('tr');tr.id='row-'+cid;
  tr.innerHTML='<td style="text-align:center">'+
    '<button type="button" class="btn btn-secondary btn-sm" onclick="moveRow(\\\''+cid+'\\\',-1)" style="padding:3px 8px">&#8593;</button>'+
    '<button type="button" class="btn btn-secondary btn-sm" onclick="moveRow(\\\''+cid+'\\\',1)"  style="padding:3px 8px">&#8595;</button></td>'+
    '<td><input type="hidden" name="id[]" value="'+cid+'"/><span class="badge badge-silver">'+cid+'</span>'+
      '<span class="muted" style="font-size:12px;margin-left:6px">Custom Stage</span></td>'+
    '<td><input type="text" name="custom_name[]" placeholder="Stage name..."/></td>'+
    '<td><input type="text" name="owner[]" placeholder="Assignee..."/></td>'+
    '<td><textarea name="notes[]" rows="1" style="resize:vertical;font-size:12px"></textarea></td>'+
    '<td style="text-align:center"><input type="checkbox" name="enabled_'+cid+'" checked style="width:auto;transform:scale(1.3)"/></td>'+
    '<td style="text-align:center"><button type="button" class="btn btn-danger btn-sm" onclick="deleteRow(\\\''+cid+'\\\')">&#x2715;</button></td>';
  tbody.appendChild(tr);
}
</script>
</body></html>"""

# ─────────────────────────────────────────────────────────────────────────────
# INCIDENT DETAIL  (split layout with robot panel)
# ─────────────────────────────────────────────────────────────────────────────

DETAIL_TMPL = """<!doctype html>
<html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>Vectorian — {{ incident_id }}</title>""" + _CSS + """</head>
<body data-page="incident-{{ incident_id }}" data-incident-id="{{ incident_id }}">""" + _TOPBAR + """
<div class="split-wrap">
  <div class="split-main">
    <div style="margin-bottom:20px"><a href="/" class="plain">&larr; Back to Dashboard</a></div>
    <div style="display:flex;align-items:center;gap:14px;margin-bottom:6px">
      <div style="font-size:22px;font-weight:700;color:var(--navy)">{{ incident_id }}</div>
      {% if current_layer %}
        <span class="badge badge-blue">Stage {{ current_layer }} Active</span>
      {% else %}
        <span class="badge badge-green">&#10003; Complete</span>
      {% endif %}
    </div>
    <div class="muted" style="margin-bottom:24px">{{ current_stage_name or 'All stages complete' }}</div>

    <div class="card">
      <div class="card-title">&#9776; Stage Progress</div>
      <div style="margin-bottom:18px">
        {% for s in all_stages %}
          <span class="stage-pill{% if s.id in completed %} done{% elif s.id==current_layer %} current{% endif %}">
            {{ s.id }}: {{ s.custom_name or s.name }}{% if s.id in completed %} &#10003;{% endif %}
          </span>
        {% endfor %}
      </div>
      <div class="muted" style="font-size:12px;margin-bottom:18px">Completed: {{ completed|join(', ') if completed else 'None yet' }}</div>
      {% if current_layer %}
      <form method="post" action="/incidents/{{ incident_id }}/proceed">
        <button class="btn btn-primary" type="submit">&#9658;&nbsp; Run Stage {{ current_layer }}: {{ current_stage_name }}</button>
      </form>
      {% else %}
      <div style="color:var(--success);font-weight:700;font-size:15px">&#10003; Runbook complete. All stages executed.</div>
      {% endif %}
    </div>

    <div class="card">
      <div class="card-title">&#128196; Runbook Output</div>
      <pre>{{ runbook_json }}</pre>
    </div>
    <div class="disclaimer">{{ disclaimer }}</div>
  </div>
  """ + _ROBOT_PANEL + """
</div></body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# FLASK APP
# ─────────────────────────────────────────────────────────────────────────────

def create_app(workdir: str = ".vectrion", data_dir: str = None) -> Flask:
    app = Flask(__name__)
    storage = Storage(Path(workdir))
    dd = Path(data_dir) if data_dir else Path(__file__).resolve().parent / "data"

    def _list_incidents():
        rows = []
        for p in sorted(storage.state_dir.glob("*.json")):
            try:
                s = storage.load_state_obj(p.stem)
                cur = s.get("current_layer")
                rows.append({
                    "id": p.stem,
                    "current_layer": cur,
                    "stage_name": get_stage_name(cur, workdir) if cur else "Complete",
                    "completed": " → ".join(s.get("completed_layers", [])) or "—",
                    "created_at": s.get("created_at", "")[:10],
                })
            except Exception:
                continue
        return rows

    @app.get("/")
    def home():
        if not is_setup_complete(workdir):
            return redirect(url_for("welcome"))
        cfg = load_config(workdir)
        fmt = cfg.get("incident_code_format", {})
        sep = fmt.get("separator", "-")
        prefix = fmt.get("prefix", "INC")
        year = fmt.get("year", True)
        digits = fmt.get("digits", 4)
        placeholder = prefix + sep + ("2026" + sep if year else "") + "1".zfill(digits)
        return render_template_string(
            INDEX_TMPL,
            page_title="Dashboard", active_nav="dashboard",
            incidents=_list_incidents(),
            disclaimer=LEGAL_DISCLAIMER,
            format_json=json.dumps(fmt),
            id_placeholder=placeholder,
        )

    @app.get("/welcome")
    def welcome():
        enter_url = url_for("setup") if not is_setup_complete(workdir) else url_for("home")
        return render_template_string(
            WELCOME_TMPL,
            page_title="Welcome", active_nav="",
            disclaimer=LEGAL_DISCLAIMER,
            enter_url=enter_url,
        )

    @app.get("/setup")
    def setup():
        cfg = load_config(workdir)
        step = int(request.args.get("step", 1))
        return render_template_string(SETUP_TMPL, page_title="Setup", active_nav="", cfg=cfg, step=step)

    @app.post("/setup/step1")
    def setup_step1():
        cfg = load_config(workdir)
        cfg["incident_code_format"] = {
            "prefix":    request.form.get("prefix", "INC").strip(),
            "year":      bool(request.form.get("year")),
            "separator": request.form.get("separator", "-"),
            "digits":    int(request.form.get("digits", 4)),
        }
        save_config(workdir, cfg)
        return redirect(url_for("setup") + "?step=2")

    @app.post("/setup/save")
    def setup_save():
        cfg = load_config(workdir)
        ids = request.form.getlist("id[]")
        names = request.form.getlist("name[]")
        custom_names = request.form.getlist("custom_name[]")
        cfg["stages"] = [
            {"id": sid, "name": names[i] if i < len(names) else sid,
             "custom_name": custom_names[i] if i < len(custom_names) else "",
             "enabled": True, "owner": "", "notes": ""}
            for i, sid in enumerate(ids)
        ]
        cfg["setup_complete"] = True
        save_config(workdir, cfg)
        return redirect(url_for("home"))

    @app.get("/config")
    def config_panel():
        cfg = load_config(workdir)
        stages = cfg.get("stages", [])
        custom_count = sum(1 for s in stages if s["id"].startswith("custom_"))
        return render_template_string(
            CONFIG_TMPL, page_title="Configuration", active_nav="config",
            cfg=cfg, stages_enum=list(enumerate(stages)), custom_count=custom_count,
        )

    @app.post("/config/save")
    def config_save():
        cfg = load_config(workdir)
        ids = request.form.getlist("id[]")
        custom_names = request.form.getlist("custom_name[]")
        owners = request.form.getlist("owner[]")
        notes_list = request.form.getlist("notes[]")
        new_stages = []
        for i, sid in enumerate(ids):
            orig = next((s for s in cfg.get("stages", []) if s["id"] == sid), None)
            new_stages.append({
                "id": sid,
                "name": orig["name"] if orig else "Custom Stage",
                "custom_name": custom_names[i] if i < len(custom_names) else "",
                "enabled": bool(request.form.get(f"enabled_{sid}")),
                "owner": owners[i] if i < len(owners) else "",
                "notes": notes_list[i] if i < len(notes_list) else "",
            })
        cfg["stages"] = new_stages
        cfg["incident_code_format"] = {
            "prefix":    request.form.get("prefix", "INC").strip(),
            "year":      bool(request.form.get("year")),
            "separator": request.form.get("separator", "-"),
            "digits":    int(request.form.get("digits", 4)),
        }
        save_config(workdir, cfg)
        return redirect(url_for("config_panel"))

    @app.post("/incidents/create")
    def create_incident():
        incident_id = (request.form.get("incident_id") or "").strip()
        if not incident_id:
            return redirect(url_for("home"))
        if not storage.load_state_obj(incident_id):
            order = get_stage_order(workdir)
            start = order[0] if order else "1"
            state = {"incident_id": incident_id, "current_layer": start, "completed_layers": [], "runbook": {}}
            storage.save_state_obj(incident_id, state)
            storage.audit(incident_id, "trigger", {"source": "ui"})
        return redirect(url_for("incident_detail", incident_id=incident_id))

    @app.get("/incidents/<incident_id>")
    def incident_detail(incident_id: str):
        s = storage.load_state_obj(incident_id)
        if not s:
            return redirect(url_for("home"))
        cur = s.get("current_layer")
        cfg = load_config(workdir)
        return render_template_string(
            DETAIL_TMPL,
            page_title=incident_id, active_nav="dashboard",
            incident_id=incident_id,
            current_layer=cur,
            current_stage_name=get_stage_name(cur, workdir) if cur else None,
            completed=s.get("completed_layers", []),
            all_stages=cfg.get("stages", []),
            runbook_json=json.dumps(s.get("runbook", {}), indent=2),
            disclaimer=LEGAL_DISCLAIMER,
        )

    @app.post("/incidents/<incident_id>/proceed")
    def incident_proceed(incident_id: str):
        s = storage.load_state_obj(incident_id)
        if not s:
            return redirect(url_for("home"))
        current = s.get("current_layer")
        if current:
            updated = run_layer(s.get("runbook", {}), current, dd, Path(workdir) / "exports")
            s["runbook"] = updated
            done = s.get("completed_layers", [])
            if current not in done:
                done.append(current)
            s["completed_layers"] = done
            s["current_layer"] = next_layer(current, workdir)
            storage.save_state_obj(incident_id, s)
            storage.audit(incident_id, "proceed_ui", {"completed": current, "next": s.get("current_layer")})
        return redirect(url_for("incident_detail", incident_id=incident_id))

    @app.post("/api/chat")
    def api_chat():
        from vectrion.chat import chat
        body = request.get_json(force=True)
        incident_id = body.get("incident_id")
        incident_context = storage.load_state_obj(incident_id) if incident_id else None
        return app.response_class(
            response=json.dumps(chat(body.get("message", ""), incident_context)),
            mimetype="application/json",
        )

    return app


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=8090)


if __name__ == "__main__":
    main()
